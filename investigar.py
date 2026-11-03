
import pdfplumber
from pathlib import Path

PASTA_PDFS = Path(
    r"C:\Users\ana57393876\Documents\ETl-cozinha\OneDrive_2026-10-28"
)

NOME_PDF = "Tecnicas-Basicas-para-Garcom-80-horas-2025.pdf"

# Localizar o PDF automaticamente
arquivos = list(PASTA_PDFS.rglob(NOME_PDF))

if not arquivos:
    print("PDF não encontrado!")
    exit()

arquivo = arquivos[0]

print("=" * 70)
print("INVESTIGAÇÃO DO PDF")
print("=" * 70)
print(f"Arquivo: {arquivo.name}")

palavras = [
    "INSUMO",
    "UTENSILHO",
    "MATERIAL",
    "EQUIPAMENTO",
    "RECURSO",
    "FERRAMENTA"
]

with pdfplumber.open(arquivo) as pdf:

    print(f"\nTotal de páginas: {len(pdf.pages)}")

    for numero, pagina in enumerate(pdf.pages, start=1):

        texto = pagina.extract_text()

        if not texto:
            continue

        linhas = texto.splitlines()

        resultados = []

        for i, linha in enumerate(linhas):

            if any(palavra in linha.upper() for palavra in palavras):

                inicio = max(0, i - 2)
                fim = min(len(linhas), i + 4)

                resultados.extend(linhas[inicio:fim])

        if resultados:
            print(f"\n--- PÁGINA {numero} ---")

            for linha in dict.fromkeys(resultados):
                print(linha)

print("\nInvestigação finalizada!")
