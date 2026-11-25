import csv
import re
import unicodedata
from itertools import zip_longest
from pathlib import Path
import pdfplumber

# ============================================================
# 1. CONFIGURAÇÕES GERAIS
# ============================================================

BASE = Path(__file__).resolve().parent

PASTA_PDFS = BASE / "OneDrive_2026-10-28" / "Dados para ETL - Cozinha"
PASTA_RESULTADOS = BASE / "resultados"

ARQUIVO_SAIDA = PASTA_RESULTADOS / "cursos_insumos_e_utensilios_final.csv"
ARQUIVO_RELATORIO = PASTA_RESULTADOS / "relatorio_extracao_unificado.csv"
ARQUIVO_REVISAO = PASTA_RESULTADOS / "itens_suspeitos_revisao_unificado.csv"

CONFIG_TABELAS_BLINDADA = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "text_x_tolerance": 1.2,
    "text_y_tolerance": 2,
}

# ============================================================
# 2. INFRAESTRUTURA COMUM (NORMALIZAÇÃO, TABELAS E NOME DO CURSO)
# ============================================================

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


def texto_corrompido_cid_ou_sobreposto(texto: str, modo_utensilio: bool = False) -> bool:
    if not texto:
        return True
    low = texto.lower()
    if "(cid:" in low or "(cid" in low:
        return True
    texto_upper = texto.upper()

    palavras_todas = re.findall(r"\b[A-Z0-9ÁÉÍÓÚÂÊÔÃÕÇ]{1,2}\b", texto_upper)
    stop_curtas = {"DE", "DA", "DO", "EM", "AO", "OS", "AS", "UM", "E", "A", "O", "G", "L", "ML", "KG", "UN", "CX", "MC", "RA"}
    if modo_utensilio:
        stop_curtas |= {"CM", "MM", "V", "W", "N", "PE"}

    tokens_estranhos = [t for t in palavras_todas if t not in stop_curtas and not t.isdigit()]
    if len(tokens_estranhos) >= 2:
        return True

    if re.search(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}[.,;][A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}", texto_upper):
        return True

    if re.search(r"\b[A-Z]\d+\b|\b\d+[A-Z]\b", texto_upper):
        if not (modo_utensilio and re.search(r"\b(?:110V|220V|127V|V60|A4)\b", texto_upper)):
            return True

    excecoes_dobradas = {
        "CIBOULETTE", "CEBOULLETE", "MOZZARELLA", "CAPPUCCINO", "PROSCIUTTO", "PANNA",
        "COTTA", "AMARETTO", "CARPACCIO", "FETTUCCINE", "TAGLIATELLE", "PAPPARDELLE",
        "RICOTTA", "STRACCIATELLA", "BURRATA", "BITTER", "STPIERRE",
        "AEROPRESS", "PITCHER", "STRAINER", "MUDDLER", "CUTTER", "CHINOIS",
        "MANDOLINE", "SOUSPLAT", "GUERIDON", "RECHAUD", "RAMEQUIN", "RAMEQUINS",
        "SOUNDBAR", "GLASS", "COFFEE", "PRESS", "SPOON", "JIGGER", "SHAKER",
        "TAMPER", "VAPOREIRA", "CUSCUZEIRA", "CAFETEIRA", "FRIGIDEIRA",
        "BATEDEIRA", "SORVETEIRA", "MASSEIRA", "MASSEIRAS", "SELADORA",
        "IMPRESSORA", "CLASSICA", "SAQUINHOS", "SAQUINHO"
    }

    palavras = re.findall(r"[A-ZÀ-Ú]{4,}", texto_upper)
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
            if not (modo_utensilio and re.search(r"(?:110V|220V|127V|CM|MM|V60)", tok)):
                return True
        if len(tok) >= 10:
            vogais = len(re.findall(r"[AEIOUÁÉÍÓÚÂÊÔÃÕ]", tok))
            if vogais == 0 or (vogais / len(tok)) < 0.22:
                return True

    return False


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
        nome_limpo = re.sub(
            r"[-–—]?\s*\b\d+\s*(?:horas?|hs?|h/a)\b",
            "",
            caminho_pdf.stem.replace("-", " ").replace("_", " "),
            flags=re.IGNORECASE,
        )
        if ano:
            nome_limpo = re.sub(rf"[-–—]?\s*\b{ano}\b", "", nome_limpo)
        nome_limpo = re.sub(r"\s+", " ", nome_limpo).strip(" -–—_\"“”'.")

    return f"{nome_limpo} ({ano})" if ano else nome_limpo


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


# ============================================================
# 3. MÓDULO ISOLADO DE INSUMOS (INGREDIENTES)
# ============================================================

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
    "AGUACOMGAS": "AGUA COM GAS",
    "CEREJAAMARENA": "CEREJA AMARENA",
    "AGARAGAR": "AGAR AGAR",
    "ALGINATODESODIO": "ALGINATO DE SODIO",
    "ANGOSTURABITTERAROMATICO": "ANGOSTURA BITTER AROMATICO",
    "APEROLAPERITIVO": "APEROL APERITIVO",
    "BALADEGENGIBRE": "BALA DE GENGIBRE",
    "BITTERCAMPARIITALIANO": "BITTER CAMPARI ITALIANO",
    "CACACA BRANCA": "CACHACA BRANCA",
    "CACHACABRANCA(YPIOCA)": "CACHACA BRANCA",
    "CAFEEMGRAOS": "CAFE EM GRAOS",
    "CANELAEMPAU": "CANELA EM PAU",
    "CANELAEMCASCA": "CANELA EM CASCA",
    "CAPSULADECAFEEXPRESSODOLCEGUSTO": "CAPSULA DE CAFE EXPRESSO DOLCE GUSTO",
    "CAPSULA DE CAFEESPRESSO DOLCEGUSTO": "CAPSULA DE CAFE EXPRESSO DOLCE GUSTO",
    "CLORETODECALCIO": "CLORETO DE CALCIO",
    "LICORCREMEDECACAU": "LICOR CREME DE CACAU",
    "FERNETBRANCA": "FERNET BRANCA",
    "FRAMBOESAINNATURA": "FRAMBOESA IN NATURA",
    "GASPARASIFAOCHANTILLY": "GAS PARA SIFAO CHANTILLY",
    "GINGERALE(STPIERRE)": "GINGER ALE",
    "GOMAXANTANA": "GOMA XANTANA",
    "LARANJABAHIA": "LARANJA BAHIA",
    "LARANJAPERA": "LARANJA PERA",
    "LECITINADESOJA": "LECITINA DE SOJA",
    "LICORBAILEYS": "LICOR BAILEYS",
    "LICORDEAMENDOAS(DISARONNO)": "LICOR DE AMENDOAS",
    "LICORDECAFE(KAHLUA)": "LICOR DE CAFE",
    "LICORDEPESSEGO(PEACHTREE)": "LICOR DE PESSEGO",
    "LICORTRIPLESEC(COINTREAU)": "LICOR TRIPLE SEC",
    "MACAPERA": "MACA PERA",
    "MANJERICAOBASILICO": "MANJERICAO BASILICO",
    "MAJERICAO": "MANJERICAO",
    "CEBOULLETE": "CIBOULETTE",
    "AL COOL DE CEREAIS": "ALCOOL DE CEREAIS",
    "MOLHODEPIMENTA": "MOLHO DE PIMENTA",
    "MOLHOINGLES": "MOLHO INGLES",
    "NOZMOSCADA": "NOZ MOSCADA",
    "PIMENTADEDODEMOCA": "PIMENTA DEDO DE MOCA",
    "REFRIGERANTEDELIMAO": "REFRIGERANTE DE LIMAO",
    "RUMBRANCO(BACARDI)": "RUM BRANCO",
    "RUMDECOCO(MALIBU)": "RUM DE COCO",
    "RUMENVELHECIDO(BACARDIANEJO)": "RUM ENVELHECIDO",
    "SUCODETOMATE": "SUCO DE TOMATE",
    "VERMOUTHDRY(MARTINI)": "VERMOUTH DRY",
    "VERMOUTHROSSO(CARPANO)": "VERMOUTH ROSSO",
    "VODKAPREMIUM(KETELONE)": "VODKA PREMIUM",
    "WHISKEYAMERICANO(JIMBEAM)": "WHISKEY AMERICANO",
    "WHISKEYIRLANDES(JAMESON)": "WHISKEY IRLANDES",
    "WHISKYESCOCESBLENDED(JHONNIEWALKER)": "WHISKEY ESCOCES BLENDED",
    "XAROPEDEFRAMBOESA": "XAROPE DE FRAMBOESA",
    "XAROPEDEGENGIBRE": "XAROPE DE GENGIBRE",
    "XAROPEGRENADINE": "XAROPE GRENADINE",
    "PIMENTADOREINOPRETAEMGRAO": "PIMENTA DO REINO PRETA EM GRAO",
    "PIMENTADOREINOBRANCAEMGRAO": "PIMENTA DO REINO BRANCA EM GRAO",
    "PIMENTADOREINOPRETAEM PO": "PIMENTA DO REINO PRETA EM PO",
    "TOMATEPELADO": "TOMATE PELADO",
    "VINHOBRANCOSECO": "VINHO BRANCO SECO",
    "SORVETEDECREME": "SORVETE DE CREME",
    "TAMBAQUEI INTEIRO EVISCERADO": "TAMBAQUI INTEIRO EVISCERADO",
}

TERMOS_PROIBIDOS_INSUMOS = {
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
    "ENSACADOR MANUAL", "CARRINHO COM RODAS", "GUERIDON", "SMART TV", "NOTEBOOK",
    "CHURRASQUEIRA", "ADEGA", "CUTTER", "TRITURADOR DE ALIMENTOS",
    "PINCA", "PINCAS", "PEGADOR", "PEGADORES", "ROLO LAMINADOR", "CORTADOR", "CORTADORES",
    "ARO", "AROS", "PIRES", "PLACA DE CORTE", "PLACAS DE ETILENO", "PORTA CONDIMENTO",
    "POTE HERMETICO", "POTE BISNAGA", "BISNAGA", "RALADOR", "ZESTER",
    "SERINGA", "SIFAO", "SPEED RAIL", "STOREN POUR", "SUPORTE PARA PLACAS",
    "SUPORTE DE PAS", "SUPORTE PARA FILTRO", "TAPETE DE SILICONE", "SERVICE MAT",
    "TESOURA", "TRAVESSA", "BOWL", "BOWLS", "BOWLL", "CAIXA PLASTICA", "CAIXA TERMICA",
    "CONTENTOR", "CHAIRA", "DESCASCADOR", "ESCUMADEIRA", "FOUET", "FUNIL",
    "MANDOLINE", "MANDOLIN", "MOEDOR", "PEDRA DE AFIAR", "ESPATULA", "PA PARA",
    "GRADE", "FORMA", "FORMAS", "FORMINHA", "FORMINHAS", "TABUA", "TABUAS", "FACA", "FACAS",
    "BARRA MAGNETICA", "PANELA", "PANELAS", "FRIGIDEIRA", "CALDEIRAO", "ASSADEIRA",
    "TIGELA", "CUBA", "CUBAS", "CONCHA", "ESCORREDOR", "PENEIRA", "COLHER", "COLHERES",
    "GARFO", "GARFOS", "PRATO", "PRATOS", "COPO", "COPOS", "XICARA", "XICARAS",
    "TACA", "TACAS", "JARRA", "TERMOMETRO", "BALANCA", "MEDIDOR", "MEDIDORES",
    "MEDIDORA", "AZEITEIRO", "RECIPIENTE", "DISPENSADOR", "RAMEQUIN", "RAMEQUINS",
    "BACIA", "MANDUCA", "ABRIDOR", "BORRIFADOR", "CHALEIRA", "BULE", "GALHETEIRO",
    "BICO DE CONFEITAR", "BICOS PARA CONFEITAR", "BICO PITANGA", "ADAPTADOR", "BAILARINA",
    "BAILARINAS", "BAILHARINAS", "PINCEL CULINARIO", "ROLO DE MASSA",
    "CARRETILHA", "VAZADOR", "BOLEADOR", "DESCAROCADOR", "ESPREMEDOR", "AMASSADOR",
    "SOCADOR", "COQUETELEIRA", "DOSADOR", "MUDDLER", "PASSADOR", "CHINOIS",
    "TAMIS", "CUSCUZEIRA", "VAPOREIRA", "CHAPA", "GRELHA", "ESPETO", "GANCHO",
    "BATEDOR MANUAL", "BATEDOR ESPIRAL", "CUTELO", "RASPADOR", "CRONOMETRO", "REFIL GAS",
    "WOK", "CANECA DE COBRE", "CESTO PARA PAES", "CLOCHE", "COADOR", "STRAINER",
    "DECANTER", "GARRAFA TERMICA", "MACERADOR", "RECHAUD", "SOUSPLAT", "VACUO VINS",
    "JOGO AMERICANO", "PANO COBRE MANCHAS", "ARCO DE SERRA", "BAR CADDY",
    "CAVIAR BOX", "LICOREIRA", "MINI PITCHER", "MOLDE STENCIL", "PICOLETEIRA",
    "CUSPIDEIRA", "CHAWAM", "TACHO", "AEROPRESS", "AMPOLAS", "BISTURI", "LEITEIRA",
    "MEXEDOR PARA DRINKS", "CORPO DE VIDRO", "PITCHER", "TAMPER", "BATE BORRA",
    "SACARROLHA", "TORTEIRA", "GAZE",
    "FIBRA SINTETICA", "FIBRACO", "FOSFORO", "HIPOCLORITO", "MASCARA",
    "PANO MULTIUSO", "PANO DE PRATO", "PANO PARA LIMPEZA", "PAPEL ALUMINIO",
    "POTE COM TAMPA", "SACO PLASTICO", "SACO DE LIXO", "SABONETE", "TOUCA",
    "BANDEJA", "APAGADOR", "PAPEL A4", "SULFITE", "PINCEL", "ALCOOL",
    "ALCOOL ETILICO", "AGUA SANITARIA", "PAPEL TOALHA", "ESCOVA DE LIMPEZA",
    "ESCOVA PARA LIMPEZA", "AVENTAL", "CALCA", "CAMISETA", "CAMISA SOCIAL",
    "COLETE ADULTO", "GRAVATA", "GRAVADA", "DOLMA", "SAPATO", "BOTA", "JALECO",
    "JAPONA", "LUVA", "ESPONJA", "DETERGENTE", "DESINFETANTE", "VASSOURA",
    "RODO", "LIXEIRA", "FILME PVC", "PAPEL MANTEIGA", "PAPEL FILME", "GUARDANAPO",
    "PALITO DE BAMBU", "PALITODEBAMBU", "PALITO DE DENTE", "PALITO DE CHURRASCO",
    "PALITO DE PIRULITO", "PALITO DE CANAPE", "PALITO GUARDA SOL", "PAPEL CHUMBO",
    "ROLO DE FITILHO", "SACO TRANSPARENTE PARA PIRULITO", "FOLHA DE TRANSFER",
    "ALGODAO", "BOBINA", "SACO DE CONFEITAR", "CERTIFICADO", "ETIQUETA ADESIVA",
    "ETIQUETA", "MARMITEX", "EMBALAGEM", "CAIXA DE PAPELAO", "BARBANTE", "ISQUEIRO",
    "CANETA", "LAPIS", "BORRACHA", "GRAMPEADOR", "PRANCHETA", "PASTA", "CADERNO",
    "ESTOJO PERSONALIZADO", "FILTRO DE PAPEL", "FILTROPAPEL", "FILTROPAPELV60103",
    "FILTRO EMBUTIDO", "FILTRO KALITA", "CANUDO", "ISOPOR", "TOPO DE BOLO",
    "PISTILO PARA ARTESANATO", "PISTILO PARA FLORES", "VOAL", "PAPEL PARA IMPRESSAO",
    "LOUSA DE VIDRO MAGNETICA", "MOLDURA TOUCH SCREEN", "SOUNDBAR", "LENHA",
    "BANCADA", "BANCADAS", "MESA", "CADEIRA", "ARMARIO", "CARTEIRA UNIVERSITARIA",
    "SOFTWARE", "EQUIPAMENTO", "UTENSILIO", "PENDAL"
}

REGEX_MATERIAIS_E_MEDIDAS_UTENSILIO = re.compile(
    r"\b(?:INOX|INOXIDAVEL|ACO INOX|SILICONE|POLIETILENO|POLIPROPILENO|ALUMINIO|"
    r"VIDRO TEMPERADO|CERAMICA|PORCELANA|LOUCA|MADEIRA|BAMBU|PLASTICO|PVC|TEFLON|"
    r"ANTIADERENTE|ACRILICO|NYLON|COBRE|110V|220V|127V|BIVOLT|WATTS|CM|MM|POLEGADAS|"
    r"MALHA FINA|CABO BRANCO|CABO PRETO|CABO VERMELHO|CABO VERDE|CABO AZUL|"
    r"CABO AMARELO|DESCARTAVEL|OCUPACIONAL|ISOPOR|ARTESANATO|TRAMONTINA|METVISA|CISPER|"
    r"LAVAR LOUCAS|COMPRESSOR|PRATELEIRAS|ERGOMETRICA|EPOXI|ESTANHO|ESPUMA INJETADA|"
    r"TAMPO SUPERIOR|FRIGORIFICA|EXAUSTAO)\b"
)

REGEX_SINAIS_ALIMENTO = re.compile(
    r"\b(?:ACUCAR|SAL|OLEO|AZEITE|FARINHA|FERMENTO|BICARBONATO|BICABORNATO|LEITE|"
    r"MANTEIGA|MARGARINA|CREME DE LEITE|NATA|QUEIJO|QUEJO|MOZZARELLA|MUCARELA|GORGONZOLA|"
    r"FIOR DI LATTE|BURRATA|RICOTA|CHEDDAR|REQUEIJAO|CATUPIRY|PARMESAO|COALHO|PROVOLONE|"
    r"OVO|OVOS|GEMA|GEMAS|CLARA|CLARAS|CARNE|FRANGO|GALINHA|PEIXE|CAMARAO|CAMAROES|"
    r"BACON|GUANCIALE|PANCETTA|LINGUICA|PRESUNTO|CHARQUE|ALCATRA|PATINHO|FILE|MIGNON|"
    r"CONTRAFILE|COSTELA|COSTELINHA|LOMBO|PERNIL|BISTECA|CUPIM|MUSCULO|ACEM|PICANHA|"
    r"MAMINHA|FRALDINHA|COXAO|LAGARTO|DIAFRAGMA|MIOLO DE ANCHO|PALETA DE CORDEIRO|"
    r"MAGRET|PERU|ROBALO|TILAPIA|PESCADA|SARDINHA|ATUM|BACALHAU|POLVO|LULA|MEXILHAO|"
    r"KANI KAMA|QUARTO TRASEIRO|QUARTO DIANTEIRO|PONTA DE AGULHA|COELHO|GALETO|SUINO|"
    r"CORDEIRO|CABRITO|T-BONE|TAMBAQUI|TAMBAQUEI|RA INTEIRA|TRIPA|DAMASCO|ESCAROLA|"
    r"REFRIGERANTE|ABSINTO|SAKE|SAQUE|SOJU|PISCO|FERNET|BRANDY|GRAPPA|COGNAC|GINGER ALE|"
    r"TIQUIRA|OUZO|ST GERMAIN|ARAK|PALETA|TENDER|FIGO|FIGOS|CEREJA|CEREJAS|BATATA|BATATAS|"
    r"CEBOLA|CEBOLAS|ALHO|ALHOS|SALSAO|ADOCANTE|XILITOL|GIN|AMARO|ANGOSTURA|CACHACA|"
    r"PLYMOUTH|REDESTILADO|LONDON DRY|FRANGELICO|TEQUILA|AGAVE|VINHO|VINHOS|LINGUADO|"
    r"FIGADO|CORACAO DE BOI|BANHA|SALAME|SALMAO|ACELGA|NABO|NIRA|PAK CHOI|SHARI|"
    r"ANIS|ESTRELADO|DENDE|CHEIRO VERDE|COENTRO|COLORAU|COMINHO|LOURO|LEITE DE COCO|"
    r"PALMITO|CAPIM SANTO|CARA|MANJERICAO|MAJERICAO|CEVADA|SEMOLINA|AMORA|AMORAS|"
    r"ERVA CIDREIRA|CEBOLETE|CIBOULETTE|CEBOULLETE|GROSELHA|CASSIS|GRENADINE|"
    r"ARROZ|FEIJAO|MACARRAO|SPAGHETTI|MASSA|FUBA|AMIDO|POLVILHO|AVEIA|TRIGO|MILHO|"
    r"CANJICA|CUSCUZ|SOJA|TOFU|LENTILHA|GRAO DE BICO|QUINOA|ALCACHOFRA|BROTO|ALFAFA|"
    r"TOMATE|CENOURA|BETERRABA|ABOBORA|ABOBRINHA|MANDIOCA|AIPIM|INHAME|PIMENTAO|"
    r"ALFACE|COUVE|REPOLHO|ESPINAFRE|RUCULA|AGRIAO|CHICORIA|BROCOLIS|COUVE-FLOR|"
    r"BERINJELA|CHUCHU|QUIABO|VAGEM|PEPINO|RABANETE|ASPARGO|SALSA|SALSINHA|CEBOLINHA|"
    r"HORTELA|ALFAVACA|ALECRIM|TOMILHO|OREGANO|ENDRO|DILL|CANELA|CRAVO|PIMENTA|"
    r"CURCUMA|ACAFRAO|PAPRICA|NOZ MOSCADA|GENGIBRE|BAUNILHA|ESSENCIA|CORANTE|CMC|"
    r"CARBOXIMETILCELULOSE|LIGA NEUTRA|DESMOLDANTE|SUMAGRE|SUMAC|CUMARU|CARDAMOMO|"
    r"ERVA DOCE|ERVAS|CREME TARTARO|GLUTAMATO|FUMAÇA LIQUIDA|FUMACA LIQUIDA|"
    r"BANANA|MACA|LARANJA|LIMAO|ABACAXI|MAMAO|MANGA|MORANGO|UVA|MARACUJA|COCO|"
    r"MELANCIA|MELAO|ABACATE|AVOCADO|GOIABA|GOIABADA|PESSEGO|AMEIXA|CAJU|ACEROLA|"
    r"TANGERINA|MEXERICA|KIWI|AMARENA|FRAMBOESA|MIRTILO|MIRTILOS|PEQUI|POLPA|"
    r"CHOCOLATE|CACAU|MEL|MELADO|GLICOSE|GELATINA|CHANTILLY|DOCE DE LEITE|"
    r"LEITE CONDENSADO|BOMBOM|GRANULADO|SORVETE|PO DOURADO|PO PEROLADO|PO COBRE|"
    r"FOLHAS DE OURO|FLOR COMESTIVEL|VINAGRE|ACETO|SHOYU|MOSTARDA|KETCHUP|MAIONESE|"
    r"EXTRATO DE TOMATE|MOLHO|CREME BALSAMICO|AZEITONA|AZEITONAS|ALCAPARRA|ALCAPARRAS|"
    r"CHAMPIGNON|COGUMELO|FUNGHI|ERVILHA|ERVILHAS|ESPUMANTE|CERVEJA|RUM|CONHAQUE|"
    r"LICOR|APEROL|BITTER|CAMPARI|VERMOUTH|VERMUTE|VODKA|WHISKY|WHISKEY|XAROPE|SUCO|"
    r"CAFE|CHA|AGUA|GELO|PAO|BAGUETE|TORRADA|BISCOITO|BOLACHA|CASTANHA|NOZES|"
    r"AMENDOA|AMENDOAS|AMENDOIM|AVELA|PISTACHE|UVA PASSA|FRUTOS SECOS|CURRY|"
    r"MIREPOIX|ROUX|FUNDO DE LEGUMES|SACHET|TEMPERO|ALCOOL DE CEREAIS|"
    r"IN NATURA|CONGELAD[OA]|RESFRIAD[OA]|SEM SAL|COM SAL|INTEGRAL|DESNATAD[OA]|MOID[OA]|"
    r"RALAD[OA]|FATIAD[OA]|EM PO|EM GRAO|EXTRA VIRGEM|REFINAD[OA]|CRISTAL|DEMERARA|COMESTIVEL)\b"
)

PADROES_RUIDO_INSUMOS = [
    r"\bAULA\b", r"^ATIVIDADES?\b", r"\(SEI\s*\d+\)", r"^\d+\s*H(?:ORAS)?$",
    r"^\d+\s*ALUNOS?$", r"^UC\s*\d+", r"^\d+\s+UNIDADE$", r"\bUNI\s+\d+\b",
    r"\bUNIDADE\s+\d+\b", r"R\$\s*\d+", r"\bCURRICULAR\b",
    r"\bINFRAESTRUTURA E LISTA BASICA\b|\bANO/ATUALIZACAO/VERSAO\b",
    r"\bAPLICAR BOAS\b|\bCOMPETENCIAS?\b|\bCRITERIOS?\b|\bMENCOES ADOTADAS\b",
    r"\bELABORACAO\s*[-–—]\s*RESPONSAVEL\b|\bELABORACAO/ATUALIZACAO\b",
    r"\bSIMILAR OU SUPERIOR\b|\bA MARCA\b|\bLOGOMARCA DA INSTITUICAO\b",
    r"\bUNIDADE(?:\s+\d+)?\s+SENAC\b|\bIMPRESSAO SENAC\b|\bFORMATIVAS\b|\bSENAC\b",
    r"\bMEDIDA\s+\d+X\d+\b|\bFORMATO\b|\bTAMANHO\s+\d+\b|\bTAMANHO UNICO\b",
    r"\bPRECISAO ELETRONICA\b|\b1 GRAMA A\b|\bDE 1 GRAMA A\b|\bGRAMA A\b",
    r"\bCAPACIDADE\b|\bMEDIDAS?\s+APROXIMADAS?\b|\bDIMENSOES\b|\bCOMPRIMENTO\b",
    r"\bALTURA\b|\bPROFUNDIDADE\b|\bTENSAO\b|\bVOLTAGEM\b|\bREVESTIMENTO\b",
    r"\bTRANSPARENTE OU BRANCO\b|\bPONTA FINA\b|\bAQUECIMENTO RAPIDO\b|\bVEDACAO\b",
    r"\b(?:COZINHE|BATA|MISTURE|ADICIONE|RESERVE|HIGIENIZE|PENEIRE|MISTURAR|MEXA|LEVE AO FORNO|CORTE EM|DESCASQUE|REFOGUE|DEIXE DESCANSAR|RETIRAR A PECA|MONTAR ESTA CAIXA|PREPARAR OS FILES|FINZALIZAR|FINALIZAR)\b",
    r"\b(?:ATIVIDADE PRATICA|ATIVIDADE TEORICA|VISITA TECNICA|SITUACAO DE APRENDIZAGEM|PLANO DE TRABALHO|DESENVOLVIMENTO DE SOLUCOES|INTRODUCAO AO PI|PLANO DE NEGOCIO|ORGANIZA E HIGIENIZA|ORGANIZACAO E ESTRUTURA)\b",
    r"\b(?:HTTPS?|WWW\.|AUTENTICIDADE DO DOCUMENTO|COORDENACAO PEDAGOGICA|EIXO/SEGMENTO|DEPARTAMENTO REGIONAL)\b",
    r"\b(?:VENDIDO POR UNIDADE|NAO SE APLICA|VARIACAO DE \d+%|INSTALACAO A CARGO|VALIDADE MINIMA|DATA DA ENTREGA)\b",
    r"\b(?:SERVICO NACIONAL DE APRENDIZAGEM|APRENDIZAGEM COMERCIAL|RESTAURANTE-ESCOLA)\b",
    r"\b(?:SAO PAULO|RIO DE JANEIRO|FORTALEZA|CEARA|ED\.|EDICAO|REIMP\.|EDITORA|CHEF PROFISSIONAL|SOU COZINHEIRO|SOU BARISTA|TECNOLOGIAS GERENCIAIS|COZINHAS PROFISSIONAIS|ALIMENTOS SEGUROS|MANUAL PRATICO)\b",
    r"\b[A-Z]{3,},\s*[A-Z]\.",
    r"\bPLATAFORMA CACHOLA\b|\bANUARIO DE TECNOLOGIAS\b|\bMAPEAMENTO DE TECNOLOGIAS\b",
]


def extrair_nome_insumo_limpo(descricao_bruta: str) -> str:
    texto = limpar_texto(descricao_bruta)
    texto = re.sub(r"^(?:DE\s+MEDIDA|ITE\s*M|QUANTID(?:ADE)?|UNIDADE)\s+", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^(?:ES|E2|20)\d{6,}\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"^\d{1,3}\s*[.)-]\s*", "", texto)

    nome = re.split(r"\s*:\s*|\s+[-–—]\s+", texto, maxsplit=1)[0]
    nome = re.sub(
        r"\s+\d+(?:[.,]\d+)?\s*(?:ML|G|GR|KG|L|UNI|UNID|UNIDADE|PCT|CX|LATA|VIDRO|GARRAFA|MACO|MC|M)\b.*$",
        "",
        nome,
        flags=re.IGNORECASE,
    )
    nome = nome.strip(" .:-;•*',")

    norm = normalizar(nome)
    return CORRECOES_OCR_E_VARIACOES_INSUMOS.get(norm, nome)


def classificar_item_insumo(titulo_insumo: str, vocabulario_receitas: set[str]) -> str:
    if texto_corrompido_cid_ou_sobreposto(titulo_insumo, modo_utensilio=False):
        return "DESCARTAR"

    desc_upper = normalizar(titulo_insumo)

    if len(desc_upper) < 3 or not re.search(r"[A-Z]", desc_upper):
        return "DESCARTAR"
    if re.fullmatch(r"[\d\s.,/R$-]+", desc_upper):
        return "DESCARTAR"
    if re.fullmatch(r"ES\d+", desc_upper) or desc_upper.startswith("ES0"):
        return "DESCARTAR"
    if desc_upper in CABECALHOS_E_SECOES:
        return "DESCARTAR"

    for padrao in PADROES_RUIDO_INSUMOS:
        if re.search(padrao, desc_upper):
            return "DESCARTAR"

    if len(desc_upper.split()) > 10:
        return "DESCARTAR"

    excecoes_validas = {
        "QUARTO TRASEIRO", "QUARTO DIANTEIRO", "PONTA DE AGULHA",
        "MEIA CARCACA", "CARCACA DE FRANGO", "PAO DE FORMA",
        "MASSA PARA PASTEL EM ROLO", "BANANA PRATA", "COXA COM SOBRE COXA",
        "SUINO INTEIRO", "GALETO INTEIRO", "SUINO ADULTO", "SAL DE CURA",
        "TRIPA DE PORCO PARA EMBUTIDO", "ALCOOL DE CEREAIS", "CREME TARTARO"
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


def extrair_itens_fichas_pdf(pdf) -> list[str]:
    encontrados = []

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text(x_tolerance=1.2) or ""
        texto_pag_norm = normalizar(texto_pag)
        if "DESCRICAO DO INGREDIENTE" not in texto_pag_norm and "FICHA TECNICA" not in texto_pag_norm:
            continue

        tabelas = pagina.extract_tables(table_settings=CONFIG_TABELAS_BLINDADA) or []
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

                if "MODO DE PREPARO" in texto_linha_norm or "RENDIMENTO" in texto_linha_norm:
                    em_tabela_ingredientes = False
                    continue

                if not em_tabela_ingredientes:
                    continue

                candidato = extrair_melhor_candidato_descricao(valores, idx_preferencial=idx_ingrediente)
                nome = extrair_nome_insumo_limpo(candidato)
                if nome and len(normalizar(nome)) >= 3:
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
                if "MODO DE PREPARO" in norm or "RENDIMENTO" in norm:
                    em_ingredientes = False
                    continue
                if em_ingredientes:
                    m = re.match(
                        r"^(?:\d+[.)-]?\s+)?(.+?)\s+(?:\d+(?:[.,]\d+)?\s*)?(?:g|gr|kg|ml|l|uni|un|mc|mç|pct|q\.?b\.?|a gosto)\b",
                        linha_limpa,
                        flags=re.IGNORECASE,
                    )
                    if m:
                        nome = extrair_nome_insumo_limpo(m.group(1))
                        if nome:
                            encontrados.append(nome)

    return encontrados


def construir_vocabulario_global_receitas(arquivos_pdf: list[Path]) -> set[str]:
    vocabulario = set()
    total = len(arquivos_pdf)
    print(f"Passada 1/2: Mapeando vocabulário de ingredientes em {total} PDFs...")

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

    print(f"Vocabulário base construído com {len(vocabulario)} ingredientes únicos.\n")
    return vocabulario


def _registrar_candidato_insumo(
    candidato: str,
    nome_curso_norm: str,
    vocabulario_receitas: set[str],
    insumos: list[str],
    suspeitos: list[str],
    forcar_receita: bool = False,
) -> None:
    nome_insumo = extrair_nome_insumo_limpo(candidato)
    norm_insumo = normalizar(nome_insumo)

    if not nome_insumo or norm_insumo == nome_curso_norm or norm_insumo in nome_curso_norm:
        return

    status_item = classificar_item_insumo(nome_insumo, vocabulario_receitas)

    if status_item == "INSUMO_CONFIRMADO" or (forcar_receita and status_item == "SUSPEITO"):
        if not any(normalizar(x) == norm_insumo for x in insumos):
            insumos.append(nome_insumo)
    elif status_item == "SUSPEITO":
        if not any(normalizar(x) == norm_insumo for x in suspeitos):
            suspeitos.append(nome_insumo)


def extrair_insumos_pdf(
    pdf, nome_curso: str, vocabulario_receitas: set[str]
) -> tuple[list[str], list[str], bool]:
    insumos = []
    suspeitos = []
    nome_curso_norm = normalizar(nome_curso)
    na_lista_basica = False
    tem_cid = False

    marcadores_unidade_lista = (
        r"\b(?:KG|UNIDADE|UNI|PACOTE|PCT|CAIXA|CX|LATA|VIDRO|GARRAFA|MACO|MC|FARDO|POTE|ROLO|RL|"
        r"LITRO|PECA|BANDEJA|NAO SE APLICA|SENAC|MIDIA ESPECIALIZADA|BANCO DE PRECOS|ESTIMATIVA)\b|R\$|ES0"
    )

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text(x_tolerance=1.2) or ""
        if "(cid:" in texto_pag.lower():
            tem_cid = True

        texto_pag_norm = normalizar(texto_pag)

        tem_marcador_lista = (
            "LISTA BASICA" in texto_pag_norm
            or ("DADOS DA LISTA" in texto_pag_norm and "BASICA" in texto_pag_norm)
            or bool(re.search(r"\bINSUMOS\b", texto_pag_norm))
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

            linhas_tratadas = consolidar_linhas_quebradas_tabela(tabela)
            idx_desc = None

            for valores in linhas_tratadas:
                texto_linha_norm = normalizar(" ".join(v for v in valores if v))
                if any(h in texto_linha_norm for h in ("CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO")):
                    idx_desc = identificar_indice_coluna_descricao(valores)
                    continue

                candidato = extrair_melhor_candidato_descricao(valores, idx_preferencial=idx_desc)
                antes_ins = len(insumos)
                antes_susp = len(suspeitos)
                _registrar_candidato_insumo(
                    candidato, nome_curso_norm, vocabulario_receitas, insumos, suspeitos
                )
                if len(insumos) > antes_ins or len(suspeitos) > antes_susp:
                    achou_na_pagina = True

        if not achou_na_pagina and tem_marcador_lista:
            for linha in texto_pag.splitlines():
                linha_limpa = limpar_texto(linha)
                norm_linha = normalizar(linha_limpa)
                if not norm_linha or any(h in norm_linha for h in ("CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO", "VALOR TOTAL")):
                    continue
                if re.search(marcadores_unidade_lista, norm_linha):
                    _registrar_candidato_insumo(
                        linha_limpa, nome_curso_norm, vocabulario_receitas, insumos, suspeitos
                    )

    for cand in extrair_itens_fichas_pdf(pdf):
        _registrar_candidato_insumo(
            cand, nome_curso_norm, vocabulario_receitas, insumos, suspeitos, forcar_receita=True
        )

    if not insumos:
        for susp in list(suspeitos):
            if REGEX_SINAIS_ALIMENTO.search(normalizar(susp)) or normalizar(susp) in vocabulario_receitas:
                insumos.append(susp)
                suspeitos.remove(susp)

        for pagina in pdf.pages:
            for tabela in pagina.extract_tables(table_settings=CONFIG_TABELAS_BLINDADA) or []:
                for linha in tabela or []:
                    for cel in linha or []:
                        if not cel:
                            continue
                        nome_cand = extrair_nome_insumo_limpo(cel)
                        norm_cand = normalizar(nome_cand)
                        if not nome_cand or norm_cand in nome_curso_norm:
                            continue
                        if classificar_item_insumo(nome_cand, vocabulario_receitas) == "INSUMO_CONFIRMADO":
                            if not any(normalizar(x) == norm_cand for x in insumos):
                                insumos.append(nome_cand)

            texto_pag = pagina.extract_text(x_tolerance=1.2) or ""
            for linha in texto_pag.splitlines():
                linha_limpa = limpar_texto(linha)
                if re.search(r"\b(?:\d+(?:[.,]\d+)?\s*(?:g|gr|kg|ml|l|uni|un|pct|cx|lata|garrafa|maco)|ES\d{6,})\b", linha_limpa, re.IGNORECASE):
                    nome_cand = extrair_nome_insumo_limpo(linha_limpa)
                    norm_cand = normalizar(nome_cand)
                    if not nome_cand or norm_cand in nome_curso_norm:
                        continue
                    if classificar_item_insumo(nome_cand, vocabulario_receitas) == "INSUMO_CONFIRMADO":
                        if not any(normalizar(x) == norm_cand for x in insumos):
                            insumos.append(nome_cand)

    return insumos, suspeitos, tem_cid


# ============================================================
# 4. MÓDULO ISOLADO DE UTENSÍLIOS E EQUIPAMENTOS
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

REGEX_ALIMENTOS_PROIBIDOS_UTENSILIO = re.compile(
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

PADROES_RUIDO_UTENSILIOS = [
    r"\bAULA\b", r"^ATIVIDADES?\b", r"\(SEI\s*\d+\)", r"^\d+\s*H(?:ORAS)?$",
    r"^\d+\s*ALUNOS?$", r"^UC\s*\d+", r"^\d+\s+UNIDADE$", r"\bUNI\s+\d+\b",
    r"\bUNIDADE\s+\d+\b", r"R\$\s*\d+", r"\bCURRICULAR\d*\b",
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
    return CORRECOES_UTENSILIOS.get(norm, nome)


def classificar_item_utensilio(titulo: str, vocabulario_receitas: set[str]) -> str:
    if texto_corrompido_cid_ou_sobreposto(titulo, modo_utensilio=True):
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

    for padrao in PADROES_RUIDO_UTENSILIOS:
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

    if REGEX_ALIMENTOS_PROIBIDOS_UTENSILIO.search(desc_upper):
        return "DESCARTAR"

    if REGEX_SINAIS_UTENSILIO.search(desc_upper) or REGEX_MATERIAIS_UTENSILIO.search(desc_upper):
        return "UTENSILIO_CONFIRMADO"

    return "SUSPEITO"


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

    print("Passada 2/2: Extraindo insumos e utensílios de todos os cursos...")

    with ARQUIVO_SAIDA.open("w", encoding="utf-8-sig", newline="") as arquivo_saida:
        escritor = csv.DictWriter(
            arquivo_saida,
            fieldnames=["nome_curso", "utensilio", "insumo"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor.writeheader()

        for indice, caminho_pdf in enumerate(arquivos_pdf, start=1):
            try:
                with pdfplumber.open(caminho_pdf) as pdf:
                    nome_curso = extrair_nome_curso(pdf, caminho_pdf)
                    insumos, suspeitos_ins, cid_ins = extrair_insumos_pdf(
                        pdf, nome_curso, vocabulario_receitas
                    )
                    utensilios, suspeitos_ut, cid_ut = extrair_utensilios_pdf(
                        pdf, nome_curso, vocabulario_receitas
                    )

                tem_cid = cid_ins or cid_ut

                # Pareia utensílios e insumos lado a lado sem duplicar itens
                for utensilio, insumo in zip_longest(utensilios, insumos, fillvalue=""):
                    escritor.writerow({
                        "nome_curso": nome_curso,
                        "utensilio": utensilio,
                        "insumo": insumo
                    })

                for susp in suspeitos_ins:
                    todos_suspeitos.append({
                        "arquivo": caminho_pdf.name,
                        "nome_curso": nome_curso,
                        "categoria_origem": "INSUMO",
                        "item_suspeito": susp
                    })

                for susp in suspeitos_ut:
                    todos_suspeitos.append({
                        "arquivo": caminho_pdf.name,
                        "nome_curso": nome_curso,
                        "categoria_origem": "UTENSILIO",
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
                    status = "SEM ITENS EXTRAIDOS"

                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": nome_curso,
                    "qtd_utensilios": qtd_ut,
                    "qtd_insumos": qtd_ins,
                    "qtd_suspeitos": len(suspeitos_ins) + len(suspeitos_ut),
                    "status": status
                })

                print(
                    f"[{indice}/{len(arquivos_pdf)}] {nome_curso} | "
                    f"Utensílios: {qtd_ut} | Insumos: {qtd_ins} | "
                    f"Suspeitos: {len(suspeitos_ins) + len(suspeitos_ut)} ({status})"
                )

            except Exception as erro:
                total_erros += 1
                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": "",
                    "qtd_utensilios": 0,
                    "qtd_insumos": 0,
                    "qtd_suspeitos": 0,
                    "status": f"ERRO: {erro}"
                })
                print(f"ERRO ao processar {caminho_pdf.name}: {erro}")

    with ARQUIVO_RELATORIO.open("w", encoding="utf-8-sig", newline="") as arquivo_relatorio:
        escritor_rel = csv.DictWriter(
            arquivo_relatorio,
            fieldnames=["arquivo", "nome_curso", "qtd_utensilios", "qtd_insumos", "qtd_suspeitos", "status"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor_rel.writeheader()
        escritor_rel.writerows(relatorio)

    with ARQUIVO_REVISAO.open("w", encoding="utf-8-sig", newline="") as arquivo_rev:
        escritor_rev = csv.DictWriter(
            arquivo_rev,
            fieldnames=["arquivo", "nome_curso", "categoria_origem", "item_suspeito"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor_rev.writeheader()
        escritor_rev.writerows(todos_suspeitos)

    print("\n========== EXTRAÇÃO UNIFICADA CONCLUÍDA ==========")
    print(f"Total de PDFs processados: {len(arquivos_pdf)}")
    print(f"Erros: {total_erros}")
    print(f"Total geral de utensílios confirmados: {total_geral_utensilios}")
    print(f"Total geral de insumos confirmados: {total_geral_insumos}")
    print(f"Itens na fila de revisão: {len(todos_suspeitos)}")
    print(f"\nArquivo principal: {ARQUIVO_SAIDA}")
    print(f"Relatório: {ARQUIVO_RELATORIO}")
    print(f"Arquivo de revisão: {ARQUIVO_REVISAO}")


if __name__ == "__main__":
    main()