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

ARQUIVO_SAIDA = PASTA_RESULTADOS / "cursos_descricao_itens.csv"
ARQUIVO_RELATORIO = PASTA_RESULTADOS / "relatorio_extracao.csv"


# ============================================================
# 2. FUNÇÕES AUXILIARES
# ============================================================

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip(" :;").upper()


def limpar_texto(texto):
    texto = texto or ""
    return re.sub(r"\s+", " ", texto).strip()


def extrair_nome_curso(pdf, caminho_pdf):
    """Extrai o nome do curso do cabeçalho do documento ou do nome do arquivo."""
    for pagina in pdf.pages[:3]:
        texto = pagina.extract_text() or ""
        padrao = r"CURSO\s*:\s*(.*?)(?=\s+(?:SEGMENTO|CARGA\s+HORÁRIA|TIPO|CÓDIGO)\s*:|$)"
        resultado = re.search(padrao, texto, flags=re.IGNORECASE | re.DOTALL)
        if resultado:
            nome = limpar_texto(resultado.group(1))
            if nome:
                return nome

    # Fallback para o nome do arquivo
    nome = caminho_pdf.stem
    nome = re.sub(r"-\d+-horas.*$", "", nome, flags=re.IGNORECASE)
    return nome.replace("-", " ").strip()


def localizar_coluna_descricao(linha):
    """Encontra o índice da coluna que contém a descrição ou especificação detalhada."""
    for indice, valor in enumerate(linha):
        rotulo = normalizar(valor)
        if "DESCRICAO" in rotulo or "ESPECIFICACAO" in rotulo:
            return indice
    return None


def descricao_valida(descricao):
    """Filtra cabeçalhos e textos inválidos para manter apenas os itens reais."""
    descricao = limpar_texto(descricao)
    if len(descricao) < 3:
        return False
    
    rotulo = normalizar(descricao)
    ignorar = {
        "DESCRICAO", "ESPECIFICACAO", "DESCRICAO/ESPECIFICACAO DETALHADA", 
        "ITEM", "LOTE", "QUANTIDADE", "VALOR UNITARIO", "VALOR TOTAL", 
        "UNIDADE", "U.M", "TIPO DE FINANCIAMENTO"
    }
    if rotulo in ignorar:
        return False

    if re.fullmatch(r"[\d\s.,/-]+", descricao):
        return False

    return True


# ============================================================
# 3. EXTRAÇÃO DE ITENS DE TODAS AS TABELAS
# ============================================================

def extrair_itens(pdf):
    """Varre todas as tabelas do PDF coletando descrições válidas de qualquer seção."""
    itens = []
    coluna_descricao = None

    for pagina in pdf.pages:
        tabelas = pagina.extract_tables()
        for tabela in tabelas:
            for linha in tabela:
                if not linha:
                    continue
                
                valores = [valor or "" for valor in linha]

                # Tenta localizar o cabeçalho da tabela se ele aparecer na página
                col_encontrada = localizar_coluna_descricao(valores)
                if col_encontrada is not None:
                    coluna_descricao = col_encontrada
                    continue

                # Se ainda não encontrou o cabeçalho, assume por padrão a 3ª coluna (índice 2), 
                # que é onde costuma ficar a descrição na estrutura padrão (como visto na imagem).
                if coluna_descricao is None and len(valores) > 2:
                    coluna_descricao = 2

                if coluna_descricao is None or coluna_descricao >= len(valores):
                    continue

                descricao = limpar_texto(valores[coluna_descricao])

                if descricao_valida(descricao) and descricao not in itens:
                    itens.append(descricao)

    return itens


# ============================================================
# 4. PROCESSAMENTO E FLUXO PRINCIPAL
# ============================================================

def processar_pdf(caminho_pdf):
    with pdfplumber.open(caminho_pdf) as pdf:
        nome_curso = extrair_nome_curso(pdf, caminho_pdf)
        itens = extrair_itens(pdf)
    return {
        "nome_curso": nome_curso,
        "itens": itens
    }


def main():
    PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    arquivos_pdf = sorted(PASTA_PDFS.rglob("*.pdf"))

    if not arquivos_pdf:
        print(f"Nenhum PDF encontrado em: {PASTA_PDFS}")
        return

    total_erros = 0
    total_geral_itens = 0
    relatorio = []

    with ARQUIVO_SAIDA.open("w", encoding="utf-8-sig", newline="") as arquivo_saida:
        escritor = csv.DictWriter(
            arquivo_saida,
            fieldnames=["nome_curso", "descricao_detalhada"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor.writeheader()

        for indice, caminho_pdf in enumerate(arquivos_pdf, start=1):
            try:
                resultado = processar_pdf(caminho_pdf)
                nome_curso = resultado["nome_curso"]
                itens = resultado["itens"]

                # Escreve cada item encontrado em uma linha separada junto com o curso
                for item in itens:
                    escritor.writerow({
                        "nome_curso": nome_curso,
                        "descricao_detalhada": item
                    })

                qtd_itens = len(itens)
                total_geral_itens += qtd_itens
                status = "OK" if qtd_itens > 0 else "ALERTA - SEM ITENS"

                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": nome_curso,
                    "qtd_itens": qtd_itens,
                    "status": status
                })

                print(f"[{indice}/{len(arquivos_pdf)}] {nome_curso} | Itens extraídos: {qtd_itens}")

            except Exception as erro:
                total_erros += 1
                relatorio.append({
                    "arquivo": caminho_pdf.name,
                    "nome_curso": "",
                    "qtd_itens": 0,
                    "status": f"ERRO: {erro}"
                })
                print(f"ERRO ao processar {caminho_pdf.name}: {erro}")

    # Relatório de conferência
    with ARQUIVO_RELATORIO.open("w", encoding="utf-8-sig", newline="") as arquivo_relatorio:
        escritor_rel = csv.DictWriter(
            arquivo_relatorio,
            fieldnames=["arquivo", "nome_curso", "qtd_itens", "status"],
            delimiter=";",
            quoting=csv.QUOTE_ALL
        )
        escritor_rel.writeheader()
        escritor_rel.writerows(relatorio)

    print("\n========== RESULTADO DA EXTRAÇÃO SIMPLIFICADA ==========")
    print(f"Total de PDFs processados: {len(arquivos_pdf)}")
    print(f"Erros: {total_erros}")
    print(f"Total de itens extraídos: {total_geral_itens}")
    print(f"\nArquivos salvos em: {PASTA_RESULTADOS}")


if __name__ == "__main__":
    main()