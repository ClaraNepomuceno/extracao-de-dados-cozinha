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


# ============================================================
# 2. NORMALIZAÇÃO E LIMPEZA
# ============================================================

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip(" :;-").upper()


def limpar_texto(texto):
    texto = texto or ""
    return re.sub(r"\s+", " ", texto).strip()


def texto_corrompido_cid(texto):
    return "(cid:" in (texto or "").lower()


def extrair_nome_curso(pdf, caminho_pdf):
    for pagina in pdf.pages[:3]:
        texto = pagina.extract_text() or ""
        if texto_corrompido_cid(texto):
            continue

        m1 = re.search(
            r"CURSO\s*:\s*([^\n]+)",
            texto,
            flags=re.IGNORECASE
        )
        if m1:
            nome = limpar_texto(m1.group(1))
            nome = re.split(r"\s+QTD\s+TOTAL", nome, flags=re.IGNORECASE)[0]
            if nome and normalizar(nome) != "CURSO":
                return nome.strip()

    nome = caminho_pdf.stem
    nome = re.sub(r"-\d+-horas.*$", "", nome, flags=re.IGNORECASE)
    return nome.replace("-", " ").strip()


# ============================================================
# 3. FILTRO CIRÚRGICO PARA EXCLUIR NÃO-INSUMOS (ATUALIZADO)
# ============================================================

def e_nao_insumo(descricao):
    desc_upper = normalizar(descricao)

    if texto_corrompido_cid(desc_upper):
        return True

    if len(desc_upper) < 2:
        return True

    # Descarta se não possuir nenhuma letra (ex: $$, #!, **, etc.)
    if not re.search(r"[A-ZÀ-ÿ]", desc_upper):
        return True

    if re.fullmatch(r"ES\d+", desc_upper) or desc_upper.startswith("ES0"):
        return True

    cabecalhos_tabela = {
        "CODIGO ITEM MXM", "DESCRICAO/ESPECIFICACAO DETALHADA", "DESCRICAO",
        "ESPECIFICACAO", "U.M", "QUANTIDADE POR ALUNO", "QUANTIDADE POR TURMA",
        "VALOR UNITARIO", "VALOR TOTAL", "TIPO DE FINANCIAMENTO", "INSUMOS",
        "MIDIA ESPECIALIZADA", "ESTIMATIVA", "UNIFORMES", "MODO DE PREPARO",
        "INFRAESTRUTURA E LISTA BASICA1", "INFRAESTRUTURA E LISTA BASICA", "INDICADORES",
        "LISTA BASICA", "DADOS DA LISTA BASICA", "QUALIFICACAO PROFISSIONAL", "ULTIMA REVISAO",
        "UNIFORME", "DESCRICAO DO INGREDIENTE", "ITEM", "QUANTIDADE", "MEDIDA", "CATEGORIA"
    }
    if desc_upper in cabecalhos_tabela:
        return True

    if re.fullmatch(r"[\d\s.,/-]+", desc_upper):
        return True

    # Termos proibidos atualizados para bloquear pinças, pegadores, rolos, conteúdos e seções
    termos_proibidos = {
        # Eletrodomésticos e Equipamentos
        "AR-CONDICIONADO", "COMPUTADOR", "MONITOR", "REFRIGERADOR", "FREEZER",
        "GELADEIRA", "FORNO", "FOGAO", "LIQUIDIFICADOR", "PROCESSADOR", "BATEDEIRA", 
        "CAFETEIRA", "MICRO-ONDA",
        # Utensílios, Pinças, Pegadores, Rolos, Cortadores e Ferramentas
        "PINCA", "PEGADOR", "ROLO LAMINADOR", "ROLO", "CORTADOR", "ARO", "PIRES", 
        "PLACA DE CORTE", "PORTA CONDIMENTO", "POTE HERMETICO", "RALADOR", "ZESTER", 
        "SERINGA", "SIFAO", "SPEED RAIL", "STOREN POUR", "SUPORTE PARA PLACAS", 
        "TAPETE DE SILICONE", "TESOURA", "TRAVESSA", "BOWL", "BOWLL", "CAIXA PLASTICA", 
        "CONTENTOR", "CHAIRA", "DESCASCADOR", "ESCUMADEIRA", "FOUET", "FUNIL", "MANDOLINE", 
        "MANDOLIN", "MOADOR", "PEDRA DE AFIAR", "ESPATULA", "PA PARA PIZZA", "GRADE", 
        "FORMA", "TABA", "FACA", "PANELA", "FRIGIDEIRA", "CALDEIRAO", "ASSADEIRA", 
        "TIGELA", "CUBA", "CONCHA", "ESCORREDOR", "PENEIRA", "COLHER", "GARFO", "PRATO", 
        "COPO", "XICARA", "TACA", "JARRA", "TERMOMETRO", "BALANCA", "MEDIDOR", "AZEITEIRO", 
        "RECIPIENTE", "DISPENSADOR", "RAMEQUIN", "BACIA", "MANDUCA",
        # Materiais de Limpeza, Higiene, Escritório e EPIs
        "FIBRA SINTETICA", "FIBRAÇO", "FOSFORO", "HIPOCLORITO", "MASCARA", "PANO MULTIUSO",
        "PAPEL ALUMINIO", "POTE COM TAMPA", "SACO PLASTICO", "SABONETE", "TOUCA", 
        "BANDEJA", "APAGADOR", "PAPEL A4", "SULFITE", "PINCEL", "ALCOOL", "PAPEL TOALHA", 
        "AVENTAL", "CALCA", "CAMISETA", "BOTA", "JALECO", "JAPONA", "LUVA",
        # Cronogramas, Competências, Técnicas de Corte, Aulas e Administrativo
        "CARGA HORARIA", "TURMA", "INDICADORES", "CRONOGRAMA", "AULA", "MODO DE PREPARO", 
        "HIGIENIZE", "RESERVE", "ADICIONE", "DEIXE DESCANSAR", "PENEIRE", "SENAC", 
        "VAGAS", "RECURSO FINANCEIRO", "CODIGO DO SEI", "ELABORACAO", "PRATO:",
        "TECNICAS DE CORTE", "REFILE", "ELEMENTOS DA COMPETENCIA", "ORIENTACOES METODOLOGICAS",
        "APROVEITAMENTO", "ESTAGIO", "ORGANIZACAO CURRICULAR", "AVALIACAO", "BIBLIOGRAFIA",
        # Móveis e Estruturas
        "BANCADA", "MESA", "CADEIRA", "ARMARIO", "SOFTWARE", "EQUIPAMENTO", "UTENSILIO"
    }

    for termo in termos_proibidos:
        if termo in desc_upper:
            return True

    return False


# ============================================================
# 4. EXTRAÇÃO DIRECIONADA DA SEÇÃO DE INSUMOS
# ============================================================

def extrair_insumos(pdf, nome_curso):
    insumos = []
    nome_curso_norm = normalizar(nome_curso)
    coletando = False
    tem_cid = False

    for pagina in pdf.pages:
        texto_pag = pagina.extract_text() or ""
        if texto_corrompido_cid(texto_pag):
            tem_cid = True

        tabelas = pagina.extract_tables()
        for tabela in tabelas:
            for linha in tabela:
                if not linha:
                    continue

                valores = [valor or "" for valor in linha]
                texto_linha = normalizar(" ".join(v for v in valores if v))

                if not texto_linha:
                    continue

                if any(sec in texto_linha for sec in ["INSUMOS", "DESCRIÇÃO DO INGREDIENTE", "PRATO:"]):
                    coletando = True
                    continue

                if any(sec in texto_linha for sec in ["EQUIPAMENTOS", "UTENSILIOS", "EPI", "MÓVEIS", "MODO DE PREPARO", "CRONOGRAMA", "INDICADORES", "ORIENTACOES METODOLOGICAS"]):
                    if "INSUMOS" not in texto_linha and "DESCRIÇÃO DO INGREDIENTE" not in texto_linha:
                        coletando = False
                        continue

                if not coletando and ("VALOR UNITARIO" in texto_linha or "MIDIA ESPECIALIZADA" in texto_linha or "QUARTO" in texto_linha or "ARROZ AGULHINHA" in texto_linha):
                    coletando = True

                if not coletando:
                    continue

                descricao = ""
                for idx in [1, 2, 0]:
                    if idx < len(valores) and len(limpar_texto(valores[idx])) >= 2:
                        candidato = limpar_texto(valores[idx])
                        candidato_up = normalizar(candidato)
                        if candidato_up not in {"DESCRICAO/ESPECIFICACAO DETALHADA", "CODIGO ITEM MXM", "INSUMOS", "DESCRICAO DO INGREDIENTE", "ITEM", "QUANTIDADE", "MEDIDA"}:
                            descricao = candidato
                            break

                if not descricao:
                    continue

                if normalizar(descricao) == nome_curso_norm:
                    continue

                if not e_nao_insumo(descricao):
                    if descricao not in insumos:
                        insumos.append(descricao)

    return insumos, tem_cid


def processar_pdf(caminho_pdf):
    with pdfplumber.open(caminho_pdf) as pdf:
        nome_curso = extrair_nome_curso(pdf, caminho_pdf)
        insumos, tem_cid = extrair_insumos(pdf, nome_curso)
    return {
        "nome_curso": nome_curso,
        "insumos": insumos,
        "tem_cid": tem_cid
    }


# ============================================================
# 5. FLUXO PRINCIPAL
# ============================================================

def main():
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    arquivos_pdf = sorted(PASTA_PDFS.rglob("*.pdf"))

    if not arquivos_pdf:
        print(f"Nenhum PDF encontrado em: {PASTA_PDFS}")
        return

    total_erros = 0
    total_geral_insumos = 0
    relatorio = []

    with ARQUIVO_SAIDA.open("w", encoding="utf-8-sig", newline="") as arquivo_saida:
        escritor = csv.DictWriter(
            arquivo_saida,
            fieldnames=["nome_curso", "insumo_detalhado"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor.writeheader()

        for indice, caminho_pdf in enumerate(arquivos_pdf, start=1):
            try:
                resultado = processar_pdf(caminho_pdf)
                nome_curso = resultado["nome_curso"]
                insumos = resultado["insumos"]
                tem_cid = resultado["tem_cid"]

                for idx_item, insumo in enumerate(insumos):
                    escritor.writerow({
                        "nome_curso": nome_curso if idx_item == 0 else "",
                        "insumo_detalhado": insumo
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
                    "status": status
                })

                print(f"[{indice}/{len(arquivos_pdf)}] {nome_curso} | Insumos: {qtd_insumos} ({status})")

            except Exception as erro:
                total_erros += 1
                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": "",
                    "qtd_insumos": 0,
                    "status": f"ERRO: {erro}"
                })
                print(f"ERRO ao processar {caminho_pdf.name}: {erro}")

    with ARQUIVO_RELATORIO.open("w", encoding="utf-8-sig", newline="") as arquivo_relatorio:
        escritor_rel = csv.DictWriter(
            arquivo_relatorio,
            fieldnames=["arquivo", "nome_curso", "qtd_insumos", "status"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor_rel.writeheader()
        escritor_rel.writerows(relatorio)

    print("\n========== EXTRAÇÃO CONCLUÍDA ==========")
    print(f"Total de PDFs processados: {len(arquivos_pdf)}")
    print(f"Erros: {total_erros}")
    print(f"Total geral de insumos extraídos: {total_geral_insumos}")
    print(f"\nArquivo gerado: {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()