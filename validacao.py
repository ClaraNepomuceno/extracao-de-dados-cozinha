import pandas as pd
from pathlib import Path

# Pasta dos resultados
PASTA = Path("resultados")

# Carregar os arquivos CSV
cursos = pd.read_csv(PASTA / "curso.csv", sep=None, engine="python")
insumos = pd.read_csv(PASTA / "insumos.csv", sep=None, engine="python")
utensilios = pd.read_csv(PASTA / "utensilios.csv", sep=None, engine="python")

# 1. Quantidade de registros
print("\n========== QUANTIDADE DE REGISTROS ==========")

print(f"Cursos: {len(cursos)}")
print(f"Insumos: {len(insumos)}")
print(f"Utensílios: {len(utensilios)}")

# 2. Identificar as colunas
print("\n========== COLUNAS ==========")

print("\nCursos:")
print(cursos.columns.tolist())

print("\nInsumos:")
print(insumos.columns.tolist())

print("\nUtensílios:")
print(utensilios.columns.tolist())

# 3. Verificar valores ausentes
print("\n========== VALORES AUSENTES ==========")

print("\nCursos:")
print(cursos.isnull().sum())

print("\nInsumos:")
print(insumos.isnull().sum())

print("\nUtensílios:")
print(utensilios.isnull().sum())

# 4. Verificar registros duplicados
print("\n========== DUPLICADOS ==========")

print(f"Cursos: {cursos.duplicated().sum()}")
print(f"Insumos: {insumos.duplicated().sum()}")
print(f"Utensílios: {utensilios.duplicated().sum()}")

print("\n========== VALIDAÇÃO FINALIZADA ==========")