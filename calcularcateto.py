import math

def calcular_cateto_faltante(cateto_conocido, hipotenusa):
    if hipotenusa <= cateto_conocido:
        raise ValueError("La hipotenusa debe ser mayor que el cateto conocido.")
    
    cateto_faltante = math.sqrt(hipotenusa**2 - cateto_conocido**2)
    return cateto_faltante

# Ejemplo de uso:
cateto_conocido = 4
hipotenusa = 5

cateto_faltante = calcular_cateto_faltante(cateto_conocido, hipotenusa)
print("El cateto faltante es:", cateto_faltante)
