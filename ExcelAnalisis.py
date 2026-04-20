import pandas as pd
# Cargar archivo (subido previamente a Colab)
df = pd.read_excel("C:\Users\elisa\OneDrive\Documentos\Excel\Excel Actualizado.xlsx")
# Mostrar primeras filas
print(df.head())
# Información general del dataset
print(df.info())
# Estadísticas básicas
print(df.describe())
# Mostrar nombres de columnas
print(df.columns)
