# Solicita al usuario que ingrese los números separados por comas
entrada = input("Introduce una lista de números separados por comas: ")

# Convierte la entrada en una lista de enteros
numeros = [int(num) for num in entrada.split(",")]

# Calcula el cuadrado de cada número
cuadrados = [num ** 2 for num in numeros]

# Convierte la lista de cuadrados en una cadena, separada por comas
resultado = ",".join(map(str, cuadrados))

# Imprime el resultado
print(f"Los cuadrados de los números son: {resultado}")
