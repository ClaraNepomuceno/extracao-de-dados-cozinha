import pdfplumber
from pathlib import Path
import csv

# Caminho dos PDFs
PASTA_PDFS = Path(
    r"C:\Users\ana57393876\Documents\ETl-cozinha\OneDrive_2026-10-28"
)

# Pasta para salvar os resultados
PASTA_RESULTADOS = Path(
    r"C:\Users\ana57393876\Documents\ETl-cozinha\resultados"
)

PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)

# Encontrar todos os PDFs
arquivos_pdf = sorted(PASTA_PDFS.rglob("*.pdf"))

print(f"Total de PDFs encontrados: {len(arquivos_pdf)}")

# Armazenar os dados extraídos
cursos = []
tabelas_extraidas = []

# Percorrer todos os PDFs
for id_curso, arquivo in enumerate(arquivos_pdf, start=1):

    print(f"\nProcessando: {arquivo.name}")

    try:
        with pdfplumber.open(arquivo) as pdf:

            nome_curso = None

            # ETAPA 1: Identificar o nome do curso
            for pagina in pdf.pages:

                texto = pagina.extract_text()

                if not texto:
                    continue

                for linha in texto.splitlines():

                    if "Nome do Curso:" in linha:

                        nome_curso = linha.split(
                            "Nome do Curso:", 1
                        )[1].strip()

                        break

                if nome_curso:
                    break

            # Armazenar o curso
            cursos.append({
                "id_curso": id_curso,
                "nome_curso": nome_curso,
                "arquivo": arquivo.name
            })

            print(f"Curso: {nome_curso}")

            # ETAPA 2: Extrair todas as tabelas
            for numero_pagina, pagina in enumerate(
                pdf.pages, start=1
            ):

                tabelas = pagina.extract_tables()

                for numero_tabela, tabela in enumerate(
                    tabelas, start=1
                ):

                    for numero_linha, linha in enumerate(
                        tabela, start=1
                    ):

                        tabelas_extraidas.append({
                            "id_curso": id_curso,
                            "nome_curso": nome_curso,
                            "arquivo": arquivo.name,
                            "pagina": numero_pagina,
                            "tabela": numero_tabela,
                            "linha": numero_linha,
                            "dados": linha
                        })

    except Exception as erro:
        print(f"Erro ao processar {arquivo.name}: {erro}")

# ETAPA 3: Salvar os cursos
with open(
    PASTA_RESULTADOS / "cursos.csv",
    "w",
    newline="",
    encoding="utf-8-sig"
) as arquivo_csv:

    escritor = csv.DictWriter(
        arquivo_csv,
        fieldnames=["id_curso", "nome_curso", "arquivo"],
        delimiter=";"
    )

    escritor.writeheader()
    escritor.writerows(cursos)

# ETAPA 4: Salvar as tabelas
with open(
    PASTA_RESULTADOS / "tabelas_extraidas.csv",
    "w",
    newline="",
    encoding="utf-8-sig"
) as arquivo_csv:

    escritor = csv.DictWriter(
        arquivo_csv,
        fieldnames=[
            "id_curso",
            "nome_curso",
            "arquivo",
            "pagina",
            "tabela",
            "linha",
            "dados"
        ],
        delimiter=";"
    )

    escritor.writeheader()
    escritor.writerows(tabelas_extraidas)

print("\n================================")
print("EXTRAÇÃO FINALIZADA")
print("================================")

print(f"PDFs encontrados: {len(arquivos_pdf)}")
print(f"Cursos registrados: {len(cursos)}")
print(f"Linhas extraídas: {len(tabelas_extraidas)}")

print("\nArquivos gerados:")
print("cursos.csv")
print("tabelas_extraidas.csv")