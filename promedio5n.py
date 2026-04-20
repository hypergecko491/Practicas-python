# Solicita al usuario ingresar una lista de 5 números
numeros = input("Ingresa 5 números separados por comas: ")

# Convierte la entrada del usuario en una lista de enteros
lista_numeros = [int(num) for num in numeros.split(",")]

# Calcula el promedio de los elementos
promedio = sum(lista_numeros) / len(lista_numeros)

# Muestra el promedio
print(f"El promedio de los elementos es: {promedio}")
