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
ARQUIVO_REVISAO = PASTA_RESULTADOS / "itens_suspeitos_revisao_utensilios.csv"

# ============================================================
# 2. NORMALIZAÇÃO E SANEAMENTO
# ============================================================

CORRECOES_UTENSILIOS = {
    "BOWLL": "BOWL",
    "BOWLS": "BOWL",
    "BAILHARINAS": "BAILARINA",
    "BAILARINAS": "BAILARINA",
    "BALACA": "BALANCA",
    "BALACA COM IMPRESSORA INTEGRADA": "BALANCA COM IMPRESSORA INTEGRADA",
    "DEFUMDOR": "DEFUMADOR",
    "DEFUMDOR SMOKE GUN": "DEFUMADOR SMOKE GUN",
    "PROJETOR MULTIMIDEA": "PROJETOR MULTIMIDIA",
    "PROJETOR MULTIMÍDEA": "PROJETOR MULTIMIDIA",
    "MANDOLIN": "MANDOLINE",
    "FILTROPAPEL": "FILTRO DE PAPEL",
    "FILTROPAPELV60103": "FILTRO DE PAPEL V60",
    "FILTROPAPEL V60 103": "FILTRO DE PAPEL V60",
    "PALITODEBAMBU": "PALITO DE BAMBU",
    "P.RATO RASO": "PRATO RASO",
    "G P.RATO RASO": "PRATO RASO",
    "PINCAS": "PINCA",
    "PEGADORES": "PEGADOR",
    "CORTADORES": "CORTADOR",
    "AROS": "ARO",
    "FORMAS": "FORMA",
    "FORMINHAS": "FORMINHA",
    "TABUAS": "TABUA",
    "FACAS": "FACA",
    "PANELAS": "PANELA",
    "CUBAS": "CUBA",
    "COLHERES": "COLHER",
    "GARFOS": "GARFO",
    "GARFOS PARA SOBREMESA": "GARFO DE SOBREMESA",
    "PRATOS": "PRATO",
    "COPOS": "COPO",
    "XICARAS": "XICARA",
    "TACAS": "TACA",
    "MEDIDORES": "MEDIDOR",
    "RAMEQUINS": "RAMEQUIN",
    "BICOS PARA CONFEITAR": "BICO DE CONFEITAR",
    "BALCOES": "BALCAO",
    "BANCADAS": "BANCADA",
    "MASSEIRAS": "MASSEIRA",
    "GRAVADA ESTILO CLASSICA": "GRAVATA ESTILO CLASSICA",
    "SACO DE CONFEITEIRO DESCARTAVEL PARA CONFEITAR": "SACO DE CONFEITAR DESCARTAVEL",
    "SACO DE CONFEITEIRO DESCARTAVEL PARA CONFEITAR TAMANHO MEDIO": "SACO DE CONFEITAR DESCARTAVEL",
    "SACO DESCARTAVEL PARA CONFEITAR": "SACO DE CONFEITAR DESCARTAVEL",
    "SAQUINHOS DE DIM DIM. DE PLASTICO COM 100 UNIDADES. ATOXICO": "SAQUINHO DE DIM DIM",
    "SAQUINHOS DE DIM DIM": "SAQUINHO DE DIM DIM",
    "TOALHA MESA BRANCA": "TOALHA DE MESA BRANCA",
    "MIDIA ACETATO": "ACETATO PARA CONFEITARIA",
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip(" :;-',.").upper()


def limpar_texto(texto: str) -> str:
    if not texto:
        return ""
    try:
        if "Ã" in texto or "Â" in texto:
            texto = texto.encode("latin1").decode("utf-8")
    except Exception:
        pass
    texto = re.sub(r"([a-záéíóúâêôãõç])([A-ZÁÉÍÓÚÂÊÔÃÕÇ])", r"\1 \2", texto)
    texto = re.sub(r"(\d)([A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]{3,})", r"\1 \2", texto)
    return re.sub(r"\s+", " ", texto).strip()


def texto_corrompido_cid_ou_sobreposto(texto: str) -> bool:
    if not texto:
        return True
    low = texto.lower()
    if "(cid:" in low or "(cid" in low:
        return True
    texto_upper = texto.upper()

    palavras_todas = re.findall(r"\b[A-Z0-9ÁÉÍÓÚÂÊÔÃÕÇ]{1,2}\b", texto_upper)
    stop_curtas = {"DE", "DA", "DO", "EM", "AO", "OS", "AS", "UM", "E", "A", "O", "G", "L", "ML", "KG", "UN", "CX", "MC", "CM", "MM", "V", "W", "N", "PE"}
    tokens_estranhos = [t for t in palavras_todas if t not in stop_curtas and not t.isdigit()]
    if len(tokens_estranhos) >= 2:
        return True

    if re.search(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}[.,;][A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}", texto_upper):
        return True

    if re.search(r"\b[A-Z]\d+\b|\b\d+[A-Z]\b", texto_upper):
        if not re.search(r"\b(?:110V|220V|127V|V60|A4)\b", texto_upper):
            return True

    palavras = re.findall(r"[A-ZÀ-Ú]{4,}", texto_upper)
    excecoes_dobradas = {
        "AEROPRESS", "PITCHER", "STRAINER", "MUDDLER", "CUTTER", "CHINOIS",
        "MANDOLINE", "SOUSPLAT", "GUERIDON", "RECHAUD", "RAMEQUIN", "RAMEQUINS",
        "SOUNDBAR", "GLASS", "COFFEE", "PRESS", "SPOON", "JIGGER", "SHAKER",
        "TAMPER", "VAPOREIRA", "CUSCUZEIRA", "CAFETEIRA", "FRIGIDEIRA",
        "BATEDEIRA", "SORVETEIRA", "MASSEIRA", "MASSEIRAS", "SELADORA",
        "IMPRESSORA", "CLASSICA", "SAQUINHOS", "SAQUINHO"
    }
    for p in palavras:
        if re.search(r"[AEIOUÁÉÍÓÚÂÊÔÃÕ]{4,}", p):
            return True
        if re.search(r"[BCDFGHJKLMNPQRSTVWXZ]{5,}", p):
            return True
        if p not in excecoes_dobradas:
            if re.search(r"([BCDFGHJKMNPQTVWXYZ])\1", p):
                return True
        acentos = len(re.findall(r"[ÁÉÍÓÚÂÊÔÃÕÇ]", p))
        if acentos >= 3:
            return True

    tokens_mistos = re.findall(r"[A-Z0-9ÁÉÍÓÚÂÊÔÃÕÇ]{7,}", texto_upper)
    for tok in tokens_mistos:
        if re.search(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ]\d+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]|\d+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]+\d+", tok):
            if not re.search(r"(?:110V|220V|127V|CM|MM|V60)", tok):
                return True
        if len(tok) >= 10:
            vogais = len(re.findall(r"[AEIOUÁÉÍÓÚÂÊÔÃÕ]", tok))
            if vogais == 0 or (vogais / len(tok)) < 0.22:
                return True

    return False


def extrair_nome_utensilio_limpo(descricao_bruta: str) -> str:
    texto = limpar_texto(descricao_bruta)

    texto = re.sub(r"^(?:DE\s+MEDIDA|ITE\s*M|QUANTID(?:ADE)?|UNIDADE|MIDIA)\s+", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^(?:ES|E2|20)\d{6,}\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^\d{1,3}\s*[.)-]\s*", "", texto)

    nome = re.split(r"\s*:\s*|\s+[-–—]\s+", texto, maxsplit=1)[0]

    nome = re.sub(
        r"\s+\d+(?:[.,]\d+)?\s*(?:ML|G|GR|KG|L|UNI|UNID|UNIDADE|PCT|CX|LATA|VIDRO|GARRAFA|MACO|MC|PAR|JOGO|JG|CJ|CONJUNTO)\b.*$",
        "",
        nome,
        flags=re.IGNORECASE,
    )
    nome = nome.strip(" .:-;•*',")

    norm = normalizar(nome)
    if norm in CORRECOES_UTENSILIOS:
        return CORRECOES_UTENSILIOS[norm]

    return nome


def extrair_nome_curso(pdf, caminho_pdf: Path) -> str:
    ano = ""
    m_ano_arq = re.search(r"\b(20\d{2})\b", caminho_pdf.stem)
    if m_ano_arq:
        ano = m_ano_arq.group(1)

    genericos = {
        "APERFEICOAMENTO", "QUALIFICACAO PROFISSIONAL", "ACAO EXTENSIVA",
        "PROGRAMA SOCIOPROFISSIONAL", "PROGRAMAS INSTRUMENTAIS", "GASTRONOMIA"
    }

    nome_encontrado = ""
    for pagina in pdf.pages[:15]:
        texto = limpar_texto(pagina.extract_text(x_tolerance=1.2) or "")
        if not ano:
            m_ano_txt = re.search(r"(?:ANO|ATUALIZACAO|ELABORACAO)\D{0,15}(20\d{2})", normalizar(texto))
            if m_ano_txt:
                ano = m_ano_txt.group(1)

        for tabela in pagina.extract_tables() or []:
            for linha in tabela:
                celulas = [limpar_texto(c) for c in linha if c]
                for idx, cel in enumerate(celulas):
                    if normalizar(cel) in {"CURSO", "CURSO:", "NOME DO CURSO", "TITULO DO CURSO"} and idx + 1 < len(celulas):
                        candidato = celulas[idx + 1]
                        if candidato and normalizar(candidato) not in {"QTD TOTAL DE ALUNOS", "SEGMENTO", "CARGA HORARIA"} | genericos:
                            nome_encontrado = candidato
                            break
                if nome_encontrado:
                    break
            if nome_encontrado:
                break

        if not nome_encontrado and "(cid:" not in texto.lower():
            m1 = re.search(r"(?:NOME\s+DO\s+|TITULO\s+DO\s+)?CURSO\s*:\s*([^\n]+)", texto, flags=re.IGNORECASE)
            if m1:
                cand = limpar_texto(m1.group(1))
                if cand and normalizar(cand) not in {"CURSO", "QTD TOTAL DE ALUNOS"} | genericos:
                    nome_encontrado = cand.strip()

        if nome_encontrado:
            break

    if not nome_encontrado or normalizar(nome_encontrado) in genericos:
        nome_encontrado = caminho_pdf.stem.replace("-", " ").replace("_", " ")

    nome_limpo = re.split(
        r"\b(?:Habilita[çc][ãa]o|Tipo\s+d[eo]\s+Curso|Compet[êe]ncia|QTD\s+TOTAL|Segmento|Carga\s+Hor[áa]ria|Eixo)\b|:\s*Aperfei[çc]oamento",
        nome_encontrado,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    nome_limpo = re.sub(r"\s+Aperfei[çc]oamento\s*$", "", nome_limpo, flags=re.IGNORECASE)
    nome_limpo = re.sub(r"[-–—]?\s*\b\d+\s*(?:horas?|hs?|h/a)\b", "", nome_limpo, flags=re.IGNORECASE)
    if ano:
        nome_limpo = re.sub(rf"[-–—]?\s*\b{ano}\b", "", nome_limpo)
    nome_limpo = re.sub(r"\s+", " ", nome_limpo).strip(" -–—_\"“”'.")

    if normalizar(nome_limpo) in genericos or len(normalizar(nome_limpo)) < 4:
        nome_limpo = re.sub(r"[-–—]?\s*\b\d+\s*(?:horas?|hs?|h/a)\b", "", caminho_pdf.stem.replace("-", " ").replace("_", " "), flags=re.IGNORECASE)
        if ano:
            nome_limpo = re.sub(rf"[-–—]?\s*\b{ano}\b", "", nome_limpo)
        nome_limpo = re.sub(r"\s+", " ", nome_limpo).strip(" -–—_\"“”'.")

    return f"{nome_limpo} ({ano})" if ano else nome_limpo


# ============================================================
# 3. CLASSIFICADOR SEMÂNTICO (UTENSÍLIO/EQUIPAMENTO VS INSUMO)
# ============================================================

REGEX_SINAIS_UTENSILIO = re.compile(
    r"\b(?:FACA|FACAS|CUTELO|CHAIRA|PEDRA DE AFIAR|PEDRA PARA AMOLAR|AFIADOR|DESCASCADOR|BOLEADOR|DESCAROCADOR|"
    r"VAZADOR|CORTADOR|CORTADORES|CARRETILHA|RALADOR|ZESTER|MANDOLINE|MANDOLIN|TESOURA|"
    r"TABUA|TABUAS|PLACA DE CORTE|PLACAS DE ETILENO|SUPORTE PARA PLACAS|BARRA MAGNETICA|"
    r"PANELA|PANELAS|FRIGIDEIRA|FRIGIDEIRAS|CALDEIRAO|CACAROLA|ASSADEIRA|FORMA|FORMAS|FORMINHA|FORMINHAS|"
    r"TORTEIRA|CUSCUZEIRA|VAPOREIRA|WOK|TACHO|CHALEIRA|BULE|LEITEIRA|"
    r"BOWL|BOWLS|BOWLL|TIGELA|BACIA|CUBA|CUBAS|TRAVESSA|RECIPIENTE|POTE|POTES|VIDRO PARA CONSERVA|"
    r"RAMEQUIN|RAMEQUINS|BISNAGA|AZEITEIRO|GALHETEIRO|PORTA CONDIMENTO|DISPENSADOR|DISPENSER|"
    r"COLHER|COLHERES|CONCHA|ESCUMADEIRA|ESPATULA|FOUET|BATEDOR|PINCA|PINCAS|"
    r"PEGADOR|PEGADORES|PA PARA|SUPORTE DE PAS|RASPADOR|AMASSADOR|SOCADOR|MACERADOR|"
    r"ESPREMEDOR|PENEIRA|TAMIS|CHINOIS|COADOR|STRAINER|PASSADOR|FUNIL|ESCORREDOR|"
    r"GARFO|GARFOS|PRATO|PRATOS|PIRES|COPO|COPOS|XICARA|XICARAS|TACA|TACAS|JARRA|GARRAFA TERMICA|"
    r"CANECA|SOUSPLAT|CLOCHE|RECHAUD|BANDEJA|CESTO PARA PAES|JOGO AMERICANO|PANO COBRE MANCHAS|"
    r"TOALHA DE MESA|TOALHA MESA|CENTRO DE MESA|"
    r"SIFAO|GARRAFA DE CHANTILLY|COQUETELEIRA|DOSADOR|JIGGER|MUDDLER|MEXEDOR|ABRIDOR|SACARROLHA|"
    r"SPEED RAIL|STOREN POUR|SERVICE MAT|BAR CADDY|CAVIAR BOX|LICOREIRA|DECANTER|VACUO VINS|"
    r"CUSPIDEIRA|CHAWAM|AEROPRESS|PITCHER|MINI PITCHER|TAMPER|BATE BORRA|FILTRO|SUPORTE PARA FILTRO|"
    r"BICO DE CONFEITAR|BICOS PARA CONFEITAR|BICO PITANGA|ADAPTADOR|BAILARINA|BAILARINAS|BAILHARINAS|"
    r"PINCEL|ROLO DE MASSA|ROLO LAMINADOR|ARO|AROS|TAPETE DE SILICONE|MOLDE|STENCIL|PICOLETEIRA|"
    r"CARTAO LAMINADO|SUPORTE DE TORTAS|SUPORTE PLASTICO|SUPORTE PARA BOLO|TOPO DE BOLO|PISTILO|FOLHA DE TRANSFER|ACETATO|"
    r"SERINGA|AMPOLAS|BISTURI|TERMOMETRO|BALANCA|BALACA|MEDIDOR|MEDIDORES|MEDIDORA|CRONOMETRO|MACARICO|"
    r"CHAPA|GRELHA|ESPETO|ESPETINHO|ESPETINHOS|GANCHO|ARCO DE SERRA|CARRINHO|GUERIDON|CONTENTOR|CAIXA PLASTICA|CAIXA TERMICA|"
    r"LIXEIRA|"
    r"FOGAO|FORNO|MICROONDAS|MICRO-ONDAS|REFRIGERADOR|GELADEIRA|FREEZER|ULTRACONGELADOR|FRIO RAPIDO|"
    r"LIQUIDIFICADOR|BATEDEIRA|PROCESSADOR|MULTIPROCESSADOR|MIXER|CUTTER|TRITURADOR|"
    r"MOEDOR|FATIADOR|CILINDRO|MASSEIRA|MASSEIRAS|DIVISORA|MODELADORA|EXTRATOR|SORVETEIRA|"
    r"MAQUINA|CAFETEIRA|SELADORA|SOUS VIDE|TERMO CIRCULADOR|CAMARA DE FERMENTACAO|"
    r"PLACA DE INDUCAO|DEFUMADOR|DEFUMDOR|DESIDRATADORA|INFUSOR|BOMBA DE AQUARIO|ENSACADOR|SERRA FITA|"
    r"AMACIADOR DE BIFE|FRITADEIRA|CHURRASQUEIRA|ADEGA|COIFA|EXAUSTOR|PURIFICADOR|"
    r"BALCAO|BALCOES|BANCADA|BANCADAS|ESTANTE|PRATELEIRA|ARMARIO|PIA|TANQUE|EXPOSITOR|VITRINE|"
    r"AVENTAL|DOLMA|TOUCA|LUVA|LUVAS|MASCARA|SAPATO|BOTA|JALECO|JAPONA|CALCA|CAMISETA|CAMISA|COLETE|GRAVATA|GRAVADA|"
    r"PANO|ESPONJA|FIBRA SINTETICA|FIBRACO|ESCOVA|VASSOURA|RODO|BORRIFADOR|HIPOCLORITO|"
    r"DETERGENTE|DESINFETANTE|AGUA SANITARIA|SABONETE|ALCOOL ETILICO|ALCOOL GEL|"
    r"PAPEL TOALHA|PAPEL ALUMINIO|PAPEL MANTEIGA|PAPEL FILME|FILME PVC|PAPEL CHUMBO|GUARDANAPO|"
    r"SACO PLASTICO|SACO DE LIXO|SACO DE CONFEITAR|SACO DE CONFEITEIRO|SACO DESCARTAVEL|SAQUINHO|SAQUINHOS|"
    r"EMBALAGEM|MARMITEX|CAIXA DE PAPELAO|ETIQUETA|"
    r"PALITO|CANUDO|BARBANTE|FITILHO|ISQUEIRO|FOSFORO|REFIL GAS|LENHA|CARVAO|GAZE|ALGODAO|BOBINA)\b"
)

REGEX_MATERIAIS_UTENSILIO = re.compile(
    r"\b(?:INOX|INOXIDAVEL|ACO INOX|SILICONE|POLIETILENO|POLIPROPILENO|ALUMINIO|"
    r"VIDRO TEMPERADO|CERAMICA|PORCELANA|LOUCA|MADEIRA|BAMBU|TEFLON|"
    r"ANTIADERENTE|ACRILICO|NYLON|COBRE|110V|220V|127V|BIVOLT|WATTS|"
    r"MALHA FINA|CABO BRANCO|CABO PRETO|CABO VERMELHO|CABO VERDE|CABO AZUL|"
    r"CABO AMARELO|OCUPACIONAL|ISOPOR|TRAMONTINA|METVISA|CISPER|EPOXI)\b"
)

REGEX_ALIMENTOS_PROIBIDOS = re.compile(
    r"\b(?:ACUCAR|SAL|OLEO|AZEITE|FARINHA|FERMENTO|BICARBONATO|BICABORNATO|LEITE|"
    r"MANTEIGA|MARGARINA|CREME DE LEITE|NATA|QUEIJO|QUEJO|MOZZARELLA|MUCARELA|GORGONZOLA|"
    r"RICOTA|CHEDDAR|REQUEIJAO|CATUPIRY|PARMESAO|COALHO|PROVOLONE|BURRATA|"
    r"OVO|OVOS|GEMA|GEMAS|CLARA|CLARAS|CARNE|FRANGO|GALINHA|PEIXE|CAMARAO|CAMAROES|"
    r"BACON|GUANCIALE|PANCETTA|LINGUICA|PRESUNTO|CHARQUE|ALCATRA|PATINHO|FILE|MIGNON|"
    r"CONTRAFILE|COSTELA|COSTELINHA|LOMBO|PERNIL|BISTECA|CUPIM|MUSCULO|ACEM|PICANHA|"
    r"MAMINHA|FRALDINHA|COXAO|LAGARTO|ROBALO|TILAPIA|PESCADA|SARDINHA|ATUM|BACALHAU|"
    r"POLVO|LULA|MEXILHAO|SALMAO|SUINO|CORDEIRO|CABRITO|T-BONE|TAMBAQUI|TAMBAQUEI|"
    r"COXA|SOBRECOXA|DIAFRAGMA|MIOLO DE ANCHO|OSSOBUCO|MAGRET|COELHO|PERU|BLANQUET|"
    r"CORACAO DE BOI|CORACAO BOVINO|FIGADO BOVINO|BANHA|RA INTEIRA|TRIPA|KANI KAMA|"
    r"ARROZ|FEIJAO|MACARRAO|SPAGHETTI|MASSA|FUBA|AMIDO|POLVILHO|AVEIA|TRIGO|MILHO|"
    r"CANJICA|CUSCUZ|SOJA|TOFU|LENTILHA|GRAO DE BICO|QUINOA|SAGU|CEVADA|"
    r"TOMATE|TOMATES|CENOURA|BETERRABA|ABOBORA|ABOBRINHA|MANDIOCA|AIPIM|INHAME|CARA|PIMENTAO|"
    r"ALFACE|COUVE|REPOLHO|ESPINAFRE|RUCULA|AGRIAO|CHICORIA|BROCOLIS|COUVE-FLOR|"
    r"BERINJELA|CHUCHU|QUIABO|VAGEM|PEPINO|RABANETE|ASPARGO|ASPARGOS|CEBOLA|CEBOLAS|ALHO|BATATA|BATATAS|"
    r"SALSA|SALSINHA|CEBOLINHA|SALSAO|ACELGA|ALCACHOFRA|BROTO|ALFAFA|CAPIM SANTO|"
    r"HORTELA|ALECRIM|TOMILHO|OREGANO|MANJERICAO|MAJERICAO|ALFAVACA|COENTRO|CEBOULLETE|CIBOULETTE|ENDRO|DILL|"
    r"CANELA|CANELAEMCASCA|CRAVO|PIMENTA|CURCUMA|ACAFRAO|PAPRICA|NOZ MOSCADA|GENGIBRE|BAUNILHA|"
    r"CARDAMOMO|CUMARU|SUMAGRE|SUMAC|ERVA DOCE|ERVAS|ANIS|ESTRELADO|WASABI|CURRY|SACHET|CREME TARTARO|COLORAU|LOURO|"
    r"BANANA|MACA|LARANJA|LIMAO|LIMAOSICILIANO|ABACAXI|ABACAXIPEROLA|MAMAO|MANGA|MORANGO|UVA|MARACUJA|COCO|"
    r"MELANCIA|MELAO|ABACATE|AVOCADO|GOIABA|PESSEGO|AMEIXA|CAJU|ACEROLA|KIWI|"
    r"FRAMBOESA|FRAMBOESAS|MIRTILO|MIRTILOS|AMORA|CEREJA|CEREJAAMARENA|AMARENA|DAMASCO|PEQUI|POLPA|"
    r"CHOCOLATE|CACAU|MEL|MELADO|GLICOSE|GELATINA|CHANTILLY|DOCE DE LEITE|IOGURTE|"
    r"LEITE CONDENSADO|BOMBOM|GRANULADO|SORVETE|CORANTE|CMC|CARBOXIMETILCELULOSE|DESMOLDANTE|"
    r"PASTA AMERICANA|PASTA DE AMENDOIN|PASTA DE AMENDOIM|BALAS|"
    r"PO DOURADO|PO PEROLADO|FLOR COMESTIVEL|ADOCANTE|XILITOL|FUMACA LIQUIDA|FUMACA EM PO|"
    r"VINAGRE|SHOYU|MOSTARDA|KETCHUP|MAIONESE|CREME BALSAMICO|CALDO DE LEGUMES|"
    r"EXTRATO DE TOMATE|MOLHO|MOLHOINGLES|AZEITONA|AZEITONAS|AZEITONASVERDESEMCAROCO|ALCAPARRA|CHAMPIGNON|COGUMELO|COGUMELOS|ERVILHA|ERVILHAS|PALMITO|"
    r"VINHO|VINHOBRANCOSECO|ESPUMANTE|CERVEJA|RUM|RUMBRANCO|CONHAQUE|BRANDY|LICOR|LICORCREMEDECACAU|LICORTRIPLESEC|"
    r"APEROL|APEROLAPERITIVO|BITTER|CAMPARI|VERMOUTH|VERMUTE|REFRIGERANTE|"
    r"VODKA|WHISKY|WHISKEY|WHISKEYAMERICANO|TEQUILA|GIN|CACHACA|CACHACABRANCA|AGUA ARDENTE|SAKE|SAQUE|"
    r"XAROPE|XAROPEGRENADINE|SUCO|CAFE|CAPSULA DE CAFE|CAPSULA DE CAFEESPRESSO|CHA|MATCHA|"
    r"AGUA MINERAL|AGUA COM GAS|GELO|PAO|BAGUETE|TORRADA|BISCOITO|BOLACHA|"
    r"CASTANHA|NOZES|AMENDOA|AMENDOIM|AVELA|PISTACHE|UVA PASSA|FRUTOS SECOS|ALCOOL DE CEREAIS|AL COOL DE CEREAIS)\b"
)

INFRA_SALA_AULA_E_PAPELARIA = {
    "AR-CONDICIONADO", "AR CONDICIONADO", "CARTEIRA UNIVERSITARIA", "CARTEIRA UNIVERSITARIA DOBRAVEL",
    "CADEIRA DE SECRETARIA GIRATORIA", "CADEIRA DE PRESIDENTE GIRATORIA", "CADEIRA SECRETARIA ECONOMICA",
    "CADEIRA COM 4 PERNAS E RODIZIOS", "MESA DE ESCRITORIO", "MESA DO PROFESSOR",
    "MESA ESCOLAR ADULTO", "MESA MULTIPLOS USUARIOS",
    "CERTIFICADO", "PAPEL PARA IMPRESSAO", "PAPEL A4", "PAPEL A4 SULFITE",
    "PAPEL A4 COR BRANCO", "PAPEL SULFITE", "SULFITE", "PENDAL", "E-BOOK",
    "COMPUTADOR", "COMPUTADOR COM ACESSO A INTERNET",
    "COMPUTADOR COM ACESSO A INTERNET E APLICATIVOS DE ESCRITORIO",
    "NOTEBOOK", "SMART TV", "PROJETOR MULTIMIDIA", "QUADRO BRANCO",
    "QUADRO DE VIDRO", "LOUSA DIGITAL", "LOUSA DIGITAL INTERATIVA",
    "LOUSA DE VIDRO MAGNETICA", "MOLDURA TOUCH SCREEN",
    "SOUNDBAR", "CAIXA DE SOM", "APAGADOR", "APAGADOR PARA QUADRO BRANCO",
    "CANETA", "CANETA ESFEROGRAFICA", "LAPIS", "LAPIS GRAFITE", "BORRACHA",
    "GRAMPEADOR", "PRANCHETA", "PASTA", "CADERNO", "ESTOJO PERSONALIZADO"
}

CABECALHOS_E_SECOES = {
    "CODIGO ITEM MXM", "CODIGO MXM", "CODIGO DO MXM", "CODIGO DO SEI",
    "DESCRICAO/ESPECIFICACAO DETALHADA", "DESCRICAO/ESPECIFI CACAO DETALHADA",
    "DESCRICAO/ESPECIFIC ACAO DETALHADA", "DESCR ICAO/",
    "DESCRICAO", "DESCRICAO DETALHADA", "DESCRICAO DO", "DESCRICAO DO REQUISITO",
    "DETALHADA", "ESPECIFICACAO", "ESPECIFICACOES",
    "U.M", "U MEDIDA", "QUANTIDADE POR ALUNO", "QUANTIDADE POR TURMA",
    "QUANTIDADE TOTAL DE ALUNOS", "TOTAL DE ALUNOS", "VALOR UNITARIO", "VALOR UNITARI",
    "VALOR TOTAL", "TOTAL", "PESO", "APROXIMADO DE", "TIPO DE FINANCIAMENTO", "TIPO DE FINANCIAMENT",
    "TIPO DE FINANCIAM", "INSUMOS", "UTENSILIOS", "EQUIPAMENTOS", "MOBILIARIO", "MATERIAIS",
    "MIDIA ESPECIALIZADA", "BANCO DE PRECOS", "ESTIMATIVA",
    "UNIFORMES", "MODO DE PREPARO", "INFRAESTRUTURA E LISTA BASICA1",
    "INFRAESTRUTURA E LISTA BASICA", "INDICADORES", "LISTA BASICA",
    "DADOS DA LISTA BASICA", "DADOS DO CURSO", "QUALIFICACAO PROFISSIONAL",
    "ULTIMA REVISAO", "UNIFORME", "DESCRICAO DO INGREDIENTE", "ITEM", "ITE M",
    "QUANTIDADE", "MEDIDA", "CATEGORIA", "NAO SE APLICA", "SENAC", "UNIDADE",
    "PACOTE", "CAIXA", "LATA", "VIDRO", "GARRAFA", "MACO", "RESMA", "FARDO",
    "POTE", "ROLO", "QTD TOTAL DE ALUNOS", "RESPONSAVEL- ELABORACAO",
    "RESPONSAVEL ELABORACAO", "DATA DE ELABORACAO", "RESPONSAVEL",
    "RESPONSAVEL - REVISAO", "SEGMENTO", "CARGA HORARIA", "TIPO", "CODIGO SIG",
    "AULAS PLANEJADAS", "PLANEJAMENTO DAS AULAS", "LANCAMENTO NO SEI",
    "PRODUCAO DE ALIMENTOS", "PROGRAMA SOCIOPROFISSIONAL",
    "HABILITACAO PROFISSIONAL TECNICA DE NIVEL MEDIO", "UNIDADE CURRICULAR",
    "UNIDADE(S) CURRICULAR(ES)", "UC", "UC/CH CURSO", "TURMA", "CURSO",
    "DOCENTE", "PLANO DE TRABALHO DOCENTE", "SITUACAO DE APRENDIZAGEM",
    "FICHA TECNICA DE PRODUCAO", "COORDENACAO PEDAGOGICA",
    "EIXO/SEGMENTO TECNOLOGICO", "WWW.DF.SENAC.BR", "HTTPS", "HTTP",
    "UNIDADE DE MEDIDA", "UNIDADE DE MEDIDIA", "UNIDADES", "UNIDADE EDUCACIONAL",
    "QUANTID", "QUANTIDA", "QUANTIDAD E", "RECURSO FINANCEIRO", "VOLTAGEM", "QUADRO",
    "APROX", "APROXIMADAMENTE", "APROXIMADAS", "MINIMA", "VOLUME MINIMO", "VOLUME",
    "SITUACAO PROBLEMA", "RECURSOS", "PERIODO", "CORES", "CONTENDO", "ADICIONAIS",
    "EAD SENAC", "REDE EAD SENAC", "EA D SENAC", "CARACTERISTICAS", "ESCRITA",
    "MOAGEM", "PORCOES INDIVIDUAIS", "NAO ATENDIDO", "METODO 1", "METODO 2",
    "METODO DIRETO RAPIDO", "METODO CESTINHA", "ALQUIMIA DOS ALIMENTOS",
    "SABORES DO BRASIL", "CORTES ARGENTINOS", "PADRAO LAGUNA", "LAGUNA",
    "LARGURA", "CONSUMO", "CAPACIDADE", "MEDIDAS", "BRUTO", "EDUCACIONAL",
    "NUMERO DE PAGINAS", "NUMERO MAXIMO DE VAGAS", "TURNO / HORARIO",
    "SENSIBILIDADE DE", "DOIS TEMPOS", "TEMPOS", "COR", "PAULO", "DUE DE",
    "VAL OR", "OBS", "APARENCIA", "UMIDADE", "ALIMENTOS", "BRASILIA", "JANEIRO", "DE JANEIRO",
    "REQUISITANTE", "ALCOOLICA", "GRAMATURA", "DRENADO", "DIAMETRO", "PRODUTO (AXLXP)",
    "AGU", "AGUE"
}

PADROES_RUIDO_REGEX = [
    r"\bAULA\b",
    r"^ATIVIDADES?\b",
    r"\(SEI\s*\d+\)",
    r"^\d+\s*H(?:ORAS)?$",
    r"^\d+\s*ALUNOS?$",
    r"^UC\s*\d+",
    r"^\d+\s+UNIDADE$",
    r"\bUNI\s+\d+\b",
    r"\bUNIDADE\s+\d+\b",
    r"R\$\s*\d+",
    r"\bCURRICULAR\d*\b",
    r"\bINFRAESTRUTURA E LISTA BASICA\d*\b|\bANO/ATUALIZACAO/VERSAO\b",
    r"\bAPLICAR BOAS\b|\bCOMPETENCIAS?\b|\bCRITERIOS?\b|\bMENCOES ADOTADAS\b",
    r"\bELABORACAO\s*[-–—]\s*RESPONSAVEL\b|\bELABORACAO/ATUALIZACAO\b",
    r"\bSIMILAR OU SUPERIOR\b|\bA MARCA\b|\bLOGOMARCA DA INSTITUICAO\b",
    r"\bUNIDADE(?:\s+\d+)?\s+SENAC\b|\bIMPRESSAO SENAC\b|\bFORMATIVAS\b|\bSENAC\b",
    r"^MEDIDA\s+\d+X\d+\b|^FORMATO\b|^TAMANHO\s+\d+\b|^TAMANHO UNICO\b",
    r"^PRECISAO ELETRONICA\b|^1 GRAMA A\b|^DE 1 GRAMA A\b|^GRAMA A\b",
    r"^CAPACIDADE\b|^MEDIDAS?\s+APROXIMADAS?\b|^DIMENSOES\b|^COMPRIMENTO\b",
    r"^ALTURA\b|^PROFUNDIDADE\b|^TENSAO\b|^VOLTAGEM\b|^REVESTIMENTO\b",
    r"^TRANSPARENTE OU BRANCO\b|^PONTA FINA\b|^AQUECIMENTO RAPIDO\b|^VEDACAO\b",
    r"\bAR CONDICIONADO\b|\bCARTEIRA UNIVERSITARIA\b|\bCERTIFICADO\b|\bMOLDURA TOUCH SCREEN\b",
    r"\b(?:CADEIRA DE|CADEIRA SECRETARIA|CADEIRA COM 4|MESA DE ESCRITORIO|MESA DO PROFESSOR|MESA ESCOLAR|MESA MULTIPLOS|COMPUTADOR COM ACESSO|LOUSA DIGITAL|APAGADOR PARA QUADRO|PAPEL A4|PAPEL SULFITE|CANETA ESFEROGRAFICA|LAPIS GRAFITE|CADERNO BROCHURA)\b",
    r"\b(?:PACOTE DE|PACOTE COM|PACOTE CONTENDO|PACOTE PLASTICO|PACOTES DE|PACOTES PLASTICOS|GARRAFA DE|GARRAFAS DE|GARRAFA PET|VIDRO DE|LATA DE|A GRANEL|EM GRANEL|GRANEL,|MEDIDO EM MACO|MEDIDA POR MACO|EM MACO|UNIDADE REQUISITANTE|UNIDADE DE COMPRA|DATA DE VALIDADE|PRAZO DE VALIDADE|RDC N|INMETRO|SEARA|PERDIGAO|SADIA|PARASITAS|LARVAS|APODRECIMENTO|DANOS FISICOS|PESANDO CERCA|PESANDO ENTRE|PESANDO APROXIMADAMENTE|GRADUACAO ALCOOLICA|TEOR ALCOOLICO|MIDIA ESPECIALIZADA|BANCO DE PRECOS)\b",
    r"\b(?:PLASTICO ATOXICO|PLASTICO TRANSPARENTE|PLASTICA, TRANSPARENTE|CAIXA DE PLASTICA|CAIXAS OU SACOS|CAIXA HERMETICAMENTE|LATA HERMETICAMENTE|LATA LIMPA|SACO DE VACUO|PLASTICO A VACUO|EMBALAGENS DE|EMBALADO EM|ACONDICIONAD[OA] EM|VENDIDO NO KG|COMERCIALIZAD[OA] EM KG|COMERCIALIZAD[OA] NO KG|COMERCIALIZADO POR KG|PRODUTO EM KG|PICADAS DE INSETOS|ODOR CARACTERISTICO|CHEIRO CARACTERISTICO|CARACTERISTICAS ORGANOLEPTICAS|CONTEM GLUTEN|CONTENDO ENTRE|CONFORME FABRICANTE|PERFEITA CONDICAO|UNIDADES DE VIDRO|MINISTERIO DA AGRICULTURA|ABNT NBR)\b",
    r"^(?:KG|MACO|PACOTE|UNIDADES?|PRODUTO)\s+\d+",
    r"\b(?:COZINHE|BATA|MISTURE|ADICIONE|RESERVE|HIGIENIZE|PENEIRE|MISTURAR|MEXA|LEVE AO FORNO|CORTE EM|DESCASQUE|REFOGUE|DEIXE DESCANSAR|RETIRAR A PECA|MONTAR ESTA CAIXA|PREPARAR OS FILES|FINZALIZAR|FINALIZAR)\b",
    r"\b(?:ATIVIDADE PRATICA|ATIVIDADE TEORICA|VISITA TECNICA|SITUACAO DE APRENDIZAGEM|PLANO DE TRABALHO|DESENVOLVIMENTO DE SOLUCOES|INTRODUCAO AO PI|PLANO DE NEGOCIO|ORGANIZA E HIGIENIZA|ORGANIZACAO E ESTRUTURA|PARA OFERTA A DISTANCIA|ORIENTACOES METODOLOGICAS|AMBIENTE PEDAGOGICO|JOGO DE QUEBRA CABECA|JOGO SOBRE OS TIPOS|JOGO DE PERGUNTAS|CAIXA SURPRESA LASANHA|PRATICA CERVEJAS|PRATICA VINHOS|PRATICA COQUETEIS|DRINKS NAO ALCOOLICOS|VINHOS BIODINAMICOS|DESTILADOS E COMPOSTOS)\b",
    r"\b(?:HTTPS?|WWW\.|AUTENTICIDADE DO DOCUMENTO|COORDENACAO PEDAGOGICA|EIXO/SEGMENTO|DEPARTAMENTO REGIONAL)\b",
    r"\b(?:VENDIDO POR UNIDADE|NAO SE APLICA|VARIACAO DE \d+%|INSTALACAO A CARGO|VALIDADE MINIMA|DATA DA ENTREGA)\b",
    r"\b(?:SERVICO NACIONAL DE APRENDIZAGEM|APRENDIZAGEM COMERCIAL|RESTAURANTE-ESCOLA)\b",
    r"\b(?:SAO PAULO|RIO DE JANEIRO|FORTALEZA|CEARA|ED\.|EDICAO|REIMP\.|EDITORA|CHEF PROFISSIONAL|SOU COZINHEIRO|SOU BARISTA|TECNOLOGIAS GERENCIAIS|COZINHAS PROFISSIONAIS|ALIMENTOS SEGUROS|MANUAL PRATICO|QUIMICA DOS BOLOS|HISTORIA DA ALIMENTACAO)\b",
    r"\b[A-Z]{3,},\s*[A-Z]\.",
    r"\bPLATAFORMA CACHOLA\b|\bANUARIO DE TECNOLOGIAS\b|\bMAPEAMENTO DE TECNOLOGIAS\b",
]


def classificar_item_utensilio(titulo: str, vocabulario_receitas: set[str]) -> str:
    if texto_corrompido_cid_ou_sobreposto(titulo):
        return "DESCARTAR"

    desc_upper = normalizar(titulo)

    if len(desc_upper) < 3 or not re.search(r"[A-Z]", desc_upper):
        return "DESCARTAR"

    if re.fullmatch(r"[\d\s.,/R$-]+", desc_upper):
        return "DESCARTAR"

    if re.fullmatch(r"ES\d+", desc_upper) or desc_upper.startswith("ES0"):
        return "DESCARTAR"

    if desc_upper in CABECALHOS_E_SECOES or desc_upper in INFRA_SALA_AULA_E_PAPELARIA:
        return "DESCARTAR"

    for padrao in PADROES_RUIDO_REGEX:
        if re.search(padrao, desc_upper):
            return "DESCARTAR"

    if len(desc_upper.split()) > 10:
        return "DESCARTAR"

    excecoes_utensilios = {
        "PAO DURO", "ESPATULA PAO DURO", "PAPEL MANTEIGA", "PAPEL ALUMINIO",
        "FORMA DE GELO", "FORMA PARA GELO", "FORMA DE BOLO", "FORMA DE TORTA",
        "FORMA DE EMPADA", "FORMA DE PIZZA", "FORMA DE PAO", "FORMA DE PUDIM",
        "FORMA DE CUPCAKE", "FORMA DE MUFFIN", "FORMA PARA CHOCOLATE",
        "TABUA DE CARNE", "TABUA PARA CARNE", "TABUA PARA LEGUMES",
        "FACA PARA PAO", "FACA PARA CARNE", "FACA PARA LEGUMES", "FACA PARA QUEIJO",
        "FACA PARA PEIXE", "FACA PARA SUSHI", "COLHER DE CAFE", "COLHER DE CHA",
        "COLHER DE SOPA", "COLHER DE ARROZ", "XICARA DE CAFE", "XICARA DE CHA",
        "COPO DE AGUA", "COPO PARA CERVEJA", "TACA DE VINHO", "TACA PARA ESPUMANTE",
        "TACA PARA AGUA", "TACA PARA CERVEJA", "MOEDOR DE CARNE", "MOEDOR DE PIMENTA",
        "MOEDOR DE SAL", "MOEDOR DE CAFE", "EXTRATOR DE SUCOS", "EXTRATOR DE FRUTAS",
        "PALITO DE CHURRASCO", "PALITO DE PIRULITO", "PALITO DE CANAPE",
        "CESTO PARA PAES", "SACO DE CONFEITAR", "SACO DE CONFEITAR DESCARTAVEL",
        "BICO DE CONFEITAR", "GARRAFA DE CHANTILLY", "SIFAO DE CHANTILLY",
        "AMACIADOR DE BIFE", "DESCAROCADOR DE AZEITONA", "DESCAROCADOR DE CEREJA",
        "CORTADOR DE PIZZA", "CORTADOR DE MASSA", "CORTADOR DE BISCOITO", "ROLO DE MASSA",
        "FILTRO DE CAFE", "SUPORTE PARA FILTRO DE CAFE", "MEXEDOR PARA DRINKS",
        "MEXEDOR DE CAFE", "AGUA SANITARIA", "ALCOOL ETILICO", "ALCOOL GEL",
        "BANHO MARIA", "PANELA BANHO MARIA", "GARFO DE SOBREMESA", "GARFO CHURRASCO",
        "DISPENSER PARA ALCOOL", "DEFUMADOR SMOKE GUN", "BALANCA COM IMPRESSORA INTEGRADA",
        "CARTAO LAMINADO DOURADO PARA SUPORTE DE TORTAS 22 CM",
        "ESPETINHOS DESCARTAVEIS PARA PETISCOS DE CRISTAL",
        "PISTILO PARA ARTESANATO", "PISTILO PARA FLORES", "TOPO DE BOLO",
        "FOLHA DE TRANSFER", "VIDRO PARA CONSERVA", "PEDRA PARA AMOLAR",
        "LIXEIRA INDUSTRIAL", "LIXEIRA COM PEDAL", "SAQUINHO DE DIM DIM",
        "TOALHA DE MESA", "SUPORTE PLASTICO PARA BOLO DE ANDAR",
        "CENTRO DE MESA", "ACETATO PARA CONFEITARIA"
    }
    if any(exc in desc_upper for exc in excecoes_utensilios):
        return "UTENSILIO_CONFIRMADO"

    if desc_upper in vocabulario_receitas:
        return "DESCARTAR"

    if REGEX_ALIMENTOS_PROIBIDOS.search(desc_upper):
        return "DESCARTAR"

    if REGEX_SINAIS_UTENSILIO.search(desc_upper) or REGEX_MATERIAIS_UTENSILIO.search(desc_upper):
        return "UTENSILIO_CONFIRMADO"

    return "SUSPEITO"


# ============================================================
# 4. EXTRAÇÃO DAS TABELAS E FICHAS TÉCNICAS
# ============================================================

CONFIG_TABELAS_BLINDADA = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "text_x_tolerance": 1.2,
    "text_y_tolerance": 2,
}


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
    marcadores_nao_lista = [
        "QTD TOTAL DE ALUNOS", "DADOS DO CURSO", "PLANEJAMENTO DAS AULAS",
        "AULAS PLANEJADAS", "ELEMENTOS DA COMPETENCIA",
        "ORGANIZACAO CURRICULAR", "BIBLIOGRAFIA", "SITUACAO DE APRENDIZAGEM"
    ]
    return any(m in amostra for m in marcadores_nao_lista)


def extrair_melhor_candidato_descricao(valores: list[str], idx_preferencial: int | None = None) -> str:
    if idx_preferencial is not None and idx_preferencial < len(valores):
        val_pref = valores[idx_preferencial]
        if val_pref and len(normalizar(val_pref)) >= 3:
            return val_pref

    ignorados = CABECALHOS_E_SECOES | {
        "NAO SE APLICA", "SENAC", "MIDIA ESPECIALIZADA", "BANCO DE PRECOS", "ESTIMATIVA",
        "KG", "UNI", "PCT", "MC", "CX", "RL", "LITRO", "UNIDADE", "PACOTE", "MACO", "LATA", "GARRAFA"
    }
    candidatos = []

    for v in valores:
        if not v:
            continue
        v_norm = normalizar(v)
        if len(v_norm) < 3 or v_norm in ignorados:
            continue
        if re.fullmatch(r"[\d.,R$\s/-]+", v_norm):
            continue
        if re.fullmatch(r"(?:ES|E2|20)\d{5,}", v_norm):
            continue
        candidatos.append(v)

    if not candidatos:
        return ""

    com_dois_pontos = [c for c in candidatos if ":" in c]
    if com_dois_pontos:
        return com_dois_pontos[0]

    return candidatos[0]


def consolidar_linhas_quebradas_tabela(tabela: list[list[str]]) -> list[list[str]]:
    linhas_consolidadas = []
    buffer_texto = []

    marcadores_linha_completa = (
        r"\b(?:KG|UNIDADE|UNI|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
        r"LITRO|PECA INTEIRA|PECA|BANDEJA|PAR|JOGO|JG|CJ|CONJUNTO|NAO SE APLICA|SENAC|"
        r"MIDIA ESPECIALIZADA|BANCO DE PRECOS|ESTIMATIVA)\b|R\$"
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
        texto_pag = pagina.extract_text(x_tolerance=1.2) or ""
        texto_pag_norm = normalizar(texto_pag)
        if "DESCRICAO DO INGREDIENTE" not in texto_pag_norm and "FICHA TECNICA" not in texto_pag_norm:
            continue

        tabelas = pagina.extract_tables(table_settings=CONFIG_TABELAS_BLINDADA) or []
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

                if "MODO DE PREPARO" in texto_linha_norm or "RENDIMENTO" in texto_linha_norm:
                    em_tabela_ingredientes = False
                    continue

                if em_tabela_ingredientes:
                    candidato = extrair_melhor_candidato_descricao(valores, idx_preferencial=idx_ingrediente)
                    nome = extrair_nome_utensilio_limpo(candidato)
                    if nome and len(normalizar(nome)) >= 3:
                        encontrados.append(nome)

    return encontrados


def construir_vocabulario_global_receitas(arquivos_pdf: list[Path]) -> set[str]:
    vocabulario = set()
    total = len(arquivos_pdf)
    print(f"Passada 1/2: Mapeando vocabulário de ingredientes (para exclusão) em {total} PDFs...")

    for idx, caminho_pdf in enumerate(arquivos_pdf, start=1):
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                for item in extrair_itens_fichas_pdf(pdf):
                    nome_norm = normalizar(item)
                    if len(nome_norm) >= 3 and nome_norm not in CABECALHOS_E_SECOES:
                        vocabulario.add(nome_norm)
        except Exception:
            pass

        if idx % 10 == 0 or idx == total:
            print(f"  -> Vocabulário mapeado: {idx}/{total} arquivos...")

    print(f"Vocabulário de ingredientes construído com {len(vocabulario)} termos únicos.\n")
    return vocabulario


def _registrar_candidato_utensilio(
    candidato: str,
    nome_curso_norm: str,
    vocabulario_receitas: set[str],
    utensilios: list[str],
    suspeitos: list[str],
) -> None:
    nome_utensilio = extrair_nome_utensilio_limpo(candidato)
    norm_utensilio = normalizar(nome_utensilio)

    if not nome_utensilio or norm_utensilio == nome_curso_norm or norm_utensilio in nome_curso_norm:
        return

    status_item = classificar_item_utensilio(nome_utensilio, vocabulario_receitas)

    if status_item == "UTENSILIO_CONFIRMADO":
        if not any(normalizar(x) == norm_utensilio for x in utensilios):
            utensilios.append(nome_utensilio)
    elif status_item == "SUSPEITO":
        if not any(normalizar(x) == norm_utensilio for x in suspeitos):
            suspeitos.append(nome_utensilio)


def extrair_utensilios_pdf(
    pdf, nome_curso: str, vocabulario_receitas: set[str]
) -> tuple[list[str], list[str], bool]:
    utensilios = []
    suspeitos = []
    nome_curso_norm = normalizar(nome_curso)
    na_lista_basica = False
    tem_cid = False

    marcadores_unidade_lista = (
        r"\b(?:KG|UNIDADE|UNI|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
        r"LITRO|PECA|BANDEJA|PAR|JOGO|JG|CJ|CONJUNTO|NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|"
        r"BANCO DE PRECOS|ESTIMATIVA)\b|R\$|ES0"
    )

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text(x_tolerance=1.2) or ""
        if "(cid:" in texto_pag.lower():
            tem_cid = True

        texto_pag_norm = normalizar(texto_pag)

        tem_marcador_lista = (
            "LISTA BASICA" in texto_pag_norm
            or ("DADOS DA LISTA" in texto_pag_norm and "BASICA" in texto_pag_norm)
            or bool(re.search(r"\b(?:UTENSILIOS|EQUIPAMENTOS|MOBILIARIO|MATERIAIS)\b", texto_pag_norm))
            or "DESCRICAO/ESPECIFICACAO" in texto_pag_norm
            or "CODIGO ITEM MXM" in texto_pag_norm
        )

        if tem_marcador_lista:
            na_lista_basica = True

        if not na_lista_basica and not tem_marcador_lista:
            continue

        achou_na_pagina = False
        tabelas = pagina.extract_tables(table_settings=CONFIG_TABELAS_BLINDADA) or []

        for tabela in tabelas:
            if not tabela or tabela_e_de_metadados_ou_cronograma(tabela):
                continue

            amostra_tab = normalizar(" ".join(limpar_texto(c) for l in tabela[:3] for c in (l or []) if c))
            if "DESCRICAO DO INGREDIENTE" in amostra_tab:
                continue

            linhas_tratadas = consolidar_linhas_quebradas_tabela(tabela)
            idx_desc = None

            for valores in linhas_tratadas:
                texto_linha_norm = normalizar(" ".join(v for v in valores if v))
                if any(h in texto_linha_norm for h in ("CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO")):
                    idx_desc = identificar_indice_coluna_descricao(valores)
                    continue

                candidato = extrair_melhor_candidato_descricao(valores, idx_preferencial=idx_desc)
                antes_ut = len(utensilios)
                antes_susp = len(suspeitos)
                _registrar_candidato_utensilio(
                    candidato, nome_curso_norm, vocabulario_receitas, utensilios, suspeitos
                )
                if len(utensilios) > antes_ut or len(suspeitos) > antes_susp:
                    achou_na_pagina = True

        if not achou_na_pagina and tem_marcador_lista:
            for linha in texto_pag.splitlines():
                linha_limpa = limpar_texto(linha)
                norm_linha = normalizar(linha_limpa)
                if not norm_linha or any(h in norm_linha for h in ("CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO", "VALOR TOTAL")):
                    continue
                if re.search(marcadores_unidade_lista, norm_linha):
                    _registrar_candidato_utensilio(
                        linha_limpa, nome_curso_norm, vocabulario_receitas, utensilios, suspeitos
                    )

    if not utensilios:
        for susp in list(suspeitos):
            if REGEX_SINAIS_UTENSILIO.search(normalizar(susp)) or REGEX_MATERIAIS_UTENSILIO.search(normalizar(susp)):
                utensilios.append(susp)
                suspeitos.remove(susp)

        for pagina in pdf.pages:
            for tabela in pagina.extract_tables(table_settings=CONFIG_TABELAS_BLINDADA) or []:
                for linha in tabela or []:
                    for cel in linha or []:
                        if not cel:
                            continue
                        nome_cand = extrair_nome_utensilio_limpo(cel)
                        norm_cand = normalizar(nome_cand)
                        if not nome_cand or norm_cand in nome_curso_norm:
                            continue
                        if classificar_item_utensilio(nome_cand, vocabulario_receitas) == "UTENSILIO_CONFIRMADO":
                            if not any(normalizar(x) == norm_cand for x in utensilios):
                                utensilios.append(nome_cand)

            texto_pag = pagina.extract_text(x_tolerance=1.2) or ""
            for linha in texto_pag.splitlines():
                linha_limpa = limpar_texto(linha)
                if re.search(r"\b(?:\d+(?:[.,]\d+)?\s*(?:uni|un|pct|cx|par|jogo|jg|cj)|ES\d{6,})\b", linha_limpa, re.IGNORECASE):
                    nome_cand = extrair_nome_utensilio_limpo(linha_limpa)
                    norm_cand = normalizar(nome_cand)
                    if not nome_cand or norm_cand in nome_curso_norm:
                        continue
                    if classificar_item_utensilio(nome_cand, vocabulario_receitas) == "UTENSILIO_CONFIRMADO":
                        if not any(normalizar(x) == norm_cand for x in utensilios):
                            utensilios.append(nome_cand)

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

    vocabulario_receitas = construir_vocabulario_global_receitas(arquivos_pdf)

    total_erros = 0
    total_geral_utensilios = 0
    relatorio = []
    todos_suspeitos = []

    print("Passada 2/2: Extraindo e classificando utensílios/equipamentos de todos os cursos...")

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
                        pdf, nome_curso, vocabulario_receitas
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

    print("\n========== EXTRAÇÃO CONCLUÍDA ==========")
    print(f"Total de PDFs processados: {len(arquivos_pdf)}")
    print(f"Erros: {total_erros}")
    print(f"Total geral de utensílios/equipamentos confirmados: {total_geral_utensilios}")
    print(f"Itens na fila de revisão (zona cinzenta): {len(todos_suspeitos)}")
    print(f"\nArquivo principal: {ARQUIVO_SAIDA}")
    print(f"Arquivo de revisão: {ARQUIVO_REVISAO}")


if __name__ == "__main__":
    main()