# ETL Cozinha — Extração e Tratamento de Dados

## Sobre o projeto

O **ETL Cozinha** é um projeto desenvolvido em Python para automatizar a extração, organização e classificação de informações presentes em documentos PDF de planos de cursos da área de gastronomia.

O projeto utiliza técnicas de processamento de texto e extração de tabelas para identificar os nomes dos cursos, seus respectivos insumos alimentícios e utensílios, transformando informações originalmente não estruturadas em arquivos CSV.

O processamento foi desenvolvido considerando documentos com diferentes estruturas de tabelas, formatações e possíveis inconsistências de leitura.

## Objetivos

- Automatizar a extração de informações de documentos PDF.
- Identificar e associar insumos e utensílios aos respectivos cursos.
- Padronizar informações extraídas dos documentos.
- Identificar possíveis erros de leitura e inconsistências.
- Organizar os dados em arquivos CSV para facilitar análises posteriores.

## Funcionalidades

- Leitura automatizada de múltiplos arquivos PDF.
- Extração e identificação dos nomes dos cursos.
- Identificação de insumos alimentícios.
- Identificação de utensílios e equipamentos.
- Normalização de textos e correção de variações identificadas pelo OCR.
- Classificação semântica de itens.
- Identificação de registros suspeitos para revisão manual.
- Geração de relatórios de processamento.
- Exportação dos dados estruturados em CSV.

## Tecnologias utilizadas

- **Python** — desenvolvimento e processamento dos dados.
- **pdfplumber** — extração de textos e tabelas de arquivos PDF.
- **CSV** — armazenamento e organização dos dados.
- **Regex (Expressões Regulares)** — identificação e tratamento de padrões textuais.
- **Pathlib** — gerenciamento de diretórios e arquivos.
- **Unicode / Unicodedata** — normalização de caracteres e textos.

## Estrutura do projeto

```text
extracao-de-dados-cozinha/
│
├── OneDrive_2026-10-28/
│   └── Dados para ETL - Cozinha/
│       └── Arquivos PDF dos cursos
│
├── resultados/
│   ├── cursos_insumos_e_utensilios_final.csv
│   ├── relatorio_extracao_unificado.csv
│   └── itens_suspeitos_revisao_unificado.csv
│
├── cozinha.py
├── insumos.py
├── utensilhos.py
├── teste.py
│
└── README.md
```

## Scripts

| Arquivo | Responsabilidade |
|---|---|
| `cozinha.py` | Extração integrada de insumos e utensílios. |
| `insumos.py` | Extração e classificação de insumos alimentícios. |
| `utensilhos.py` | Extração e classificação de utensílios e equipamentos. |
| `teste.py` | Script auxiliar para testes e validação da extração. |

## Como executar

### 1. Clone o repositório

```bash
git clone URL_DO_REPOSITORIO
```

### 2. Acesse a pasta do projeto

```bash
cd extracao-de-dados-cozinha
```

### 3. Crie um ambiente virtual

```bash
python -m venv .venv
```

### 4. Ative o ambiente virtual

Windows:

```bash
.venv\Scripts\activate
```

### 5. Instale a dependência

```bash
pip install pdfplumber
```

### 6. Execute o processamento

Para extração integrada:

```bash
python cozinha.py
```

Para extrair somente insumos:

```bash
python insumos.py
```

Para extrair somente utensílios:

```bash
python utensilhos.py
```

**Importante:** os arquivos PDF devem estar na estrutura de diretórios esperada pelo projeto para que os scripts encontrem os documentos.

## Arquivos gerados

A execução do script integrado gera três arquivos principais:

| Arquivo | Conteúdo |
|---|---|
| `cursos_insumos_e_utensilios_final.csv` | Dados extraídos, associados aos respectivos cursos. |
| `relatorio_extracao_unificado.csv` | Quantidade de itens identificados, status e informações de processamento por PDF. |
| `itens_suspeitos_revisao_unificado.csv` | Registros identificados como suspeitos e que precisam de revisão. |

Os arquivos CSV utilizam codificação UTF-8 com BOM e separador de ponto e vírgula.

## Etapas do processo ETL

**1. Extract — Extração**

Leitura dos arquivos PDF e identificação das informações presentes nos documentos, incluindo nomes dos cursos, insumos alimentícios, utensílios e equipamentos.

**2. Transform — Transformação**

Limpeza e normalização dos textos, tratamento de caracteres, correção de variações de escrita, classificação dos itens e identificação de possíveis inconsistências.

**3. Load — Carga**

Organização e exportação dos dados estruturados em arquivos CSV, permitindo sua utilização em etapas posteriores de análise e armazenamento.

## Tratamento e qualidade dos dados

Um dos principais desafios do projeto é a diversidade de estruturas encontradas nos documentos PDF.

Para lidar com esse problema, foram implementados mecanismos de:

- Normalização de caracteres e remoção de inconsistências textuais.
- Identificação de possíveis erros de extração.
- Correção de variações de escrita e falhas comuns de OCR.
- Classificação de itens por categorias.
- Identificação de registros que necessitam de revisão.

A extração automatizada não elimina a necessidade de validação dos dados, especialmente em documentos com tabelas complexas ou problemas de formatação.

## Resultados

O projeto foi desenvolvido para processar um conjunto de **78 documentos PDF**, transformando informações de planos de cursos em dados estruturados e organizados.

Os resultados podem ser utilizados como base para análises exploratórias, identificação de padrões e desenvolvimento de soluções de gestão de dados.

---

**Projeto desenvolvido em Python | ETL | Extração de Dados | Processamento de Texto | Organização de Dados**
