import csv
import re
import unicodedata
from itertools import zip_longest
from pathlib import Path
import pdfplumber

# ============================================================
# 1. CONFIGURAÇÕES
# ============================================================

BASE = Path(__file__).resolve().parent

PASTA_PDFS = BASE / "OneDrive_2026-10-28" / "Dados para ETL - Cozinha"
PASTA_RESULTADOS = BASE / "resultados"

ARQUIVO_SAIDA = PASTA_RESULTADOS / "cursos_insumos_utensilios_unificado.csv"
ARQUIVO_RELATORIO = PASTA_RESULTADOS / "relatorio_extracao_unificado.csv"
ARQUIVO_REVISAO = PASTA_RESULTADOS / "itens_suspeitos_revisao_unificado.csv"


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
    "GRAVADA ESTILO CLASSICA": "GRAVATA ESTILO CLASSICA",
}

CORRECOES_OCR_E_VARIACOES_INSUMOS = {
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
    "VINHO TINTO CARBENET SAUVIGNON": "VINHO TINTO CABERNET SAUVIGNON",
    "BATAJA DOCE": "BATATA DOCE",
    "QURIO COALHO": "QUEIJO COALHO",
    "MAO TAITE": "LIMAO TAITI",
    "TOMAJE CEREJA": "TOMATE CEREJA",
    "FARINHA DE TRIGO TIPO \"00\"": "FARINHA DE TRIGO TIPO 00",
    "FARINHA DE TRIGO TIPO '00'": "FARINHA DE TRIGO TIPO 00",
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip(" :;-',.").upper()


def limpar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def texto_corrompido_cid_utensilios(texto: str) -> bool:
    if not texto:
        return True
    low = texto.lower()
    if "(cid:" in low or "(cid" in low:
        return True

    palavras = re.findall(r"[A-ZÀ-Ú]{5,}", texto.upper())
    for p in palavras:
        if re.search(r"[AEIOUÁÉÍÓÚÂÊÔÃÕ]{3,}", p) and not re.search(
            r"(?:QUEI|LINGUIC|AGUA|MEIA|AVEIA|AMEIXA|MANTEIGA|REQUEIJ|CEBOUL|AJOE|EUCAL|MULTIMIDIA|BOUILL)", p
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


def texto_corrompido_cid_insumos(texto: str) -> bool:
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
        # Detecta consoantes impossíveis típicas de OCR corrompido (ex: S000000, DALZADA, etc.)
        if re.search(r"[BCDFGHJKLMNPQRSTVWXZ]{5,}", p):
            return True
    return False


def extrair_nome_utensilio_limpo(descricao_bruta: str) -> str:
    texto = limpar_texto(descricao_bruta)
    texto = re.sub(r"^(?:ES|E5|S0|10)\d{6,}\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^\d+\s*[.)-]\s*", "", texto)
    nome = re.split(r"\s*:\s*|\s+-\s+", texto, maxsplit=1)[0]
    nome = nome.strip(" .:-;•*',\"")

    norm = normalizar(nome)
    if norm in CORRECOES_OCR_E_VARIACOES_UTENSILIOS:
        return CORRECOES_OCR_E_VARIACOES_UTENSILIOS[norm]

    return nome


def extrair_nome_insumo_limpo(descricao_bruta: str) -> str:
    texto = limpar_texto(descricao_bruta)
    texto = re.sub(r"^(?:ES|E5|S0|10)\d{6,}\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^\d+\s*[.)-]\s*", "", texto)
    texto = re.sub(r"\s+\d+(?:[.,]\d+)?\s*(?:ML|G|GR|KG|L|UNI|UNID|UNIDADE|M|MT|METRO|PCT|MC|CX)\b.*$", "", texto, flags=re.IGNORECASE)
    nome = re.split(r"\s*:\s*|\s+-\s+", texto, maxsplit=1)[0]
    nome = nome.strip(" .:-;•*',\"")

    norm = normalizar(nome)
    if norm in CORRECOES_OCR_E_VARIACOES_INSUMOS:
        return CORRECOES_OCR_E_VARIACOES_INSUMOS[norm]

    return nome


def extrair_nome_curso(pdf, caminho_pdf: Path) -> str:
    """Extrai o nome oficial do curso da Capa, Identificação do Curso ou cabeçalho da Lista Básica."""
    # 1ª tentativa: Capa e Seção 1 (Identificação do Curso) nas 5 primeiras páginas
    for pagina in pdf.pages[:5]:
        texto = pagina.extract_text() or ""
        if "(cid:" in texto.lower():
            continue

        # Padrão Capa: "Nome do Curso: Vera Pizza Napoletana - Curso Básico"
        m_capa = re.search(
            r"(?:Nome|T[íi]tulo)\s+do\s+Curso\s*:\s*(.+?)(?=\n|Eixo\s+Tecnol[óo]gico|Segmento|Modalidade|Carga\s+Hor[áa]ria|$)",
            texto,
            flags=re.IGNORECASE,
        )
        if m_capa:
            nome = limpar_texto(m_capa.group(1)).strip(" :;-")
            # Remove sufixos internos de turno/modalidade se existirem (ex: TEM / NEM)
            nome = re.sub(r"\s+(?:TEM|NEM)\b$", "", nome).strip(" :;-")
            if len(nome) >= 4 and normalizar(nome) not in {"CURSO", "PLANO DE CURSO"}:
                return nome

    # 2ª tentativa: Tabelas e cabeçalhos internos de Lista Básica em todo o documento
    for pagina in pdf.pages[:60]:
        for tabela in pagina.extract_tables() or []:
            for linha in tabela:
                if not linha:
                    continue
                celulas = [limpar_texto(c) for c in linha if c]
                for idx, cel in enumerate(celulas):
                    if normalizar(cel) in {"CURSO", "CURSO:"} and idx + 1 < len(celulas):
                        candidato = celulas[idx + 1]
                        candidato = re.sub(r"\s+(?:TEM|NEM)\b$", "", candidato).strip(" :;-")
                        if candidato and normalizar(candidato) not in {"QTD TOTAL DE ALUNOS", "SEGMENTO"}:
                            return candidato

        texto = pagina.extract_text() or ""
        if "(cid:" in texto.lower():
            continue

        m1 = re.search(
            r"CURSO\s*:\s*(.+?)(?=\s*(?:QTD\s+TOTAL|SEGMENTO|CARGA\s+HOR[ÁA]RIA|TIPO\s*:|C[ÓO]DIGO\s+SIG|\n))",
            texto,
            flags=re.IGNORECASE,
        )
        if m1:
            nome = limpar_texto(m1.group(1))
            nome = re.sub(r"\s+(?:TEM|NEM)\b$", "", nome).strip(" :;-")
            if nome and normalizar(nome) not in {"CURSO", "QTD TOTAL DE ALUNOS"}:
                return nome

    return limpar_texto(caminho_pdf.stem.replace("-", " "))


# ============================================================
# 3. CLASSIFICADORES SEMÂNTICOS (UTENSÍLIOS E INSUMOS)
# ============================================================

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
    "ENSACADOR MANUAL", "CARRINHO COM RODAS", "GUERIDON", "PENDAL", "MAQUINA DE GELO",
    "MAQUINA DE CAFE",
    # Utensílios, Ferramentas e Serviço de Salão/Bar
    "PINCA", "PINCAS", "PEGADOR", "PEGADORES", "ROLO LAMINADOR", "CORTADOR", "CORTADORES",
    "ARO", "AROS", "PIRES", "PLACA DE CORTE", "PLACAS DE ETILENO", "PORTA CONDIMENTO",
    "POTE HERMETICO", "POTE BISNAGA", "BISNAGA", "RALADOR", "ZESTER",
    "SERINGA", "SIFAO", "GARRAFA SIFAO", "SPEED RAIL", "STOREN POUR", "STORE AND POUR",
    "SUPORTE PARA PLACAS", "SUPORTE DE PAS", "SUPORTE PARA FILTRO",
    "TAPETE DE SILICONE", "SERVICE MAT", "BAR MAT",
    "TESOURA", "TRAVESSA", "TRAVESSAS", "BOWL", "BOWLS", "BOWLL",
    "CAIXA PLASTICA", "CAIXA TERMICA", "CONTENTOR", "CHAIRA", "DESCASCADOR",
    "ESCUMADEIRA", "FOUET", "FUNIL", "MANDOLINE", "MANDOLIN", "MOEDOR",
    "PEDRA DE AFIAR", "PEDRA PARA AMOLAR", "ESPATULA", "PA PARA",
    "GRADE", "FORMA", "FORMAS", "TABUA", "TABUAS", "FACA", "FACAS", "BARRA MAGNETICA",
    "PANELA", "PANELAS", "FRIGIDEIRA", "CALDEIRAO", "ASSADEIRA", "TIGELA", "CUBA", "CUBAS",
    "CONCHA", "ESCORREDOR", "PENEIRA", "COLHER", "COLHERES", "GARFO", "GARFOS",
    "PRATO", "PRATOS", "COPO", "COPOS", "XICARA", "XICARAS", "TACA", "TACAS", "CALICE",
    "JARRA", "TERMOMETRO", "MEDIDOR", "MEDIDORES", "MEDIDORA",
    "AZEITEIRO", "RECIPIENTE", "DISPENSADOR", "RAMEQUIN", "RAMEQUINS", "BACIA",
    "MANDUCA", "ABRIDOR", "SACA ROLHAS", "BORRIFADOR", "CHALEIRA", "BULE", "GALHETEIRO",
    "BICO DE CONFEITAR", "BICOS PARA CONFEITAR", "BICO DOSADOR", "BIQUEIRA",
    "ADAPTADOR", "BAILARINA", "BAILARINAS", "BAILHARINAS", "PINCEL CULINARIO",
    "ROLO DE MASSA", "CARRETILHA", "VAZADOR", "BOLEADOR", "DESCAROCADOR",
    "ESPREMEDOR", "AMASSADOR", "SOCADOR", "COQUETELEIRA", "DOSADOR", "JIGGER",
    "MUDDLER", "PASSADOR", "CHINOIS", "TAMIS", "CUSCUZEIRA", "VAPOREIRA",
    "CHAPA", "GRELHA", "ESPETO", "GANCHO", "BATEDOR MANUAL", "CUTELO",
    "RASPADOR", "CRONOMETRO", "WOK", "CANECA DE COBRE", "CESTO PARA PAES",
    "CLOCHE", "COADOR", "STRAINER", "DECANTER", "GARRAFA TERMICA", "MACERADOR",
    "RECHAUD", "SOUSPLAT", "VACUO VINS", "JOGO AMERICANO", "PANO COBRE MANCHAS",
    "ARCO DE SERRA", "BAR CADDY", "CAVIAR BOX", "LICOREIRA", "MINI PITCHER",
    "MOLDE STENCIL", "PICOLETEIRA", "CUSPIDEIRA", "CHAWAM", "TACHO", "AEROPRESS",
    "BISTURI", "LEITEIRA", "VOAL", "BANCADA", "BANCADAS", "MESA", "CADEIRA", "ARMARIO",
    "ACUCAREIRO", "ANEL PARA GUARDANAPO", "BALDE DE GELO", "INFUSOR DE CHA",
    "POLVILHADOR", "PORTA GUARDANAPO", "TOALHA DE MESA", "TOALHA MESA",
    "GUARDANAPO DE PANO", "GUARDANAPO DE VINHO",
    # EPIs e Vestuário Profissional
    "AVENTAL", "DOLMA", "TOUCA", "SAPATO", "BOTA", "JALECO", "JAPONA", "LUVA",
    "CAMISA SOCIAL", "COLETE ADULTO", "GRAVATA", "GRAVADA", "CALCA", "CAMISETA"
}

REGEX_SINAIS_UTENSILIO = re.compile(
    r"\b(?:INOX|INOXIDAVEL|ACO INOX|SILICONE|POLIETILENO|POLIPROPILENO|ALUMINIO|"
    r"VIDRO TEMPERADO|CERAMICA|PORCELANA|LOUCA|MADEIRA|BAMBU|TEFLON|ANTIADERENTE|"
    r"ACRILICO|NYLON|COBRE|110V|220V|127V|BIVOLT|WATTS|POLEGADAS|MALHA FINA|"
    r"CABO BRANCO|CABO PRETO|CABO VERMELHO|CABO VERDE|CABO AZUL|CABO AMARELO|"
    r"PANELA|FRIGIDEIRA|FACA|COLHER|GARFO|PRATO|COPO|TACA|CALICE|XICARA|FORMA|ASSADEIRA|"
    r"TABUA|ESPATULA|CONCHA|PENEIRA|RALADOR|BATEDOR|FOUET|PEGADOR|PINCA|TRAVESSA|"
    r"TIGELA|BOWL|BACIA|JARRA|BALANCA|TERMOMETRO|MEDIDOR|MEDIDORA|CORTADOR|ROLO|"
    r"FORNO|FOGAO|LIQUIDIFICADOR|BATEDEIRA|PROCESSADOR|MIXER|FREEZER|REFRIGERADOR|"
    r"GELADEIRA|BANCADA|BANCADAS|COADOR|FUNIL|CRONOMETRO|CUTELO|RASPADOR|BULE|BALDE)\b"
)

REGEX_BLOQUEIO_ALIMENTOS = re.compile(
    r"\b(?:ACUCAR|SAL|OLEO|AZEITE|FARINHA|FERMENTO|BICARBONATO|MANTEIGA|"
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
    r"COLORAU|PAPRICA|GENGIBRE|BAUNILHA|ESSENCIA|CORANTE|BANANA|MACA|LARANJA|"
    r"ABACAXI|MAMAO|MANGA|MORANGO|UVA|MARACUJA|COCO|MELANCIA|MELAO|ABACATE|AVOCADO|"
    r"GOIABA|GOIABADA|PESSEGO|AMEIXA|CAJU|ACEROLA|TANGERINA|KIWI|CEREJA|FRAMBOESA|"
    r"AMORA|MIRTILO|PEQUI|POLPA|CHOCOLATE|CACAU|MEL|GLICOSE|GELATINA|"
    r"DOCE DE LEITE|LEITE CONDENSADO|BOMBOM|GRANULADO|SORVETE|VINAGRE|ACETO|SHOYU|"
    r"MOSTARDA|KETCHUP|MAIONESE|MOLHO|AZEITONA|ALCAPARRA|CHAMPIGNON|COGUMELO|"
    r"PALMITO|ERVILHA|ESPUMANTE|CERVEJA|CACHACA|RUM|CONHAQUE|APEROL|"
    r"BITTER|TEQUILA|VERMOUTH|VODKA|WHISKY|XAROPE|SUCO|BISCOITO|"
    r"CASTANHA|NOZES|AMENDOA|AMENDOIM|AVELA|PISTACHE|CURRY|IN NATURA|CONGELAD[OA]|"
    r"RESFRIAD[OA]|EXTRA VIRGEM|REFINAD[OA]|CRISTAL|DEMERARA|COMESTIVEL)\b"
)

ITENS_LIMPEZA_ESCRITORIO_DESCARTAVEIS = {
    "FIBRA SINTETICA", "FIBRACO", "FOSFORO", "HIPOCLORITO", "MASCARA",
    "PANO MULTIUSO", "PANO DE PRATO", "PANO PARA LIMPEZA", "PAPEL ALUMINIO",
    "POTE COM TAMPA", "SACO PLASTICO", "SACO DE LIXO", "SABONETE",
    "APAGADOR", "PAPEL A4", "SULFITE", "ALCOOL", "ALCOOL ETILICO",
    "AGUA SANITARIA", "PAPEL TOALHA", "ESCOVA DE LIMPEZA", "ESCOVA PARA LIMPEZA",
    "ESPONJA", "DETERGENTE", "DESINFETANTE", "VASSOURA", "RODO", "LIXEIRA",
    "FILME PVC", "PAPEL MANTEIGA", "GUARDANAPO DE PAPEL", "PALITO DE BAMBU",
    "PALITO DE DENTE", "ALGODAO", "BOBINA", "SACO DE CONFEITAR", "CERTIFICADO",
    "ETIQUETA ADESIVA", "ETIQUETA", "MARMITEX", "EMBALAGEM", "CAIXA DE PAPELAO",
    "BARBANTE", "ISQUEIRO", "CANETA", "LAPIS", "BORRACHA", "GRAMPEADOR",
    "PRANCHETA", "PASTA", "CADERNO", "ESTOJO PERSONALIZADO", "FILTRO DE PAPEL",
    "FILTRO KALITA", "CANUDO", "ISOPOR", "TOPO DE BOLO", "PISTILO PARA ARTESANATO",
    "AMPOLAS", "REFIL GAS", "CARTEIRA UNIVERSITARIA", "SOFTWARE", "TOUCA DE REDE",
    "LENHA", "LENHA PARA FORNO", "PINCEL P/QUADRO", "QUADRO BRANCO", "APAGADOR PARA QUADRO"
}

TERMOS_PROIBIDOS_INSUMOS = TERMOS_UTENSILIOS_E_EQUIPAMENTOS | ITENS_LIMPEZA_ESCRITORIO_DESCARTAVEIS | {
    "PINCEL", "EQUIPAMENTO", "UTENSILIO", "GUARDANAPO", "BANDEJA", "TOUCA"
}

REGEX_MATERIAIS_E_MEDIDAS_UTENSILIO = re.compile(
    r"\b(?:INOX|INOXIDAVEL|ACO INOX|SILICONE|POLIETILENO|POLIPROPILENO|ALUMINIO|"
    r"VIDRO TEMPERADO|CERAMICA|PORCELANA|LOUCA|MADEIRA|BAMBU|PLASTICO|PVC|TEFLON|"
    r"ANTIADERENTE|ACRILICO|NYLON|COBRE|110V|220V|127V|BIVOLT|WATTS|CM|MM|POLEGADAS|"
    r"MALHA FINA|CABO BRANCO|CABO PRETO|CABO VERMELHO|CABO VERDE|CABO AZUL|"
    r"CABO AMARELO|DESCARTAVEL|OCUPACIONAL|ISOPOR|ARTESANATO|QUADRO BRANCO)\b"
)

REGEX_SINAIS_ALIMENTO = re.compile(
    r"\b(?:ACUCAR|SAL|OLEO|AZEITE|FARINHA|SEMOLA|SEMOLINA|FERMENTO|BICARBONATO|BICABORNATO|LEITE|"
    r"MANTEIGA|MARGARINA|CREME DE LEITE|NATA|QUEIJO|QUEJO|MOZZARELLA|MUCARELA|"
    r"FIOR DI LATTE|BURRATA|RICOTA|CHEDDAR|REQUEIJAO|CATUPIRY|PARMESAO|GRANA PADANO|PECORINO|"
    r"GORGONZOLA|PROVOLONE|COALHO|PROVONE|"
    r"OVO|OVOS|CARNE|FRANGO|PEIXE|CAMARAO|BACON|GUANCIALE|PANCETTA|LINGUICA|PRESUNTO|"
    r"PASTRAMI|COPA LOMBO|SALAME|PEPPERONI|MORTADELA|CHARQUE|ALCATRA|PATINHO|FILE|MIGNON|CONTRAFILE|"
    r"COSTELA|COSTELINHA|LOMBO|PERNIL|BISTECA|CUPIM|MUSCULO|ACEM|PICANHA|MAMINHA|"
    r"FRALDINHA|COXAO|LAGARTO|DIAFRAGMA|MIOLO DE ANCHO|PALETA DE CORDEIRO|MAGRET|PERU|"
    r"ROBALO|TILAPIA|PESCADA|SARDINHA|ATUM|BACALHAU|ALICHE|ANCHOVA|POLVO|LULA|MEXILHAO|KANI KAMA|"
    r"QUARTO TRASEIRO|QUARTO DIANTEIRO|PONTA DE AGULHA|"
    r"ARROZ|FEIJAO|MACARRAO|SPAGHETTI|MASSA|FUBA|AMIDO|POLVILHO|AVEIA|TRIGO|MILHO|MIIHO|"
    r"CANJICA|CUSCUZ|SOJA|TOFU|LENTILHA|GRAO DE BICO|QUINOA|"
    r"TOMATE|PASSATA|PELATI|CEBOLA|ALHO|BATATA|CENOURA|BETERRABA|ABOBORA|ABOBRINHA|MANDIOCA|AIPIM|INHAME|"
    r"PIMENTAO|ALFACE|COUVE|REPOLHO|ESPINAFRE|RUCULA|AGRIAO|CHICORIA|BROCOLIS|COUVE-FLOR|"
    r"BERINJELA|CHUCHU|QUIABO|VAGEM|PEPINO|RABANETE|ASPARGO|ALCACHOFRA|SALSAO|CHEIRO VERDE|COENTRO|"
    r"SALSA|SALSINHA|CEBOLINHA|CEBOULLETE|HORTELA|MANJERICAO|ALFAVACA|ALECRIM|TOMILHO|"
    r"OREGANO|LOURO|ENDRO|DILL|CANELA|CRAVO|PIMENTA|COMINHO|CURCUMA|ACAFRAO|COLORAU|"
    r"PAPRICA|NOZ MOSCADA|GENGIBRE|BAUNILHA|ESSENCIA|CORANTE|CMC|CARBOXIMETILCELULOSE|"
    r"LIGA NEUTRA|DESMOLDANTE|SUMAGRE|SUMAC|CUMARU|CARDAMOMO|ERVA DOCE|ERVA MATE|ERVAS|"
    r"HIBISCO|BANANA|MACA|LARANJA|LIMAO|LIMAOSICILIANO|ABACAXI|ABACAXIPEROLA|MAMAO|"
    r"MANGA|MORANGO|UVA|MARACUJA|COCO|MELANCIA|MELAO|ABACATE|AVOCADO|GOIABA|GOIABADA|"
    r"PESSEGO|AMEIXA|CAJU|ACEROLA|TANGERINA|MEXERICA|KIWI|CEREJA|AMARENA|FRAMBOESA|"
    r"AMORA|MIRTILO|MIRTILOS|PEQUI|POLPA|CHOCOLATE|CACAU|MEL|MELADO|GLICOSE|GELATINA|"
    r"CHANTILLY|DOCE DE LEITE|LEITE CONDENSADO|BOMBOM|GRANULADO|SORVETE|PO DOURADO|"
    r"PO PEROLADO|PO COBRE|FOLHAS DE OURO|FLOR COMESTIVEL|VINAGRE|ACETO|SHOYU|MOSTARDA|"
    r"MOSTARDAAMARELAEMGRAOS|KETCHUP|MAIONESE|EXTRATO DE TOMATE|MOLHO|CREME BALSAMICO|"
    r"AZEITONA|AZEITONAS|AZEITONASPRETASSEMCAROCO|AZEITONASVERDESEMCAROCO|ALCAPARRA|"
    r"ALCAPARRAS|CHAMPIGNON|COGUMELO|FUNGHI|PALMITO|ERVILHA|ERVILHAS|VINHO|ESPUMANTE|"
    r"CHAMPAGNE|CERVEJA|CACHACA|RUM|CONHAQUE|LICOR|FRANGELICO|APEROL|BITTER|CAMPARI|"
    r"ANGOSTURA|TEQUILA|VERMOUTH|VERMUTE|VODKA|WHISKY|WHISKEY|XAROPE|SUCO|CAFE|CHA|"
    r"AGUA|GELO|PAO|TORRADA|BISCOITO|BOLACHA|CASTANHA|NOZES|AMENDOA|AMENDOIM|AVELA|"
    r"PISTACHE|UVA PASSA|FRUTOS SECOS|CURRY|IN NATURA|CONGELAD[OA]|RESFRIAD[OA]|TIPO 1|"
    r"SEM SAL|COM SAL|INTEGRAL|DESNATAD[OA]|MOID[OA]|RALAD[OA]|FATIAD[OA]|EM PO|EM GRAO|"
    r"EXTRA VIRGEM|REFINAD[OA]|CRISTAL|DEMERARA|COMESTIVEL)\b"
)

CABECALHOS_E_SECOES = {
    "CODIGO ITEM MXM", "CODIGO MXM", "DESCRICAO/ESPECIFICACAO DETALHADA", "DESCRICAO",
    "ESPECIFICACAO", "U.M", "U.N", "QUANTIDADE POR ALUNO", "QUANTIDADE POR TURMA",
    "QUANTIDADE ALUNO", "VALOR UNITARIO", "VALOR TOTAL", "TOTAL", "PESO", "APROXIMADO DE",
    "TIPO DE FINANCIAMENTO", "INSUMOS", "EQUIPAMENTOS", "UTENSILIOS",
    "EQUIPAMENTOS E UTENSILIOS", "EQUIPAMENTOS, MOVEIS E SOFTWARE", "MATERIAIS",
    "MIDIA ESPECIALIZADA", "BANCO DE PRECOS", "ESTIMATIVA", "UNIFORMES", "MODO DE PREPARO",
    "INFRAESTRUTURA E LISTA BASICA1", "INFRAESTRUTURA E LISTA BASICA",
    "INDICADORES", "LISTA BASICA", "DADOS DA LISTA BASICA", "DADOS DO CURSO",
    "QUALIFICACAO PROFISSIONAL", "ULTIMA REVISAO", "UNIFORME",
    "DESCRICAO DO INGREDIENTE", "ITEM", "QUANTIDADE", "MEDIDA", "CATEGORIA",
    "NAO SE APLICA", "SENAC", "UNIDADE", "PACOTE", "CAIXA", "LATA", "VIDRO",
    "GARRAFA", "MACO", "RESMA", "FARDO", "POTE", "ROLO", "QTD TOTAL DE ALUNOS",
    "RESPONSAVEL- ELABORACAO", "RESPONSAVEL ELABORACAO", "DATA DE ELABORACAO",
    "RESPONSAVEL", "RESPONSAVEL - REVISAO", "RESPONSAVEL-REVISAO", "SEGMENTO",
    "CARGA HORARIA", "TIPO", "CODIGO SIG", "AULAS PLANEJADAS", "PLANEJAMENTO DAS AULAS",
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


def _filtros_comuns_descarte(desc_upper: str) -> bool:
    if len(desc_upper) < 3:
        return True
    if not re.search(r"[A-Z]", desc_upper):
        return True
    if re.fullmatch(r"[\d\s.,/R$-]+", desc_upper):
        return True
    if re.fullmatch(r"(?:ES|E5|S0|10)\d+", desc_upper) or desc_upper.startswith("ES0"):
        return True
    if desc_upper in CABECALHOS_E_SECOES:
        return True
    for padrao in PADROES_RUIDO_REGEX:
        if re.search(padrao, desc_upper):
            return True
    if len(desc_upper.split()) > 10:
        return True
    return False


def classificar_item_utensilio(titulo_item: str, vocabulario_alimentos: set[str]) -> str:
    if texto_corrompido_cid_utensilios(titulo_item):
        return "DESCARTAR"

    desc_upper = normalizar(titulo_item)
    if _filtros_comuns_descarte(desc_upper):
        return "DESCARTAR"

    excecoes_utensilios = {
        "BALDE DE GELO", "PA PARA GELO", "TACA DE AGUA", "PURIFICADOR DE AGUA",
        "CESTO PARA PAES", "PRATO DE PAO", "FACA DE MANTEIGA", "FACA PARA PEIXE",
        "GARFOS DE MESA PARA PEIXE", "FORMA INOX PARA TORTA", "BULE DE CAFE",
        "BULE DE CHA", "BULE DE LEITE", "INFUSOR DE CHA", "MOEDOR DE CAFE",
        "MOEDOR DE PIMENTA", "ESPREMEDOR MANUAL DE LIMAO", "GARRAFA SIFAO PARA CHANTILLY",
        "STORE AND POUR (GARRAFA DE SUCO)", "CALICE LICOR", "TAÇA DE VINHO",
        "TACA DE VINHO", "TACA VINHO", "TACA TULIPA CERVEJA", "COPO WHISKY",
        "TAÇA MARTINI", "TACA MARTINI", "TAÇA IRISH", "TACA IRISH", "TAÇA GT",
        "TACA GT", "GUARDANAPO DE VINHO", "GUARDANAPO DE PANO", "DESCASCADOR DE LEGUMES",
        "FACA DE LEGUMES", "FACA DE SERRA LONGA PARA PAO", "ESCORREDOR DE MACARRAO",
        "POTE BISNAGA PARA CALDAS", "SUPORTE PARA FILTRO", "PA PARA PIZZA", "PA DE PIZZA"
    }
    if any(exc in desc_upper for exc in excecoes_utensilios):
        return "UTENSILIO_CONFIRMADO"

    if desc_upper in vocabulario_alimentos or REGEX_BLOQUEIO_ALIMENTOS.search(desc_upper):
        return "DESCARTAR"

    palavras_titulo = set(re.findall(r"[A-Z0-9-]+", desc_upper))
    for termo_lixo in ITENS_LIMPEZA_ESCRITORIO_DESCARTAVEIS:
        if " " in termo_lixo:
            if re.search(rf"\b{re.escape(termo_lixo)}\b", desc_upper):
                return "DESCARTAR"
        else:
            if termo_lixo in palavras_titulo:
                return "DESCARTAR"

    for termo_ut in TERMOS_UTENSILIOS_E_EQUIPAMENTOS:
        if " " in termo_ut:
            if re.search(rf"\b{re.escape(termo_ut)}\b", desc_upper):
                return "UTENSILIO_CONFIRMADO"
        else:
            if termo_ut in palavras_titulo:
                return "UTENSILIO_CONFIRMADO"

    if REGEX_SINAIS_UTENSILIO.search(desc_upper):
        return "UTENSILIO_CONFIRMADO"

    return "SUSPEITO"


def classificar_item_insumo(titulo_insumo: str, vocabulario_receitas: set[str]) -> str:
    if texto_corrompido_cid_insumos(titulo_insumo):
        return "DESCARTAR"

    desc_upper = normalizar(titulo_insumo)
    if _filtros_comuns_descarte(desc_upper):
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
        "AGUA COM GAS",
        "AGUA TONICA",
        "GELO EM CUBO",
    }
    if any(exc in desc_upper for exc in excecoes_validas):
        return "INSUMO_CONFIRMADO"

    if REGEX_MATERIAIS_E_MEDIDAS_UTENSILIO.search(desc_upper):
        return "DESCARTAR"

    palavras_titulo = set(re.findall(r"[A-Z0-9-]+", desc_upper))
    for termo in TERMOS_PROIBIDOS_INSUMOS:
        if " " in termo:
            if re.search(rf"\b{re.escape(termo)}\b", desc_upper):
                return "DESCARTAR"
        else:
            if termo in palavras_titulo:
                return "DESCARTAR"

    if desc_upper in vocabulario_receitas or REGEX_SINAIS_ALIMENTO.search(desc_upper):
        return "INSUMO_CONFIRMADO"

    return "SUSPEITO"


# ============================================================
# 4. EXTRAÇÃO DAS TABELAS E FICHAS TÉCNICAS
# ============================================================

def extrair_tabelas_inteligente(pagina) -> list[list[list[str]]]:
    tabelas_padrao = pagina.extract_tables() or []

    colapsada = False
    for tab in tabelas_padrao:
        for linha in tab:
            for cel in (linha or []):
                if cel and cel.count("\n") > 12:
                    colapsada = True
                    break
            if colapsada:
                break

    if colapsada or not tabelas_padrao:
        tabelas_texto = pagina.extract_tables(
            table_settings={
                "vertical_strategy": "lines",
                "horizontal_strategy": "text",
                "snap_tolerance": 4,
            }
        ) or []
        if tabelas_texto:
            return tabelas_texto

    return tabelas_padrao


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
    if any(k in texto_inteiro for k in ("CODIGO ITEM MXM", "CODIGO MXM", "QUANTIDADE POR TURMA", "DESCRICAO DO INGREDIENTE", "U.M", "U.N", "VALOR UNITARIO")):
        return False

    amostra = normalizar(" ".join(
        limpar_texto(c) for linha in tabela[:4] for c in (linha or []) if c
    ))
    marcadores_nao_lista = [
        "QTD TOTAL DE ALUNOS", "DADOS DO CURSO", "PLANEJAMENTO DAS AULAS",
        "AULAS PLANEJADAS", "MODO DE PREPARO", "ELEMENTOS DA COMPETENCIA",
        "ORGANIZACAO CURRICULAR", "BIBLIOGRAFIA", "SITUACAO DE APRENDIZAGEM",
    ]
    return any(m in amostra for m in marcadores_nao_lista)


def linha_parece_item_lista_basica_utensilio(valores: list[str]) -> bool:
    texto_completo = normalizar(" ".join(v for v in valores if v))
    marcadores = (
        r"\b(?:KG|UNIDADE|UNI|UN|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
        r"LITRO|LT|PECA|PC|BANDEJA|JOGO|JG|KIT|CONJUNTO|CJ|PAR|METRO|MT|"
        r"NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|BANCO DE PRECOS)\b|R\$|(?:ES|E5|S0|10)\d{5,}"
    )
    return bool(re.search(marcadores, texto_completo))


def linha_parece_item_insumo(valores: list[str], modo_ficha_aula: bool) -> bool:
    texto_completo = normalizar(" ".join(v for v in valores if v))
    if modo_ficha_aula:
        tem_numero = any(re.fullmatch(r"\d+(?:[.,]\d+)?", v.strip()) for v in valores if v)
        tem_unidade = bool(re.search(r"\b(?:G|GR|KG|ML|L|UN|UNID|UNIDADE|PCT|CX|LATA|DENTE|FOLHA|MACO|COLHER|XICARA|METRO|Q\.?B\.?|A GOSTO)\b", texto_completo))
        return tem_numero or tem_unidade
    else:
        marcadores = (
            r"\b(?:KG|UNIDADE|UNI|UN|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
            r"LITRO|LT|PECA|PC|BANDEJA|NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|BANCO DE PRECOS)\b|R\$|(?:ES|E5|S0|10)\d{5,}"
        )
        return bool(re.search(marcadores, texto_completo))


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
        if re.fullmatch(r"(?:ES|E5|S0|10)\d+", v_norm) or v_norm.startswith("ES0"):
            continue
        candidatos.append(v)

    return max(candidatos, key=len) if candidatos else ""


def consolidar_linhas_quebradas_tabela(tabela: list[list[str]], incluir_unidades_extras: bool = True) -> list[list[str]]:
    linhas_consolidadas = []
    bloco_atual = []

    if incluir_unidades_extras:
        marcadores_linha_completa = (
            r"\b(?:KG|UNIDADE|UNI|UN|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
            r"LITRO|LT|PECA INTEIRA|PECA|PC|BANDEJA|JOGO|JG|KIT|CONJUNTO|CJ|PAR|METRO|MT|"
            r"NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|BANCO DE PRECOS)\b|R\$"
        )
    else:
        marcadores_linha_completa = (
            r"\b(?:KG|UNIDADE|UNI|UN|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
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

        if any(h in texto_norm for h in ("CODIGO ITEM MXM", "CODIGO MXM", "DESCRICAO/ESPECIFICACAO", "QUANTIDADE POR TURMA")):
            if bloco_atual:
                linhas_consolidadas.append(bloco_atual)
                bloco_atual = []
            linhas_consolidadas.append(valores)
            continue

        cand = extrair_melhor_candidato_descricao(valores)
        tem_marcador = bool(re.search(marcadores_linha_completa, texto_norm))

        primeiro_val = valores[0].strip() if valores else ""
        eh_inicio_novo_item = (
            bool(re.fullmatch(r"\d{1,3}", primeiro_val))
            or bool(re.match(r"^(?:ES|E5|S0|10)\d{5,}", primeiro_val, flags=re.IGNORECASE))
            or bool(re.match(r"^[A-ZÀ-Ú0-9\s().,/\"'-]{3,65}\s*:", cand))
        )

        if eh_inicio_novo_item and bloco_atual:
            linhas_consolidadas.append(bloco_atual)
            bloco_atual = []

        if cand:
            if not bloco_atual:
                bloco_atual = [cand] + [v for v in valores if v != cand]
            else:
                bloco_atual[0] = f"{bloco_atual[0]} {cand}"
                bloco_atual.extend([v for v in valores if v != cand])
        elif tem_marcador:
            bloco_atual.extend([v for v in valores if v])

    if bloco_atual:
        linhas_consolidadas.append(bloco_atual)

    return linhas_consolidadas


def construir_vocabulario_global_receitas(arquivos_pdf: list[Path]) -> set[str]:
    """Passada 1 única: mapeia ingredientes das receitas."""
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
                                r"^\d+[.)-]?\s+(.+?)\s+\d+(?:[.,]\d+)?\s*(?:g|gr|kg|ml|l|uni|unid|unidade|un|mc|mç|pct)\b",
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

                if not linha_parece_item_insumo(valores, modo_ficha_aula=True):
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
                        r"^\d+[.)-]?\s+(.+?)\s+\d+(?:[.,]\d+)?\s*(?:g|gr|kg|ml|l|uni|unid|unidade|un|mc|mç|pct)\b",
                        linha_limpa,
                        flags=re.IGNORECASE,
                    )
                    if m:
                        nome = extrair_nome_insumo_limpo(m.group(1))
                        if nome:
                            encontrados.append(nome)

    return encontrados


def extrair_utensilios_pdf(
    pdf, nome_curso: str, vocabulario_alimentos: set[str]
) -> tuple[list[str], list[str], bool]:
    utensilios = []
    suspeitos = []
    nome_curso_norm = normalizar(nome_curso)
    na_lista_basica = False
    em_bloco_insumos = False
    tem_cid = False

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text() or ""
        if "(cid:" in texto_pag.lower():
            tem_cid = True

        texto_pag_norm = normalizar(texto_pag)

        if (
            "LISTA BASICA" in texto_pag_norm
            or "DADOS DA LISTA BASICA" in texto_pag_norm
            or "INFRAESTRUTURA E LISTA BASICA" in texto_pag_norm
            or re.search(r"\bUTENSILIOS\b", texto_pag_norm)
            or "EQUIPAMENTOS E UTENSILIOS" in texto_pag_norm
        ):
            na_lista_basica = True

        if not na_lista_basica:
            continue

        if any(
            marc in texto_pag_norm
            for marc in (
                "DESCRICAO DO INGREDIENTE",
                "FICHA TECNICA DE PRODUCAO",
                "MODO DE PREPARO",
                "PARECER - N",
            )
        ):
            break

        tem_cabecalho_utensilios = bool(
            re.search(r"\bUTENSILIOS\b", texto_pag_norm)
            or "EQUIPAMENTOS E UTENSILIOS" in texto_pag_norm
        )
        tem_cabecalho_equipamentos_sozinhos = "EQUIPAMENTOS, MOVEIS E SOFTWARE" in texto_pag_norm
        tem_cabecalho_insumos = bool(re.search(r"\bINSUMOS\b", texto_pag_norm))
        tem_cabecalho_uniformes = bool(re.search(r"\bUNIFORMES?\b", texto_pag_norm))

        if tem_cabecalho_utensilios:
            em_bloco_insumos = False
        elif tem_cabecalho_insumos or tem_cabecalho_uniformes or tem_cabecalho_equipamentos_sozinhos:
            em_bloco_insumos = True

        if em_bloco_insumos:
            continue

        for tabela in extrair_tabelas_inteligente(pagina):
            if not tabela or tabela_e_de_metadados_ou_cronograma(tabela):
                continue

            linhas_tratadas = consolidar_linhas_quebradas_tabela(tabela, incluir_unidades_extras=True)

            for valores in linhas_tratadas:
                texto_linha_norm = normalizar(" ".join(v for v in valores if v))
                if any(h in texto_linha_norm for h in ("CODIGO ITEM MXM", "CODIGO MXM", "DESCRICAO/ESPECIFICACAO")):
                    continue

                if not linha_parece_item_lista_basica_utensilio(valores):
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


def extrair_insumos_pdf(
    pdf, nome_curso: str, vocabulario_receitas: set[str]
) -> tuple[list[str], list[str], bool]:
    insumos = []
    suspeitos = []
    nome_curso_norm = normalizar(nome_curso)
    na_lista_basica = False
    em_bloco_nao_insumos = False
    tem_cid = False

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text() or ""
        if "(cid:" in texto_pag.lower():
            tem_cid = True

        texto_pag_norm = normalizar(texto_pag)

        if (
            "LISTA BASICA" in texto_pag_norm
            or "DADOS DA LISTA BASICA" in texto_pag_norm
            or re.search(r"\bINSUMOS\b", texto_pag_norm)
        ):
            na_lista_basica = True

        # Encerra apenas nas Fichas Técnicas ou no Parecer Final (NÃO encerra em "ANEXO", pois a Lista Básica fica dentro do Anexo em vários PDFs)
        if na_lista_basica and any(
            marc in texto_pag_norm
            for marc in (
                "DESCRICAO DO INGREDIENTE",
                "FICHA TECNICA DE PRODUCAO",
                "MODO DE PREPARO",
                "PARECER - N",
            )
        ):
            break

        if not na_lista_basica:
            continue

        if re.search(r"\bINSUMOS\b", texto_pag_norm):
            em_bloco_nao_insumos = False
        elif (
            "EQUIPAMENTOS, MOVEIS E SOFTWARE" in texto_pag_norm
            or (re.search(r"\bUTENSILIOS\b", texto_pag_norm) and not re.search(r"\bINSUMOS\b", texto_pag_norm))
            or re.search(r"\bUNIFORMES?\b", texto_pag_norm)
        ):
            em_bloco_nao_insumos = True

        if em_bloco_nao_insumos:
            continue

        for tabela in extrair_tabelas_inteligente(pagina):
            if not tabela or tabela_e_de_metadados_ou_cronograma(tabela):
                continue

            linhas_tratadas = consolidar_linhas_quebradas_tabela(tabela, incluir_unidades_extras=False)

            for valores in linhas_tratadas:
                texto_linha_norm = normalizar(" ".join(v for v in valores if v))
                if any(h in texto_linha_norm for h in ("CODIGO ITEM MXM", "CODIGO MXM", "DESCRICAO/ESPECIFICACAO")):
                    continue

                if not linha_parece_item_insumo(valores, modo_ficha_aula=False):
                    continue

                candidato = extrair_melhor_candidato_descricao(valores)
                nome_insumo = extrair_nome_insumo_limpo(candidato)

                if not nome_insumo or normalizar(nome_insumo) == nome_curso_norm:
                    continue

                status_item = classificar_item_insumo(nome_insumo, vocabulario_receitas)

                if status_item == "INSUMO_CONFIRMADO":
                    if not any(normalizar(x) == normalizar(nome_insumo) for x in insumos):
                        insumos.append(nome_insumo)
                elif status_item == "SUSPEITO":
                    if not any(normalizar(x) == normalizar(nome_insumo) for x in suspeitos):
                        suspeitos.append(nome_insumo)

    # Complementa sempre com as Fichas Técnicas (garante cobertura total mesmo quando a tabela INSUMOS tem OCR corrompido)
    for cand in extrair_itens_fichas_pdf(pdf):
        if not cand or normalizar(cand) == nome_curso_norm:
            continue
        status_ficha = classificar_item_insumo(cand, vocabulario_receitas)
        if status_ficha != "DESCARTAR":
            if not any(normalizar(x) == normalizar(cand) for x in insumos):
                insumos.append(cand)

    return insumos, suspeitos, tem_cid


# ============================================================
# 5. FLUXO PRINCIPAL UNIFICADO
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
    total_geral_utensilios = 0
    relatorio = []
    todos_suspeitos = []

    print("Passada 2/2: Extraindo e unificando insumos e utensílios de todos os cursos...")

    with ARQUIVO_SAIDA.open("w", encoding="utf-8-sig", newline="") as arquivo_saida:
        escritor = csv.DictWriter(
            arquivo_saida,
            fieldnames=["nome_curso", "insumos", "utensilios"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor.writeheader()

        for indice, caminho_pdf in enumerate(arquivos_pdf, start=1):
            try:
                with pdfplumber.open(caminho_pdf) as pdf:
                    nome_curso = extrair_nome_curso(pdf, caminho_pdf)
                    insumos, suspeitos_ins, tem_cid_ins = extrair_insumos_pdf(
                        pdf, nome_curso, vocabulario_receitas
                    )
                    utensilios, suspeitos_ut, tem_cid_ut = extrair_utensilios_pdf(
                        pdf, nome_curso, vocabulario_receitas
                    )

                tem_cid = tem_cid_ins or tem_cid_ut

                if insumos or utensilios:
                    for ins, ut in zip_longest(insumos, utensilios, fillvalue=""):
                        escritor.writerow({
                            "nome_curso": nome_curso,
                            "insumos": ins,
                            "utensilios": ut
                        })
                else:
                    escritor.writerow({
                        "nome_curso": nome_curso,
                        "insumos": "",
                        "utensilios": ""
                    })

                for susp in suspeitos_ins:
                    todos_suspeitos.append({
                        "arquivo": caminho_pdf.name,
                        "nome_curso": nome_curso,
                        "tipo": "INSUMO",
                        "item_suspeito": susp
                    })

                for susp in suspeitos_ut:
                    todos_suspeitos.append({
                        "arquivo": caminho_pdf.name,
                        "nome_curso": nome_curso,
                        "tipo": "UTENSILIO",
                        "item_suspeito": susp
                    })

                qtd_ins = len(insumos)
                qtd_ut = len(utensilios)
                total_geral_insumos += qtd_ins
                total_geral_utensilios += qtd_ut

                if qtd_ins > 0 or qtd_ut > 0:
                    status = "OK"
                elif tem_cid:
                    status = "FONTE CORROMPIDA (CID) - REQUER OCR"
                else:
                    status = "SEM ITENS"

                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": nome_curso,
                    "qtd_insumos": qtd_ins,
                    "qtd_utensilios": qtd_ut,
                    "qtd_suspeitos": len(suspeitos_ins) + len(suspeitos_ut),
                    "status": status
                })

                print(
                    f"[{indice}/{len(arquivos_pdf)}] {nome_curso} | "
                    f"Insumos: {qtd_ins} | Utensílios: {qtd_ut} ({status})"
                )

            except Exception as erro:
                total_erros += 1
                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": "",
                    "qtd_insumos": 0,
                    "qtd_utensilios": 0,
                    "qtd_suspeitos": 0,
                    "status": f"ERRO: {erro}"
                })
                print(f"ERRO ao processar {caminho_pdf.name}: {erro}")

    with ARQUIVO_RELATORIO.open("w", encoding="utf-8-sig", newline="") as arquivo_relatorio:
        escritor_rel = csv.DictWriter(
            arquivo_relatorio,
            fieldnames=["arquivo", "nome_curso", "qtd_insumos", "qtd_utensilios", "qtd_suspeitos", "status"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor_rel.writeheader()
        escritor_rel.writerows(relatorio)

    with ARQUIVO_REVISAO.open("w", encoding="utf-8-sig", newline="") as arquivo_rev:
        escritor_rev = csv.DictWriter(
            arquivo_rev,
            fieldnames=["arquivo", "nome_curso", "tipo", "item_suspeito"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor_rev.writeheader()
        escritor_rev.writerows(todos_suspeitos)

    print("\n========== EXTRAÇÃO UNIFICADA CONCLUÍDA ==========")
    print(f"Total de PDFs processados: {len(arquivos_pdf)}")
    print(f"Erros: {total_erros}")
    print(f"Total geral de insumos confirmados: {total_geral_insumos}")
    print(f"Total geral de utensílios/equipamentos confirmados: {total_geral_utensilios}")
    print(f"Itens na fila de revisão (zona cinzenta): {len(todos_suspeitos)}")
    print(f"\nArquivo principal unificado: {ARQUIVO_SAIDA}")
    print(f"Arquivo de relatório: {ARQUIVO_RELATORIO}")
    print(f"Arquivo de revisão: {ARQUIVO_REVISAO}")


if __name__ == "__main__":
    main()