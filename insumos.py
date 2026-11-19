import csv
import re
import unicodedata
from pathlib import Path
import pdfplumber

# ============================================================
# 1. CONFIGURAÇÕES
# ============================================================

BASE = Path(__file__).resolve().parent

PASTA_PDFS = BASE / "OneDrive_2026-10-28" / "Dados para ETL - Cozinha"
PASTA_RESULTADOS = BASE / "resultados"

ARQUIVO_SAIDA = PASTA_RESULTADOS / "cursos_insumos_final_ajustado.csv"
ARQUIVO_RELATORIO = PASTA_RESULTADOS / "relatorio_extracao_insumos.csv"
ARQUIVO_REVISAO = PASTA_RESULTADOS / "itens_suspeitos_revisao.csv"


# ============================================================
# 2. NORMALIZAÇÃO E SANEAMENTO
# ============================================================

CORRECOES_OCR_E_VARIACOES = {
    "NTA DO REINO PRETA MOIDA": "PIMENTA DO REINO PRETA MOIDA",
    "GUICA CALABRESA": "LINGUICA CALABRESA",
    "ARROZ AGULINHA": "ARROZ AGULHINHA",
    "OVOS DE GALINHA": "OVO DE GALINHA",
    "COCO RALADO SEM ACUCAR'": "COCO RALADO SEM ACUCAR",
    "BICABORNATO DE SODIO": "BICARBONATO DE SODIO",
    "LIMAOSICILIANO": "LIMAO SICILIANO",
    "CANJICA DE MIIHO BRANCA": "CANJICA DE MILHO BRANCA",
    "QUEJO MINAS FRESCAL": "QUEIJO MINAS FRESCAL",
    "O AGRIAO": "AGRIAO",
    "MOSTARDAAMARELAEMGRAOS": "MOSTARDA AMARELA EM GRAOS",
    "ABACAXIPEROLA": "ABACAXI PEROLA",
    "AZEITONASPRETASSEMCAROCO": "AZEITONAS PRETAS SEM CAROCO",
    "AZEITONASVERDESEMCAROCO": "AZEITONAS VERDES SEM CAROCO",
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip(" :;-',.").upper()


def limpar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def texto_corrompido_cid_ou_sobreposto(texto: str) -> bool:
    if not texto:
        return True
    low = texto.lower()
    if "(cid:" in low or "(cid" in low:
        return True
    palavras = re.findall(r"[A-ZÀ-Ú]{5,}", texto.upper())
    for p in palavras:
        if re.search(r"[AEIOUÁÉÍÓÚÂÊÔÃÕ]{4,}", p):
            return True
        acentos = len(re.findall(r"[ÁÉÍÓÚÂÊÔÃÕÇ]", p))
        if acentos >= 2 and re.search(r"[AEIOUÁÉÍÓÚÂÊÔÃÕ]{3,}", p):
            return True
        if acentos >= 3:
            return True
    return False


def extrair_nome_insumo_limpo(descricao_bruta: str) -> str:
    texto = limpar_texto(descricao_bruta)
    texto = re.sub(r"^ES\d{8,}\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^\d+\s*[.)-]\s*", "", texto)
    texto = re.sub(r"\s+\d+\s*(?:ML|G|GR|KG|L|UNI|M)\b.*$", "", texto, flags=re.IGNORECASE)
    nome = re.split(r"\s*:\s*|\s+-\s+", texto, maxsplit=1)[0]
    nome = nome.strip(" .:-;•*',")

    norm = normalizar(nome)
    if norm in CORRECOES_OCR_E_VARIACOES:
        return CORRECOES_OCR_E_VARIACOES[norm]

    return nome


def extrair_nome_curso(pdf, caminho_pdf: Path) -> str:
    for pagina in pdf.pages[:35]:
        for tabela in pagina.extract_tables():
            for linha in tabela:
                celulas = [limpar_texto(c) for c in linha if c]
                for idx, cel in enumerate(celulas):
                    if normalizar(cel) in {"CURSO", "CURSO:"} and idx + 1 < len(celulas):
                        candidato = celulas[idx + 1]
                        if candidato and normalizar(candidato) not in {"QTD TOTAL DE ALUNOS", "SEGMENTO"}:
                            return candidato

        texto = pagina.extract_text() or ""
        if "(cid:" in texto.lower():
            continue

        m1 = re.search(r"CURSO\s*:\s*([^\n]+)", texto, flags=re.IGNORECASE)
        if m1:
            nome = limpar_texto(m1.group(1))
            nome = re.split(r"\s+(?:QTD\s+TOTAL|SEGMENTO|CARGA\s+HORARIA)", nome, flags=re.IGNORECASE)[0]
            if nome and normalizar(nome) not in {"CURSO", "QTD TOTAL DE ALUNOS"}:
                return nome.strip()

    nome = caminho_pdf.stem
    nome = re.sub(r"-\d+-horas.*$", "", nome, flags=re.IGNORECASE)
    return nome.replace("-", " ").strip()


# ============================================================
# 3. CLASSIFICADOR SEMÂNTICO (INSUMO VS UTENSÍLIO/EQUIPAMENTO)
# ============================================================

TERMOS_PROIBIDOS_EXATOS = {
    # Eletrodomésticos e Equipamentos
    "AR-CONDICIONADO", "AR CONDICIONADO", "COMPUTADOR", "MONITOR", "REFRIGERADOR",
    "FREEZER", "GELADEIRA", "FORNO", "FOGAO", "LIQUIDIFICADOR", "PROCESSADOR",
    "BATEDEIRA", "CAFETEIRA", "MICRO-ONDAS", "MICROONDAS", "COIFA", "EXAUSTOR",
    "BALCAO", "BALCOES", "ESTANTE", "PRATELEIRA", "PIA", "TANQUE", "EXPOSITOR", "VITRINE",
    "PURIFICADOR DE AGUA", "PROJETOR MULTIMIDIA", "PROJETOR MULTIMIDEA",
    "QUADRO BRANCO", "QUADRO DE VIDRO", "LOUSA DIGITAL", "CILINDRO ELETRICO",
    "EXTRATOR DE SUCOS", "EXTRATOR DE FRUTAS", "FATIADOR DE FRIOS", "FATIADOR DE PAES",
    "FRITADEIRA", "MIXER", "MULTIPROCESSADOR", "SELADORA", "MOEDOR DE CARNE",
    "MAQUINA DE MOER", "MAQUINA DEFUMADORA", "MAQUINA DE PICOLE", "SORVETEIRA",
    "SERRA FITA", "AMACIADOR DE BIFE", "BALANCA DIGITAL", "BALACA",
    "TERMOMETRO CULINARIO", "MACARICO", "CHAMBER", "SOUS VIDE", "TERMO CIRCULADOR",
    "CAMARA DE FERMENTACAO", "DIVISORA DE MASSAS", "MASSEIRA", "MASSEIRAS",
    "MODELADORA", "PLACA DE INDUCAO", "ULTRACONGELADOR", "FRIO RAPIDO",
    "DEFUMADOR", "DEFUMDOR", "DESIDRATADORA", "INFUSOR DE FUMACA", "BOMBA DE AQUARIO",
    "ENSACADOR MANUAL", "CARRINHO COM RODAS", "GUERIDON",
    # Utensílios e Ferramentas (singular + plural)
    "PINCA", "PINCAS", "PEGADOR", "PEGADORES", "ROLO LAMINADOR", "CORTADOR", "CORTADORES",
    "ARO", "AROS", "PIRES", "PLACA DE CORTE", "PLACAS DE ETILENO", "PORTA CONDIMENTO",
    "POTE HERMETICO", "POTE BISNAGA", "BISNAGA", "RALADOR", "ZESTER",
    "SERINGA", "SIFAO", "SPEED RAIL", "STOREN POUR", "SUPORTE PARA PLACAS",
    "SUPORTE DE PAS", "SUPORTE PARA FILTRO", "TAPETE DE SILICONE", "SERVICE MAT",
    "TESOURA", "TRAVESSA", "BOWL", "BOWLS", "BOWLL", "CAIXA PLASTICA", "CAIXA TERMICA",
    "CONTENTOR", "CHAIRA", "DESCASCADOR", "ESCUMADEIRA", "FOUET", "FUNIL",
    "MANDOLINE", "MANDOLIN", "MOEDOR", "PEDRA DE AFIAR", "ESPATULA", "PA PARA",
    "GRADE", "FORMA", "FORMAS", "TABUA", "TABUAS", "FACA", "FACAS", "BARRA MAGNETICA",
    "PANELA", "PANELAS", "FRIGIDEIRA", "CALDEIRAO", "ASSADEIRA", "TIGELA", "CUBA", "CUBAS",
    "CONCHA", "ESCORREDOR", "PENEIRA", "COLHER", "COLHERES", "GARFO", "GARFOS",
    "PRATO", "PRATOS", "COPO", "COPOS", "XICARA", "XICARAS", "TACA", "TACAS",
    "JARRA", "TERMOMETRO", "BALANCA", "MEDIDOR", "MEDIDORES", "MEDIDORA",
    "AZEITEIRO", "RECIPIENTE", "DISPENSADOR", "RAMEQUIN", "RAMEQUINS", "BACIA",
    "MANDUCA", "ABRIDOR", "BORRIFADOR", "CHALEIRA", "BULE", "GALHETEIRO",
    "BICO DE CONFEITAR", "BICOS PARA CONFEITAR", "ADAPTADOR", "BAILARINA",
    "BAILARINAS", "BAILHARINAS", "PINCEL CULINARIO", "ROLO DE MASSA",
    "CARRETILHA", "VAZADOR", "BOLEADOR", "DESCAROCADOR", "ESPREMEDOR", "AMASSADOR",
    "SOCADOR", "COQUETELEIRA", "DOSADOR", "MUDDLER", "PASSADOR", "CHINOIS",
    "TAMIS", "CUSCUZEIRA", "VAPOREIRA", "CHAPA", "GRELHA", "ESPETO", "GANCHO",
    "BATEDOR MANUAL", "CUTELO", "RASPADOR", "CRONOMETRO", "REFIL GAS", "WOK",
    "CANECA DE COBRE", "CESTO PARA PAES", "CLOCHE", "COADOR", "STRAINER", "DECANTER",
    "GARRAFA TERMICA", "MACERADOR", "RECHAUD", "SOUSPLAT", "VACUO VINS",
    "JOGO AMERICANO", "PANO COBRE MANCHAS", "ARCO DE SERRA", "BAR CADDY",
    "CAVIAR BOX", "LICOREIRA", "MINI PITCHER", "MOLDE STENCIL", "PICOLETEIRA",
    "CUSPIDEIRA", "CHAWAM", "TACHO", "AEROPRESS", "AMPOLAS", "BISTURI", "LEITEIRA",
    # Limpeza, Higiene, Escritório, Descartáveis, Decoração não-comestível e EPIs
    "FIBRA SINTETICA", "FIBRACO", "FOSFORO", "HIPOCLORITO", "MASCARA",
    "PANO MULTIUSO", "PANO DE PRATO", "PANO PARA LIMPEZA", "PAPEL ALUMINIO",
    "POTE COM TAMPA", "SACO PLASTICO", "SACO DE LIXO", "SABONETE", "TOUCA",
    "BANDEJA", "APAGADOR", "PAPEL A4", "SULFITE", "PINCEL", "ALCOOL",
    "ALCOOL ETILICO", "AGUA SANITARIA", "PAPEL TOALHA", "ESCOVA DE LIMPEZA",
    "ESCOVA PARA LIMPEZA", "AVENTAL", "CALCA", "CAMISETA", "CAMISA SOCIAL",
    "COLETE ADULTO", "GRAVATA", "GRAVADA", "DOLMA", "SAPATO", "BOTA", "JALECO",
    "JAPONA", "LUVA", "ESPONJA", "DETERGENTE", "DESINFETANTE", "VASSOURA",
    "RODO", "LIXEIRA", "FILME PVC", "PAPEL MANTEIGA", "GUARDANAPO",
    "PALITO DE BAMBU", "PALITO DE DENTE", "ALGODAO", "BOBINA", "SACO DE CONFEITAR",
    "CERTIFICADO", "ETIQUETA ADESIVA", "ETIQUETA", "MARMITEX", "EMBALAGEM",
    "CAIXA DE PAPELAO", "BARBANTE", "ISQUEIRO", "CANETA", "LAPIS", "BORRACHA",
    "GRAMPEADOR", "PRANCHETA", "PASTA", "CADERNO", "ESTOJO PERSONALIZADO",
    "FILTRO DE PAPEL", "FILTRO KALITA", "CANUDO", "ISOPOR", "TOPO DE BOLO",
    "PISTILO PARA ARTESANATO", "VOAL",
    # Móveis e Estruturas
    "BANCADA", "BANCADAS", "MESA", "CADEIRA", "ARMARIO", "CARTEIRA UNIVERSITARIA",
    "SOFTWARE", "EQUIPAMENTO", "UTENSILIO", "PENDAL"
}

REGEX_MATERIAIS_E_MEDIDAS_UTENSILIO = re.compile(
    r"\b(?:INOX|INOXIDAVEL|ACO INOX|SILICONE|POLIETILENO|POLIPROPILENO|ALUMINIO|"
    r"VIDRO TEMPERADO|CERAMICA|PORCELANA|LOUCA|MADEIRA|BAMBU|PLASTICO|PVC|TEFLON|"
    r"ANTIADERENTE|ACRILICO|NYLON|COBRE|110V|220V|127V|BIVOLT|WATTS|CM|MM|POLEGADAS|"
    r"MALHA FINA|CABO BRANCO|CABO PRETO|CABO VERMELHO|CABO VERDE|CABO AZUL|"
    r"CABO AMARELO|DESCARTAVEL|OCUPACIONAL|ISOPOR|ARTESANATO)\b"
)

REGEX_SINAIS_ALIMENTO = re.compile(
    r"\b(?:ACUCAR|SAL|OLEO|AZEITE|FARINHA|FERMENTO|BICARBONATO|BICABORNATO|LEITE|"
    r"MANTEIGA|MARGARINA|CREME DE LEITE|NATA|QUEIJO|QUEJO|MOZZARELLA|MUCARELA|"
    r"FIOR DI LATTE|BURRATA|RICOTA|CHEDDAR|REQUEIJAO|CATUPIRY|PARMESAO|COALHO|PROVONE|"
    r"OVO|OVOS|CARNE|FRANGO|PEIXE|CAMARAO|BACON|GUANCIALE|PANCETTA|LINGUICA|PRESUNTO|"
    r"CHARQUE|ALCATRA|PATINHO|FILE|MIGNON|CONTRAFILE|COSTELA|COSTELINHA|LOMBO|PERNIL|"
    r"BISTECA|CUPIM|MUSCULO|ACEM|PICANHA|MAMINHA|FRALDINHA|COXAO|LAGARTO|DIAFRAGMA|"
    r"MIOLO DE ANCHO|PALETA DE CORDEIRO|MAGRET|PERU|ROBALO|TILAPIA|PESCADA|SARDINHA|ATUM|"
    r"BACALHAU|POLVO|LULA|MEXILHAO|KANI KAMA|QUARTO TRASEIRO|QUARTO DIANTEIRO|PONTA DE AGULHA|"
    r"ARROZ|FEIJAO|MACARRAO|SPAGHETTI|MASSA|FUBA|AMIDO|POLVILHO|AVEIA|TRIGO|MILHO|MIIHO|"
    r"CANJICA|CUSCUZ|SOJA|TOFU|LENTILHA|GRAO DE BICO|QUINOA|"
    r"TOMATE|CEBOLA|ALHO|BATATA|CENOURA|BETERRABA|ABOBORA|ABOBRINHA|MANDIOCA|AIPIM|INHAME|"
    r"PIMENTAO|ALFACE|COUVE|REPOLHO|ESPINAFRE|RUCULA|AGRIAO|CHICORIA|BROCOLIS|COUVE-FLOR|"
    r"BERINJELA|CHUCHU|QUIABO|VAGEM|PEPINO|RABANETE|ASPARGO|CHEIRO VERDE|COENTRO|SALSA|"
    r"SALSINHA|CEBOLINHA|CEBOULLETE|HORTELA|MANJERICAO|ALFAVACA|ALECRIM|TOMILHO|OREGANO|"
    r"LOURO|ENDRO|DILL|CANELA|CRAVO|PIMENTA|COMINHO|CURCUMA|ACAFRAO|COLORAU|PAPRICA|"
    r"NOZ MOSCADA|GENGIBRE|BAUNILHA|ESSENCIA|CORANTE|CMC|CARBOXIMETILCELULOSE|"
    r"LIGA NEUTRA|DESMOLDANTE|SUMAGRE|SUMAC|CUMARU|CARDAMOMO|ERVA DOCE|ERVAS|"
    r"BANANA|MACA|LARANJA|LIMAO|LIMAOSICILIANO|ABACAXI|ABACAXIPEROLA|MAMAO|MANGA|MORANGO|"
    r"UVA|MARACUJA|COCO|MELANCIA|MELAO|ABACATE|AVOCADO|GOIABA|GOIABADA|PESSEGO|AMEIXA|"
    r"CAJU|ACEROLA|TANGERINA|MEXERICA|KIWI|CEREJA|AMARENA|FRAMBOESA|AMORA|MIRTILO|MIRTILOS|"
    r"PEQUI|POLPA|CHOCOLATE|CACAU|MEL|MELADO|GLICOSE|GELATINA|CHANTILLY|DOCE DE LEITE|"
    r"LEITE CONDENSADO|BOMBOM|GRANULADO|SORVETE|PO DOURADO|PO PEROLADO|PO COBRE|"
    r"FOLHAS DE OURO|FLOR COMESTIVEL|VINAGRE|ACETO|SHOYU|MOSTARDA|MOSTARDAAMARELAEMGRAOS|"
    r"KETCHUP|MAIONESE|EXTRATO DE TOMATE|MOLHO|CREME BALSAMICO|AZEITONA|AZEITONAS|"
    r"AZEITONASPRETASSEMCAROCO|AZEITONASVERDESEMCAROCO|ALCAPARRA|ALCAPARRAS|CHAMPIGNON|"
    r"COGUMELO|FUNGHI|PALMITO|ERVILHA|ERVILHAS|VINHO|ESPUMANTE|CERVEJA|CACHACA|RUM|"
    r"CONHAQUE|LICOR|APEROL|BITTER|CAMPARI|TEQUILA|VERMOUTH|VERMUTE|VODKA|WHISKY|WHISKEY|"
    r"XAROPE|SUCO|CAFE|CHA|AGUA|GELO|PAO|TORRADA|BISCOITO|BOLACHA|CASTANHA|NOZES|"
    r"AMENDOA|AMENDOIM|AVELA|PISTACHE|UVA PASSA|FRUTOS SECOS|CURRY|IN NATURA|"
    r"CONGELAD[OA]|RESFRIAD[OA]|TIPO 1|SEM SAL|COM SAL|INTEGRAL|DESNATAD[OA]|MOID[OA]|"
    r"RALAD[OA]|FATIAD[OA]|EM PO|EM GRAO|EXTRA VIRGEM|REFINAD[OA]|CRISTAL|DEMERARA|COMESTIVEL)\b"
)

CABECALHOS_E_SECOES = {
    "CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO DETALHADA", "DESCRICAO",
    "ESPECIFICACAO", "U.M", "QUANTIDADE POR ALUNO", "QUANTIDADE POR TURMA",
    "VALOR UNITARIO", "VALOR TOTAL", "TOTAL", "PESO", "APROXIMADO DE",
    "TIPO DE FINANCIAMENTO", "INSUMOS", "MIDIA ESPECIALIZADA", "BANCO DE PRECOS",
    "ESTIMATIVA", "UNIFORMES", "MODO DE PREPARO", "INFRAESTRUTURA E LISTA BASICA1",
    "INFRAESTRUTURA E LISTA BASICA", "INDICADORES", "LISTA BASICA",
    "DADOS DA LISTA BASICA", "DADOS DO CURSO", "QUALIFICACAO PROFISSIONAL",
    "ULTIMA REVISAO", "UNIFORME", "DESCRICAO DO INGREDIENTE", "ITEM",
    "QUANTIDADE", "MEDIDA", "CATEGORIA", "NAO SE APLICA", "SENAC", "UNIDADE",
    "PACOTE", "CAIXA", "LATA", "VIDRO", "GARRAFA", "MACO", "RESMA", "FARDO",
    "POTE", "ROLO", "QTD TOTAL DE ALUNOS", "RESPONSAVEL- ELABORACAO",
    "RESPONSAVEL ELABORACAO", "DATA DE ELABORACAO", "RESPONSAVEL",
    "RESPONSAVEL - REVISAO", "SEGMENTO", "CARGA HORARIA", "TIPO", "CODIGO SIG",
    "AULAS PLANEJADAS", "PLANEJAMENTO DAS AULAS", "LANCAMENTO NO SEI",
    "PRODUCAO DE ALIMENTOS", "PROGRAMA SOCIOPROFISSIONAL",
    "HABILITACAO PROFISSIONAL TECNICA DE NIVEL MEDIO", "UNIDADE CURRICULAR",
    "UNIDADE(S) CURRICULAR(ES)", "UC", "CURSO", "DOCENTE",
    "PLANO DE TRABALHO DOCENTE – SENAC DF", "PLANO DE TRABALHO DOCENTE - SENAC DF",
    "GARDE MANGER", "SITUACAO DE APRENDIZAGEM", "INTRODUCAO AO PI",
    "DESENVOLVIMENTO DE SOLUCOES", "FICHA TECNICA DE PRODUCAO",
    "PRATICAS OPERACIONAIS EM NUTRICAO E DIETETICA",
    "PREPARO DE ALIMENTOS SEM GLUTEN"
}

PADROES_RUIDO_REGEX = [
    r"\bAULA\b",
    r"^ATIVIDADES?\b",
    r"\(SEI\s*\d+\)",
    r"^\d+\s*H(?:ORAS)?$",
    r"^\d+\s*ALUNOS?$",
    r"^UC\s*\d+",
    r"\b(?:COZINHE|BATA|MISTURE|ADICIONE|RESERVE|HIGIENIZE|PENEIRE|MISTURAR|MEXA|LEVE AO FORNO|CORTE EM|DESCASQUE|REFOGUE|DEIXE DESCANSAR)\b",
    r"\b(?:ATIVIDADE PRATICA|ATIVIDADE TEORICA|VISITA TECNICA|UNIDADE CURRICULAR|SITUACAO DE APRENDIZAGEM|ESPACO PRIVILEGIADO|PERGUNTAS OBJETIVAS|DESENVOLVIMENTO DO PI)\b",
    r"\b(?:SAO PAULO|ED\.|EDITORA|CHEF PROFISSIONAL)\b",
]


def classificar_item(titulo_insumo: str, vocabulario_receitas: set[str]) -> str:
    if texto_corrompido_cid_ou_sobreposto(titulo_insumo):
        return "DESCARTAR"

    desc_upper = normalizar(titulo_insumo)

    if len(desc_upper) < 3:
        return "DESCARTAR"

    if not re.search(r"[A-Z]", desc_upper):
        return "DESCARTAR"

    if re.fullmatch(r"[\d\s.,/R$-]+", desc_upper):
        return "DESCARTAR"

    if re.fullmatch(r"ES\d+", desc_upper) or desc_upper.startswith("ES0"):
        return "DESCARTAR"

    if desc_upper in CABECALHOS_E_SECOES:
        return "DESCARTAR"

    for padrao in PADROES_RUIDO_REGEX:
        if re.search(padrao, desc_upper):
            return "DESCARTAR"

    if len(desc_upper.split()) > 10:
        return "DESCARTAR"

    excecoes_validas = {
        "QUARTO TRASEIRO",
        "QUARTO DIANTEIRO",
        "PONTA DE AGULHA",
        "MEIA CARCACA",
        "CARCACA DE FRANGO",
        "PAO DE FORMA",
        "MASSA PARA PASTEL EM ROLO",
        "BANANA PRATA",
    }
    if any(exc in desc_upper for exc in excecoes_validas):
        return "INSUMO_CONFIRMADO"

    # 1. Bloqueio por material/dimensão típica de utensílio/equipamento
    if REGEX_MATERIAIS_E_MEDIDAS_UTENSILIO.search(desc_upper):
        return "DESCARTAR"

    # 2. Bloqueio por lista negra de utensílios/equipamentos/limpeza
    palavras_titulo = set(re.findall(r"[A-Z0-9-]+", desc_upper))
    for termo in TERMOS_PROIBIDOS_EXATOS:
        if " " in termo:
            if re.search(rf"\b{re.escape(termo)}\b", desc_upper):
                return "DESCARTAR"
        else:
            if termo in palavras_titulo:
                return "DESCARTAR"

    # 3. Confirmação positiva: está nas fichas técnicas OU tem radical culinário
    if desc_upper in vocabulario_receitas or REGEX_SINAIS_ALIMENTO.search(desc_upper):
        return "INSUMO_CONFIRMADO"

    # 4. Zona cinzenta
    return "SUSPEITO"


# ============================================================
# 4. EXTRAÇÃO DAS TABELAS E FICHAS TÉCNICAS
# ============================================================

def identificar_indice_coluna_descricao(cabecalho_linha: list[str]) -> int | None:
    for idx, celula in enumerate(cabecalho_linha):
        norm = normalizar(celula)
        if "DESCRICAO" in norm or "ESPECIFICACAO" in norm or "INGREDIENTE" in norm:
            return idx
    return None


def tabela_e_de_metadados_ou_cronograma(tabela: list[list[str]]) -> bool:
    texto_inteiro = normalizar(" ".join(
        limpar_texto(c) for linha in tabela for c in (linha or []) if c
    ))
    if any(k in texto_inteiro for k in ("CODIGO ITEM MXM", "QUANTIDADE POR TURMA", "DESCRICAO DO INGREDIENTE", "U.M", "VALOR UNITARIO")):
        return False

    amostra = normalizar(" ".join(
        limpar_texto(c) for linha in tabela[:4] for c in (linha or []) if c
    ))
    marcadores_nao_insumo = [
        "QTD TOTAL DE ALUNOS", "DADOS DO CURSO", "PLANEJAMENTO DAS AULAS",
        "AULAS PLANEJADAS", "MODO DE PREPARO", "ELEMENTOS DA COMPETENCIA",
        "ORGANIZACAO CURRICULAR", "BIBLIOGRAFIA", "SITUACAO DE APRENDIZAGEM"
    ]
    return any(m in amostra for m in marcadores_nao_insumo)


def linha_parece_item_valido(valores: list[str], modo_ficha_aula: bool) -> bool:
    texto_completo = normalizar(" ".join(v for v in valores if v))

    if modo_ficha_aula:
        tem_numero = any(re.fullmatch(r"\d+(?:[.,]\d+)?", v.strip()) for v in valores if v)
        tem_unidade = bool(re.search(r"\b(?:G|GR|KG|ML|L|UN|UNID|UNIDADE|PCT|CX|LATA|DENTE|FOLHA|MACO|COLHER|XICARA|Q\.?B\.?|A GOSTO)\b", texto_completo))
        return tem_numero or tem_unidade
    else:
        marcadores_lista_basica = (
            r"\b(?:KG|UNIDADE|UNI|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
            r"LITRO|PECA|BANDEJA|NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|BANCO DE PRECOS)\b|R\$|ES0"
        )
        return bool(re.search(marcadores_lista_basica, texto_completo))


def extrair_melhor_candidato_descricao(valores: list[str]) -> str:
    ignorados = CABECALHOS_E_SECOES | {
        "NAO SE APLICA", "SENAC", "MIDIA ESPECIALIZADA", "BANCO DE PRECOS", "ESTIMATIVA",
        "KG", "UNI", "PCT", "MC", "CX", "RL", "LITRO"
    }
    candidatos = []

    for v in valores:
        if not v:
            continue
        v_norm = normalizar(v)
        if len(v_norm) < 3:
            continue
        if v_norm in ignorados:
            continue
        if re.fullmatch(r"[\d.,R$\s/-]+", v_norm):
            continue
        if re.fullmatch(r"ES\d+", v_norm) or v_norm.startswith("ES0"):
            continue
        candidatos.append(v)

    return max(candidatos, key=len) if candidatos else ""


def consolidar_linhas_quebradas_tabela(tabela: list[list[str]]) -> list[list[str]]:
    linhas_consolidadas = []
    buffer_texto = []

    marcadores_linha_completa = (
        r"\b(?:KG|UNIDADE|UNI|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
        r"LITRO|PECA INTEIRA|PECA|BANDEJA|NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|BANCO DE PRECOS)\b|R\$"
    )

    for linha in tabela:
        if not linha:
            continue
        valores = [limpar_texto(v) for v in linha]
        texto_linha = " ".join(v for v in valores if v)
        texto_norm = normalizar(texto_linha)

        if not texto_norm or texto_norm.startswith("VALOR TOTAL"):
            continue

        if any(h in texto_norm for h in ("CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO", "QUANTIDADE POR TURMA")):
            buffer_texto.clear()
            linhas_consolidadas.append(valores)
            continue

        tem_marcador = bool(re.search(marcadores_linha_completa, texto_norm))

        if not tem_marcador:
            cand = extrair_melhor_candidato_descricao(valores)
            if cand:
                buffer_texto.append(cand)
        else:
            if buffer_texto:
                texto_acumulado = " ".join(buffer_texto)
                buffer_texto.clear()
                valores_unidos = [texto_acumulado] + valores
                linhas_consolidadas.append(valores_unidos)
            else:
                linhas_consolidadas.append(valores)

    return linhas_consolidadas


def extrair_itens_fichas_pdf(pdf) -> list[str]:
    encontrados = []

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text() or ""
        texto_pag_norm = normalizar(texto_pag)
        if "DESCRICAO DO INGREDIENTE" not in texto_pag_norm:
            continue

        tabelas = pagina.extract_tables() or []
        achou_na_tabela = False

        for tabela in tabelas:
            if not tabela or tabela_e_de_metadados_ou_cronograma(tabela):
                continue

            em_tabela_ingredientes = False
            idx_ingrediente = 1

            for linha in tabela:
                if not linha:
                    continue
                valores = [limpar_texto(v) for v in linha]
                texto_linha_norm = normalizar(" ".join(v for v in valores if v))

                if "DESCRICAO DO INGREDIENTE" in texto_linha_norm:
                    em_tabela_ingredientes = True
                    novo_idx = identificar_indice_coluna_descricao(valores)
                    if novo_idx is not None:
                        idx_ingrediente = novo_idx
                    continue

                if "MODO DE PREPARO" in texto_linha_norm:
                    em_tabela_ingredientes = False
                    continue

                if not em_tabela_ingredientes:
                    continue

                if not linha_parece_item_valido(valores, modo_ficha_aula=True):
                    continue

                candidato = valores[idx_ingrediente] if idx_ingrediente < len(valores) else ""
                nome = extrair_nome_insumo_limpo(candidato)
                if nome:
                    achou_na_tabela = True
                    encontrados.append(nome)

        if not achou_na_tabela:
            em_ingredientes = False
            for linha in texto_pag.splitlines():
                linha_limpa = limpar_texto(linha)
                norm = normalizar(linha_limpa)
                if "DESCRICAO DO INGREDIENTE" in norm:
                    em_ingredientes = True
                    continue
                if "MODO DE PREPARO" in norm:
                    em_ingredientes = False
                    continue
                if em_ingredientes:
                    m = re.match(
                        r"^\d+[.)-]?\s+(.+?)\s+\d+(?:[.,]\d+)?\s*(?:g|gr|kg|ml|l|uni|un|mc|mç|pct)\b",
                        linha_limpa,
                        flags=re.IGNORECASE,
                    )
                    if m:
                        nome = extrair_nome_insumo_limpo(m.group(1))
                        if nome:
                            encontrados.append(nome)

    return encontrados


def construir_vocabulario_global_receitas(arquivos_pdf: list[Path]) -> set[str]:
    """Passada 1 otimizada: usa extração rápida de texto para mapear ingredientes das receitas."""
    vocabulario = set()
    total = len(arquivos_pdf)
    print(f"Passada 1/2: Mapeando vocabulário de ingredientes em {total} PDFs...")

    for idx, caminho_pdf in enumerate(arquivos_pdf, start=1):
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                for pagina in pdf.pages:
                    texto_pag = pagina.extract_text() or ""
                    if "DESCRICAO DO INGREDIENTE" not in normalizar(texto_pag):
                        continue

                    em_ingredientes = False
                    for linha in texto_pag.splitlines():
                        linha_limpa = limpar_texto(linha)
                        norm = normalizar(linha_limpa)
                        if "DESCRICAO DO INGREDIENTE" in norm:
                            em_ingredientes = True
                            continue
                        if "MODO DE PREPARO" in norm:
                            em_ingredientes = False
                            continue
                        if em_ingredientes:
                            m = re.match(
                                r"^\d+[.)-]?\s+(.+?)\s+\d+(?:[.,]\d+)?\s*(?:g|gr|kg|ml|l|uni|un|mc|mç|pct)\b",
                                linha_limpa,
                                flags=re.IGNORECASE,
                            )
                            if m:
                                nome = normalizar(extrair_nome_insumo_limpo(m.group(1)))
                                if len(nome) >= 2 and nome not in CABECALHOS_E_SECOES:
                                    vocabulario.add(nome)
        except Exception:
            pass

        if idx % 10 == 0 or idx == total:
            print(f"  -> Vocabulário mapeado: {idx}/{total} arquivos...")

    print(f"Vocabulário base construído com {len(vocabulario)} ingredientes únicos.\n")
    return vocabulario


def extrair_insumos_pdf(
    pdf, nome_curso: str, vocabulario_receitas: set[str]
) -> tuple[list[str], list[str], bool]:
    insumos = []
    suspeitos = []
    nome_curso_norm = normalizar(nome_curso)
    na_lista_basica = False
    tem_cid = False

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text() or ""
        if "(cid:" in texto_pag.lower():
            tem_cid = True

        texto_pag_norm = normalizar(texto_pag)

        if (
            "LISTA BASICA" in texto_pag_norm
            or ("DADOS DA LISTA" in texto_pag_norm and "BASICA" in texto_pag_norm)
            or re.search(r"\bINSUMOS\b", texto_pag_norm)
        ):
            na_lista_basica = True

        # Encerra quando a Lista Básica acaba
        if na_lista_basica and any(
            marc in texto_pag_norm
            for marc in (
                "ANEXO",
                "DESCRICAO DO INGREDIENTE",
                "PLANEJAMENTO DAS AULAS",
                "ORGANIZACAO CURRICULAR",
                "BIBLIOGRAFIA",
            )
        ):
            break

        if not na_lista_basica:
            continue

        for tabela in pagina.extract_tables():
            if not tabela or tabela_e_de_metadados_ou_cronograma(tabela):
                continue

            linhas_tratadas = consolidar_linhas_quebradas_tabela(tabela)

            for valores in linhas_tratadas:
                texto_linha_norm = normalizar(" ".join(v for v in valores if v))
                if any(h in texto_linha_norm for h in ("CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO")):
                    continue

                if not linha_parece_item_valido(valores, modo_ficha_aula=False):
                    continue

                candidato = extrair_melhor_candidato_descricao(valores)
                nome_insumo = extrair_nome_insumo_limpo(candidato)

                if not nome_insumo or normalizar(nome_insumo) == nome_curso_norm:
                    continue

                status_item = classificar_item(nome_insumo, vocabulario_receitas)

                if status_item == "INSUMO_CONFIRMADO":
                    if not any(normalizar(x) == normalizar(nome_insumo) for x in insumos):
                        insumos.append(nome_insumo)
                elif status_item == "SUSPEITO":
                    if not any(normalizar(x) == normalizar(nome_insumo) for x in suspeitos):
                        suspeitos.append(nome_insumo)

    # Fallback: se o PDF não tinha Lista Básica, usa diretamente as Fichas Técnicas dele
    if not insumos:
        for cand in extrair_itens_fichas_pdf(pdf):
            if not cand or normalizar(cand) == nome_curso_norm:
                continue
            if classificar_item(cand, vocabulario_receitas) != "DESCARTAR":
                if not any(normalizar(x) == normalizar(cand) for x in insumos):
                    insumos.append(cand)

    return insumos, suspeitos, tem_cid


# ============================================================
# 5. FLUXO PRINCIPAL
# ============================================================

def main():
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    arquivos_pdf = sorted(PASTA_PDFS.rglob("*.pdf"))

    if not arquivos_pdf:
        print(f"Nenhum PDF encontrado em: {PASTA_PDFS}")
        return

    vocabulario_receitas = construir_vocabulario_global_receitas(arquivos_pdf)

    total_erros = 0
    total_geral_insumos = 0
    relatorio = []
    todos_suspeitos = []

    print("Passada 2/2: Extraindo e classificando insumos de todos os cursos...")

    with ARQUIVO_SAIDA.open("w", encoding="utf-8-sig", newline="") as arquivo_saida:
        escritor = csv.DictWriter(
            arquivo_saida,
            fieldnames=["nome_curso", "insumo"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor.writeheader()

        for indice, caminho_pdf in enumerate(arquivos_pdf, start=1):
            try:
                with pdfplumber.open(caminho_pdf) as pdf:
                    nome_curso = extrair_nome_curso(pdf, caminho_pdf)
                    insumos, suspeitos, tem_cid = extrair_insumos_pdf(
                        pdf, nome_curso, vocabulario_receitas
                    )

                for insumo in insumos:
                    escritor.writerow({
                        "nome_curso": nome_curso,
                        "insumo": insumo
                    })

                for susp in suspeitos:
                    todos_suspeitos.append({
                        "arquivo": caminho_pdf.name,
                        "nome_curso": nome_curso,
                        "item_suspeito": susp
                    })

                qtd_insumos = len(insumos)
                total_geral_insumos += qtd_insumos

                if qtd_insumos > 0:
                    status = "OK"
                elif tem_cid:
                    status = "FONTE CORROMPIDA (CID) - REQUER OCR"
                else:
                    status = "SEM INSUMOS"

                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": nome_curso,
                    "qtd_insumos": qtd_insumos,
                    "qtd_suspeitos": len(suspeitos),
                    "status": status
                })

                print(
                    f"[{indice}/{len(arquivos_pdf)}] {nome_curso} | "
                    f"Insumos: {qtd_insumos} | Suspeitos: {len(suspeitos)} ({status})"
                )

            except Exception as erro:
                total_erros += 1
                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": "",
                    "qtd_insumos": 0,
                    "qtd_suspeitos": 0,
                    "status": f"ERRO: {erro}"
                })
                print(f"ERRO ao processar {caminho_pdf.name}: {erro}")

    with ARQUIVO_RELATORIO.open("w", encoding="utf-8-sig", newline="") as arquivo_relatorio:
        escritor_rel = csv.DictWriter(
            arquivo_relatorio,
            fieldnames=["arquivo", "nome_curso", "qtd_insumos", "qtd_suspeitos", "status"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor_rel.writeheader()
        escritor_rel.writerows(relatorio)

    with ARQUIVO_REVISAO.open("w", encoding="utf-8-sig", newline="") as arquivo_rev:
        escritor_rev = csv.DictWriter(
            arquivo_rev,
            fieldnames=["arquivo", "nome_curso", "item_suspeito"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor_rev.writeheader()
        escritor_rev.writerows(todos_suspeitos)

    print("\n========== EXTRAÇÃO CONCLUÍDA ==========")
    print(f"Total de PDFs processados: {len(arquivos_pdf)}")
    print(f"Erros: {total_erros}")
    print(f"Total geral de insumos confirmados: {total_geral_insumos}")
    print(f"Itens na fila de revisão (zona cinzenta): {len(todos_suspeitos)}")
    print(f"\nArquivo principal: {ARQUIVO_SAIDA}")
    print(f"Arquivo de revisão: {ARQUIVO_REVISAO}")


if __name__ == "__main__":
    main()