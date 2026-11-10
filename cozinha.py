import csv
import re
import unicodedata
from pathlib import Path

import pdfplumber


BASE = Path(__file__).resolve().parent
PASTA_PDFS = BASE / 'OneDrive_2026-10-28' / 'Dados para ETL - Cozinha'
PASTA_RESULTADOS = BASE / 'resultados'
ARQUIVO_SAIDA = PASTA_RESULTADOS / 'cursos_insumos_utensilios.csv'

SECOES_PEDIDAS = {
	'INSUMOS': 'insumos',
	'UTENSILIOS': 'utensilios',
}
SECOES_FORA_DO_ESCOPO = {
	'EQUIPAMENTOS, MOVEIS E SOFTWARE',
	'EQUIPAMENTOS, MOVEIS E SOFTWARES',
	'UNIFORME',
	'MATERIAL DE CONSUMO',
	'MATERIAL PERMANENTE',
	'MATERIAIS DE CONSUMO',
}


def normalizar_rotulo(texto):
	texto = unicodedata.normalize('NFKD', texto or '')
	texto = ''.join(caractere for caractere in texto if not unicodedata.combining(caractere))
	return re.sub(r'\s+', ' ', texto).strip(' :;').upper()


def identificar_secao(texto):
	rotulo = normalizar_rotulo(texto)
	if rotulo in SECOES_PEDIDAS:
		return SECOES_PEDIDAS[rotulo]
	if rotulo in SECOES_FORA_DO_ESCOPO:
		return ''
	return None


def extrair_nome_curso(pdf):
	padrao_principal = r'(?:Nome|Título)\s+do\s+Curso\s*:\s*([^\r\n]+)'
	for pagina in pdf.pages:
		texto = pagina.extract_text() or ''
		correspondencia = re.search(padrao_principal, texto, flags=re.IGNORECASE)
		if correspondencia:
			return re.sub(r'\s+', ' ', correspondencia.group(1)).strip()

	padrao_alternativo = r'^\s*Curso\s*:\s*(.*?)(?=\s+(?:Docente:|QTD TOTAL DE ALUNOS:|Segmento:|Carga Horária:)|\s*$)'
	for pagina in pdf.pages:
		texto = pagina.extract_text() or ''
		correspondencia = re.search(padrao_alternativo, texto, flags=re.IGNORECASE | re.MULTILINE)
		if correspondencia:
			return re.sub(r'\s+', ' ', correspondencia.group(1)).strip()
	return ''


def extrair_itens(pdf):
	itens = {'insumos': [], 'utensilios': []}
	secao_atual = ''
	tabela_de_itens = False
	coluna_descricao = 1

	for pagina in pdf.pages:
		texto = pagina.extract_text() or ''
		for linha in texto.splitlines():
			secao = identificar_secao(linha)
			if secao is not None:
				secao_atual = secao
				tabela_de_itens = False

		for tabela in pagina.extract_tables():
			for linha in tabela:
				if not linha:
					continue

				valores = [valor or '' for valor in linha]
				secao_encontrada = next(
					(identificar_secao(valor) for valor in valores if identificar_secao(valor) is not None),
					None,
				)
				if secao_encontrada is not None:
					secao_atual = secao_encontrada
					tabela_de_itens = False
					continue

				coluna_cabecalho = next(
					(
						indice
						for indice, valor in enumerate(valores)
						if 'DESCRICAO' in normalizar_rotulo(valor)
						and 'ESPECIFICACAO' in normalizar_rotulo(valor)
					),
					None,
				)
				if coluna_cabecalho is not None:
					coluna_descricao = coluna_cabecalho
					tabela_de_itens = True
					continue

				if not tabela_de_itens or secao_atual not in itens:
					continue
				if coluna_descricao >= len(valores):
					continue

				descricao = valores[coluna_descricao].strip()
				if descricao:
					itens[secao_atual].append(descricao)

	return itens


def main():
	arquivos_pdf = sorted(PASTA_PDFS.glob('*.pdf'))
	PASTA_RESULTADOS.mkdir(parents=True, exist_ok=True)

	with ARQUIVO_SAIDA.open('w', encoding='utf-8-sig', newline='') as arquivo_saida:
		escritor = csv.DictWriter(
			arquivo_saida,
			fieldnames=['nome_curso', 'insumos', 'utensilios'],
			delimiter=';',
		)
		escritor.writeheader()

		for caminho_pdf in arquivos_pdf:
			with pdfplumber.open(caminho_pdf) as pdf:
				nome_curso = extrair_nome_curso(pdf)
				itens = extrair_itens(pdf)

			escritor.writerow({
				'nome_curso': nome_curso,
				'insumos': '\n'.join(itens['insumos']),
				'utensilios': '\n'.join(itens['utensilios']),
			})

	print(f'PDFs processados: {len(arquivos_pdf)}')
	print(f'Arquivo gerado: {ARQUIVO_SAIDA.relative_to(BASE)}')


if __name__ == '__main__':
	main()
