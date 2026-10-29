# ETL Cozinha

## Descrição do Projeto

O ETL Cozinha é um projeto desenvolvido em Python com o objetivo de automatizar a extração de dados presentes em documentos PDF de planos de cursos da área de gastronomia e produção alimentícia.

O sistema utiliza a biblioteca `pdfplumber` para identificar e extrair informações dos documentos, organizando os dados em arquivos CSV para facilitar sua análise e posterior tratamento.

## Objetivo

Automatizar a extração de informações dos planos de cursos, preservando o vínculo entre cada curso e seus respectivos insumos e utensílios.

## Funcionalidades

- Leitura automatizada de múltiplos arquivos PDF.
- Identificação dos nomes dos cursos.
- Extração de tabelas contendo insumos e utensílios.
- Associação dos dados extraídos aos respectivos cursos.
- Exportação dos resultados para arquivos CSV.
- Verificação inicial da integridade dos dados extraídos.

## Tecnologias Utilizadas

- Python
- pdfplumber
- Pandas
- pathlib
- CSV

## Estrutura do Projeto

```text
ETl-cozinha/
│
├── OneDrive_2026-10-28/
│   └── Dados para ETL - Cozinha/
│       └── Arquivos PDF
│
├── resultados/
│   ├── curso.csv
│   ├── insumos.csv
│   └── utensilios.csv
│
├── cozinha.py
├── validacao.py
└── README.md
```

## Instalação

Clone o repositório:

```bash
git clone URL_DO_REPOSITORIO
```

Instale as dependências:

```bash
pip install pdfplumber pandas
```

## Execução

Configure o caminho da pasta contendo os PDFs no arquivo `cozinha.py`.

Execute a extração:

```bash
python cozinha.py
```

Os dados extraídos serão armazenados na pasta `resultados`.

Para executar a validação inicial:

```bash
python validacao.py
```

## Arquivos Gerados

| Arquivo | Descrição |
|---|---|
| curso.csv | Informações dos cursos identificados nos PDFs. |
| insumos.csv | Insumos extraídos e associados aos respectivos cursos. |
| utensilios.csv | Utensílios extraídos e associados aos respectivos cursos. |

## Etapas do ETL

**1. Extração (Extract)**

Leitura dos documentos PDF e extração das informações dos cursos, insumos e utensílios.

**2. Transformação (Transform)**

Etapa destinada à limpeza, padronização e organização dos dados extraídos.

**3. Carga (Load)**

Etapa destinada ao armazenamento dos dados tratados em um banco de dados.

## Observações

Os dados extraídos são mantidos inicialmente em seu formato bruto, podendo apresentar inconsistências, duplicações e valores ausentes.

O tratamento dessas informações será realizado nas próximas etapas do projeto.
