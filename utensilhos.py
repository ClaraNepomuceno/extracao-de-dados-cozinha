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

ARQUIVO_SAIDA = PASTA_RESULTADOS / "cursos_utensilios_final_ajustado.csv"
ARQUIVO_RELATORIO = PASTA_RESULTADOS / "relatorio_extracao_utensilios.csv"
ARQUIVO_REVISAO = PASTA_RESULTADOS / "utensilios_suspeitos_revisao.csv"


# ============================================================
# 2. NORMALIZAÇÃO E SANEAMENTO
# ============================================================

CORRECOES_OCR_E_VARIACOES_UTENSILIOS = {
    "BAILHARINAS PARA CONFEITAR": "BAILARINA PARA CONFEITAR",
    "BAILHARINAS": "BAILARINA",
    "BALACA COM IMPRESSORA INTEGRADA": "BALANCA COM IMPRESSORA INTEGRADA",
    "BALACA": "BALANCA",
    "DEFUMDOR SMOKE GUN": "DEFUMADOR SMOKE GUN",
    "BOWLL": "BOWL",
    "COLHERES MEDIDORA": "COLHERES MEDIDORAS",
    "PROJETOR MULTIMIDEA": "PROJETOR MULTIMIDIA",
    "REIL GAS": "REFIL GAS",
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
        if re.search(r"[AEIOUÁÉÍÓÚÂÊÔÃÕ]{3,}", p) and not re.search(
            r"(?:QUEI|LINGUIC|AGUA|MEIA|AVEIA|AMEIXA|MANTEIGA|REQUEIJ|CEBOUL|AJOE|EUCAL|MULTIMIDIA)", p
        ):
            return True

        acentos = len(re.findall(r"[ÁÉÍÓÚÂÊÔÃÕÇ]", p))
        if acentos >= 2:
            return True

        if re.search(r"^(?:FP|PN|SX|DB|DZ|VT|NR|RT|TM|BT|CT|PT|GD|FD|MD|SD)", p):
            return True
        if re.search(r"[BCDFGHJKLMNPQRSTVWXZ]{4,}", p):
            return True

    return False


def extrair_nome_utensilio_limpo(descricao_bruta: str) -> str:
    texto = limpar_texto(descricao_bruta)
    texto = re.sub(r"^ES\d{8,}\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^\d+\s*[.)-]\s*", "", texto)
    # Remove especificações longas após dois-pontos ou hífen, preservando nomes compostos úteis
    nome = re.split(r"\s*:\s*|\s+-\s+", texto, maxsplit=1)[0]
    nome = nome.strip(" .:-;•*',")

    norm = normalizar(nome)
    if norm in CORRECOES_OCR_E_VARIACOES_UTENSILIOS:
        return CORRECOES_OCR_E_VARIACOES_UTENSILIOS[norm]

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
# 3. CLASSIFICADOR SEMÂNTICO (UTENSÍLIO/EQUIPAMENTO VS INSUMO)
# ============================================================

# Vocabulário positivo de utensílios, ferramentas, equipamentos e EPIs de cozinha/bar/salão
TERMOS_UTENSILIOS_E_EQUIPAMENTOS = {
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
    "SERRA FITA", "AMACIADOR DE BIFE", "BALANCA DIGITAL", "BALANCA", "BALACA",
    "TERMOMETRO CULINARIO", "MACARICO", "CHAMBER", "SOUS VIDE", "TERMO CIRCULADOR",
    "CAMARA DE FERMENTACAO", "DIVISORA DE MASSAS", "MASSEIRA", "MASSEIRAS",
    "MODELADORA", "PLACA DE INDUCAO", "ULTRACONGELADOR", "FRIO RAPIDO",
    "DEFUMADOR", "DEFUMDOR", "DESIDRATADORA", "INFUSOR DE FUMACA", "BOMBA DE AQUARIO",
    "ENSACADOR MANUAL", "CARRINHO COM RODAS", "GUERIDON", "PENDAL",
    # Utensílios e Ferramentas
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
    "JARRA", "TERMOMETRO", "MEDIDOR", "MEDIDORES", "MEDIDORA",
    "AZEITEIRO", "RECIPIENTE", "DISPENSADOR", "RAMEQUIN", "RAMEQUINS", "BACIA",
    "MANDUCA", "ABRIDOR", "BORRIFADOR", "CHALEIRA", "BULE", "GALHETEIRO",
    "BICO DE CONFEITAR", "BICOS PARA CONFEITAR", "ADAPTADOR", "BAILARINA",
    "BAILARINAS", "BAILHARINAS", "PINCEL CULINARIO", "ROLO DE MASSA",
    "CARRETILHA", "VAZADOR", "BOLEADOR", "DESCAROCADOR", "ESPREMEDOR", "AMASSADOR",
    "SOCADOR", "COQUETELEIRA", "DOSADOR", "MUDDLER", "PASSADOR", "CHINOIS",
    "TAMIS", "CUSCUZEIRA", "VAPOREIRA", "CHAPA", "GRELHA", "ESPETO", "GANCHO",
    "BATEDOR MANUAL", "CUTELO", "RASPADOR", "CRONOMETRO", "WOK",
    "CANECA DE COBRE", "CESTO PARA PAES", "CLOCHE", "COADOR", "STRAINER", "DECANTER",
    "GARRAFA TERMICA", "MACERADOR", "RECHAUD", "SOUSPLAT", "VACUO VINS",
    "JOGO AMERICANO", "PANO COBRE MANCHAS", "ARCO DE SERRA", "BAR CADDY",
    "CAVIAR BOX", "LICOREIRA", "MINI PITCHER", "MOLDE STENCIL", "PICOLETEIRA",
    "CUSPIDEIRA", "CHAWAM", "TACHO", "AEROPRESS", "BISTURI", "LEITEIRA",
    "VOAL", "BANCADA", "BANCADAS", "MESA", "CADEIRA", "ARMARIO",
    # EPIs e Vestuário Profissional
    "AVENTAL", "DOLMA", "TOUCA", "SAPATO", "BOTA", "JALECO", "JAPONA", "LUVA",
    "CAMISA SOCIAL", "COLETE ADULTO", "GRAVATA", "GRAVADA", "CALCA", "CAMISETA"
}

REGEX_SINAIS_UTENSILIO = re.compile(
    r"\b(?:INOX|INOXIDAVEL|ACO INOX|SILICONE|POLIETILENO|POLIPROPILENO|ALUMINIO|"
    r"VIDRO TEMPERADO|CERAMICA|PORCELANA|LOUCA|MADEIRA|BAMBU|TEFLON|ANTIADERENTE|"
    r"ACRILICO|NYLON|COBRE|110V|220V|127V|BIVOLT|WATTS|POLEGADAS|MALHA FINA|"
    r"CABO BRANCO|CABO PRETO|CABO VERMELHO|CABO VERDE|CABO AZUL|CABO AMARELO|"
    r"PANELA|FRIGIDEIRA|FACA|COLHER|GARFO|PRATO|COPO|TACA|XICARA|FORMA|ASSADEIRA|"
    r"TABUA|ESPATULA|CONCHA|PENEIRA|RALADOR|BATEDOR|FOUET|PEGADOR|PINCA|TRAVESSA|"
    r"TIGELA|BOWL|BACIA|JARRA|BALANCA|TERMOMETRO|MEDIDOR|MEDIDORA|CORTADOR|ROLO|"
    r"FORNO|FOGAO|LIQUIDIFICADOR|BATEDEIRA|PROCESSADOR|MIXER|FREEZER|REFRIGERADOR|"
    r"GELADEIRA|BANCADA|BANCADAS|COADOR|FUNIL|CRONOMETRO|CUTELO|RASPADOR)\b"
)

# Bloqueia alimentos/ingredientes e itens de limpeza/escritório para não contaminarem os utensílios
REGEX_BLOQUEIO_ALIMENTOS = re.compile(
    r"\b(?:ACUCAR|SAL|OLEO|AZEITE|FARINHA|FERMENTO|BICARBONATO|LEITE|MANTEIGA|"
    r"MARGARINA|CREME DE LEITE|NATA|QUEIJO|MOZZARELLA|MUCARELA|BURRATA|RICOTA|"
    r"CHEDDAR|REQUEIJAO|CATUPIRY|PARMESAO|OVO|OVOS|CARNE|FRANGO|PEIXE|CAMARAO|"
    r"BACON|GUANCIALE|PANCETTA|LINGUICA|PRESUNTO|CHARQUE|ALCATRA|PATINHO|FILE|"
    r"MIGNON|CONTRAFILE|COSTELA|COSTELINHA|LOMBO|PERNIL|BISTECA|CUPIM|MUSCULO|"
    r"ACEM|PICANHA|MAMINHA|FRALDINHA|COXAO|LAGARTO|DIAFRAGMA|MAGRET|PERU|ROBALO|"
    r"TILAPIA|PESCADA|SARDINHA|ATUM|BACALHAU|POLVO|LULA|MEXILHAO|ARROZ|FEIJAO|"
    r"MACARRAO|SPAGHETTI|FUBA|AMIDO|POLVILHO|AVEIA|TRIGO|MILHO|CANJICA|CUSCUZ|"
    r"SOJA|TOFU|LENTILHA|QUINOA|TOMATE|CEBOLA|ALHO|BATATA|CENOURA|BETERRABA|"
    r"ABOBORA|ABOBRINHA|MANDIOCA|AIPIM|INHAME|PIMENTAO|ALFACE|COUVE|REPOLHO|"
    r"ESPINAFRE|RUCULA|AGRIAO|CHICORIA|BROCOLIS|BERINJELA|CHUCHU|QUIABO|VAGEM|"
    r"PEPINO|RABANETE|ASPARGO|COENTRO|SALSA|SALSINHA|CEBOLINHA|HORTELA|MANJERICAO|"
    r"ALFAVACA|ALECRIM|TOMILHO|OREGANO|LOURO|CANELA|CRAVO|PIMENTA|COMINHO|CURCUMA|"
    r"COLORAU|PAPRICA|GENGIBRE|BAUNILHA|ESSENCIA|CORANTE|BANANA|MACA|LARANJA|LIMAO|"
    r"ABACAXI|MAMAO|MANGA|MORANGO|UVA|MARACUJA|COCO|MELANCIA|MELAO|ABACATE|AVOCADO|"
    r"GOIABA|GOIABADA|PESSEGO|AMEIXA|CAJU|ACEROLA|TANGERINA|KIWI|CEREJA|FRAMBOESA|"
    r"AMORA|MIRTILO|PEQUI|POLPA|CHOCOLATE|CACAU|MEL|GLICOSE|GELATINA|CHANTILLY|"
    r"DOCE DE LEITE|LEITE CONDENSADO|BOMBOM|GRANULADO|SORVETE|VINAGRE|ACETO|SHOYU|"
    r"MOSTARDA|KETCHUP|MAIONESE|MOLHO|AZEITONA|ALCAPARRA|CHAMPIGNON|COGUMELO|"
    r"PALMITO|ERVILHA|VINHO|ESPUMANTE|CERVEJA|CACHACA|RUM|CONHAQUE|LICOR|APEROL|"
    r"BITTER|TEQUILA|VERMOUTH|VODKA|WHISKY|XAROPE|SUCO|CAFE|CHA|PAO|BISCOITO|"
    r"CASTANHA|NOZES|AMENDOA|AMENDOIM|AVELA|PISTACHE|CURRY|IN NATURA|CONGELAD[OA]|"
    r"RESFRIAD[OA]|EXTRA VIRGEM|REFINAD[OA]|CRISTAL|DEMERARA|COMESTIVEL)\b"
)

ITENS_LIMPEZA_ESCRITORIO_DESCARTAVEIS = {
    "FIBRA SINTETICA", "FIBRACO", "FOSFORO", "HIPOCLORITO", "MASCARA",
    "PANO MULTIUSO", "PANO DE PRATO", "PANO PARA LIMPEZA", "PAPEL ALUMINIO",
    "POTE COM TAMPA", "SACO PLASTICO", "SACO DE LIXO", "SABONETE",
    "BANDEJA", "APAGADOR", "PAPEL A4", "SULFITE", "ALCOOL", "ALCOOL ETILICO",
    "AGUA SANITARIA", "PAPEL TOALHA", "ESCOVA DE LIMPEZA", "ESCOVA PARA LIMPEZA",
    "ESPONJA", "DETERGENTE", "DESINFETANTE", "VASSOURA", "RODO", "LIXEIRA",
    "FILME PVC", "PAPEL MANTEIGA", "GUARDANAPO", "PALITO DE BAMBU",
    "PALITO DE DENTE", "ALGODAO", "BOBINA", "SACO DE CONFEITAR", "CERTIFICADO",
    "ETIQUETA ADESIVA", "ETIQUETA", "MARMITEX", "EMBALAGEM", "CAIXA DE PAPELAO",
    "BARBANTE", "ISQUEIRO", "CANETA", "LAPIS", "BORRACHA", "GRAMPEADOR",
    "PRANCHETA", "PASTA", "CADERNO", "ESTOJO PERSONALIZADO", "FILTRO DE PAPEL",
    "FILTRO KALITA", "CANUDO", "ISOPOR", "TOPO DE BOLO", "PISTILO PARA ARTESANATO",
    "AMPOLAS", "REFIL GAS", "CARTEIRA UNIVERSITARIA", "SOFTWARE"
}

CABECALHOS_E_SECOES = {
    "CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO DETALHADA", "DESCRICAO",
    "ESPECIFICACAO", "U.M", "QUANTIDADE POR ALUNO", "QUANTIDADE POR TURMA",
    "VALOR UNITARIO", "VALOR TOTAL", "TOTAL", "PESO", "APROXIMADO DE",
    "TIPO DE FINANCIAMENTO", "INSUMOS", "EQUIPAMENTOS", "UTENSILIOS",
    "EQUIPAMENTOS E UTENSILIOS", "MATERIAIS", "MIDIA ESPECIALIZADA",
    "BANCO DE PRECOS", "ESTIMATIVA", "UNIFORMES", "MODO DE PREPARO",
    "INFRAESTRUTURA E LISTA BASICA1", "INFRAESTRUTURA E LISTA BASICA",
    "INDICADORES", "LISTA BASICA", "DADOS DA LISTA BASICA", "DADOS DO CURSO",
    "QUALIFICACAO PROFISSIONAL", "ULTIMA REVISAO", "UNIFORME",
    "DESCRICAO DO INGREDIENTE", "ITEM", "QUANTIDADE", "MEDIDA", "CATEGORIA",
    "NAO SE APLICA", "SENAC", "UNIDADE", "PACOTE", "CAIXA", "LATA", "VIDRO",
    "GARRAFA", "MACO", "RESMA", "FARDO", "POTE", "ROLO", "QTD TOTAL DE ALUNOS",
    "RESPONSAVEL- ELABORACAO", "RESPONSAVEL ELABORACAO", "DATA DE ELABORACAO",
    "RESPONSAVEL", "RESPONSAVEL - REVISAO", "SEGMENTO", "CARGA HORARIA", "TIPO",
    "CODIGO SIG", "AULAS PLANEJADAS", "PLANEJAMENTO DAS AULAS",
    "LANCAMENTO NO SEI", "PRODUCAO DE ALIMENTOS", "PROGRAMA SOCIOPROFISSIONAL",
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


def classificar_item_utensilio(titulo_item: str, vocabulario_alimentos: set[str]) -> str:
    if texto_corrompido_cid_ou_sobreposto(titulo_item):
        return "DESCARTAR"

    desc_upper = normalizar(titulo_item)

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

    # 1. Bloqueio de ingredientes (receitas e radicais alimentícios)
    if desc_upper in vocabulario_alimentos or REGEX_BLOQUEIO_ALIMENTOS.search(desc_upper):
        return "DESCARTAR"

    # 2. Bloqueio de limpeza, descartáveis e papelaria
    palavras_titulo = set(re.findall(r"[A-Z0-9-]+", desc_upper))
    for termo_lixo in ITENS_LIMPEZA_ESCRITORIO_DESCARTAVEIS:
        if " " in termo_lixo:
            if re.search(rf"\b{re.escape(termo_lixo)}\b", desc_upper):
                return "DESCARTAR"
        else:
            if termo_lixo in palavras_titulo:
                return "DESCARTAR"

    # 3. Confirmação positiva: vocabulário de utensílios/equipamentos/EPIs ou material técnico
    for termo_ut in TERMOS_UTENSILIOS_E_EQUIPAMENTOS:
        if " " in termo_ut:
            if re.search(rf"\b{re.escape(termo_ut)}\b", desc_upper):
                return "UTENSILIO_CONFIRMADO"
        else:
            if termo_ut in palavras_titulo:
                return "UTENSILIO_CONFIRMADO"

    if REGEX_SINAIS_UTENSILIO.search(desc_upper):
        return "UTENSILIO_CONFIRMADO"

    # 4. Zona cinzenta
    return "SUSPEITO"


# ============================================================
# 4. EXTRAÇÃO DAS TABELAS E FICHAS TÉCNICAS
# ============================================================

def tabela_e_de_metadados_ou_cronograma(tabela: list[list[str]]) -> bool:
    texto_inteiro = normalizar(" ".join(
        limpar_texto(c) for linha in tabela for c in (linha or []) if c
    ))
    if any(k in texto_inteiro for k in ("CODIGO ITEM MXM", "QUANTIDADE POR TURMA", "U.M", "VALOR UNITARIO")):
        return False

    amostra = normalizar(" ".join(
        limpar_texto(c) for linha in tabela[:4] for c in (linha or []) if c
    ))
    marcadores_nao_lista = [
        "QTD TOTAL DE ALUNOS", "DADOS DO CURSO", "PLANEJAMENTO DAS AULAS",
        "AULAS PLANEJADAS", "MODO DE PREPARO", "ELEMENTOS DA COMPETENCIA",
        "ORGANIZACAO CURRICULAR", "BIBLIOGRAFIA", "SITUACAO DE APRENDIZAGEM",
        "DESCRICAO DO INGREDIENTE"
    ]
    return any(m in amostra for m in marcadores_nao_lista)


def linha_parece_item_lista_basica(valores: list[str]) -> bool:
    texto_completo = normalizar(" ".join(v for v in valores if v))
    marcadores_lista_basica = (
        r"\b(?:KG|UNIDADE|UNI|UN|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
        r"LITRO|LT|PECA|PC|BANDEJA|JOGO|JG|KIT|CONJUNTO|CJ|PAR|METRO|MT|"
        r"NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|BANCO DE PRECOS)\b|R\$|ES0"
    )
    return bool(re.search(marcadores_lista_basica, texto_completo))


def extrair_melhor_candidato_descricao(valores: list[str]) -> str:
    ignorados = CABECALHOS_E_SECOES | {
        "NAO SE APLICA", "SENAC", "MIDIA ESPECIALIZADA", "BANCO DE PRECOS", "ESTIMATIVA",
        "KG", "UNI", "UN", "PCT", "MC", "CX", "RL", "LITRO", "LT", "JOGO", "JG", "KIT",
        "CONJUNTO", "CJ", "PAR", "PECA", "PC", "METRO", "MT"
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
        r"\b(?:KG|UNIDADE|UNI|UN|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
        r"LITRO|LT|PECA INTEIRA|PECA|PC|BANDEJA|JOGO|JG|KIT|CONJUNTO|CJ|PAR|METRO|MT|"
        r"NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|BANCO DE PRECOS)\b|R\$"
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


def construir_vocabulario_alimentos_receitas(arquivos_pdf: list[Path]) -> set[str]:
    """Passada 1: mapeia ingredientes das fichas técnicas para excluí-los da extração de utensílios."""
    vocabulario = set()
    total = len(arquivos_pdf)
    print(f"Passada 1/2: Mapeando vocabulário de alimentos para bloqueio cruzado em {total} PDFs...")

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
                                nome = normalizar(extrair_nome_utensilio_limpo(m.group(1)))
                                if len(nome) >= 2 and nome not in CABECALHOS_E_SECOES:
                                    vocabulario.add(nome)
        except Exception:
            pass

        if idx % 10 == 0 or idx == total:
            print(f"  -> Vocabulário de bloqueio mapeado: {idx}/{total} arquivos...")

    print(f"Vocabulário de alimentos mapeado com {len(vocabulario)} itens.\n")
    return vocabulario


def extrair_utensilios_pdf(
    pdf, nome_curso: str, vocabulario_alimentos: set[str]
) -> tuple[list[str], list[str], bool]:
    utensilios = []
    suspeitos = []
    nome_curso_norm = normalizar(nome_curso)
    na_lista_basica = False
    tem_cid = False

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text() or ""
        if "(cid:" in texto_pag.lower():
            tem_cid = True

        texto_pag_norm = normalizar(texto_pag)

        # 1. Detecta entrada na Lista Básica (Equipamentos, Utensílios, Uniformes)
        if (
            "LISTA BASICA" in texto_pag_norm
            or ("DADOS DA LISTA" in texto_pag_norm and "BASICA" in texto_pag_norm)
            or any(sec in texto_pag_norm for sec in ("EQUIPAMENTOS", "UTENSILIOS", "UNIFORMES", "INFRAESTRUTURA"))
        ):
            na_lista_basica = True

        if not na_lista_basica:
            continue

        # 2. Encerra quando inicia o bloco exclusivo de INSUMOS (sem equipamentos/utensílios na página)
        linhas_pag = [normalizar(l) for l in texto_pag.splitlines()]
        if "INSUMOS" in linhas_pag and not any(
            sec in texto_pag_norm for sec in ("EQUIPAMENTOS", "UTENSILIOS", "UNIFORMES")
        ):
            break

        # 3. Encerra se iniciar seção de receitas/fichas técnicas após a Lista Básica
        if any(
            marc in texto_pag_norm
            for marc in (
                "DESCRICAO DO INGREDIENTE",
                "FICHA TECNICA DE PRODUCAO",
                "MODO DE PREPARO",
            )
        ):
            break

        for tabela in pagina.extract_tables():
            if not tabela or tabela_e_de_metadados_ou_cronograma(tabela):
                continue

            linhas_tratadas = consolidar_linhas_quebradas_tabela(tabela)

            for valores in linhas_tratadas:
                texto_linha_norm = normalizar(" ".join(v for v in valores if v))
                if any(h in texto_linha_norm for h in ("CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO")):
                    continue

                if not linha_parece_item_lista_basica(valores):
                    continue

                candidato = extrair_melhor_candidato_descricao(valores)
                nome_utensilio = extrair_nome_utensilio_limpo(candidato)

                if not nome_utensilio or normalizar(nome_utensilio) == nome_curso_norm:
                    continue

                status_item = classificar_item_utensilio(nome_utensilio, vocabulario_alimentos)

                if status_item == "UTENSILIO_CONFIRMADO":
                    if not any(normalizar(x) == normalizar(nome_utensilio) for x in utensilios):
                        utensilios.append(nome_utensilio)
                elif status_item == "SUSPEITO":
                    if not any(normalizar(x) == normalizar(nome_utensilio) for x in suspeitos):
                        suspeitos.append(nome_utensilio)

    return utensilios, suspeitos, tem_cid


# ============================================================
# 5. FLUXO PRINCIPAL
# ============================================================

def main():
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    arquivos_pdf = sorted(PASTA_PDFS.rglob("*.pdf"))

    if not arquivos_pdf:
        print(f"Nenhum PDF encontrado em: {PASTA_PDFS}")
        return

    vocabulario_alimentos = construir_vocabulario_alimentos_receitas(arquivos_pdf)

    total_erros = 0
    total_geral_utensilios = 0
    relatorio = []
    todos_suspeitos = []

    print("Passada 2/2: Extraindo e classificando utensílios e equipamentos de todos os cursos...")

    with ARQUIVO_SAIDA.open("w", encoding="utf-8-sig", newline="") as arquivo_saida:
        escritor = csv.DictWriter(
            arquivo_saida,
            fieldnames=["nome_curso", "utensilio"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor.writeheader()

        for indice, caminho_pdf in enumerate(arquivos_pdf, start=1):
            try:
                with pdfplumber.open(caminho_pdf) as pdf:
                    nome_curso = extrair_nome_curso(pdf, caminho_pdf)
                    utensilios, suspeitos, tem_cid = extrair_utensilios_pdf(
                        pdf, nome_curso, vocabulario_alimentos
                    )

                for utensilio in utensilios:
                    escritor.writerow({
                        "nome_curso": nome_curso,
                        "utensilio": utensilio
                    })

                for susp in suspeitos:
                    todos_suspeitos.append({
                        "arquivo": caminho_pdf.name,
                        "nome_curso": nome_curso,
                        "item_suspeito": susp
                    })

                qtd_utensilios = len(utensilios)
                total_geral_utensilios += qtd_utensilios

                if qtd_utensilios > 0:
                    status = "OK"
                elif tem_cid:
                    status = "FONTE CORROMPIDA (CID) - REQUER OCR"
                else:
                    status = "SEM UTENSILIOS"

                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": nome_curso,
                    "qtd_utensilios": qtd_utensilios,
                    "qtd_suspeitos": len(suspeitos),
                    "status": status
                })

                print(
                    f"[{indice}/{len(arquivos_pdf)}] {nome_curso} | "
                    f"Utensílios: {qtd_utensilios} | Suspeitos: {len(suspeitos)} ({status})"
                )

            except Exception as erro:
                total_erros += 1
                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": "",
                    "qtd_utensilios": 0,
                    "qtd_suspeitos": 0,
                    "status": f"ERRO: {erro}"
                })
                print(f"ERRO ao processar {caminho_pdf.name}: {erro}")

    with ARQUIVO_RELATORIO.open("w", encoding="utf-8-sig", newline="") as arquivo_relatorio:
        escritor_rel = csv.DictWriter(
            arquivo_relatorio,
            fieldnames=["arquivo", "nome_curso", "qtd_utensilios", "qtd_suspeitos", "status"],
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

    print("\n========== EXTRAÇÃO DE UTENSÍLIOS CONCLUÍDA ==========")
    print(f"Total de PDFs processados: {len(arquivos_pdf)}")
    print(f"Erros: {total_erros}")
    print(f"Total geral de utensílios/equipamentos confirmados: {total_geral_utensilios}")
    print(f"Itens na fila de revisão (zona cinzenta): {len(todos_suspeitos)}")
    print(f"\nArquivo principal: {ARQUIVO_SAIDA}")
    print(f"Arquivo de revisão: {ARQUIVO_REVISAO}")


if __name__ == "__main__":
    main()