# Solicita al usuario ingresar una lista de 5 números
numeros = input("Ingresa los números separados por comas: ")

# Convierte la entrada del usuario en una lista de enteros
lista_numeros = [int(num) for num in numeros.split(",")]

# Encuentra el número más grande y el más pequeño
maximo = max(lista_numeros)
minimo = min(lista_numeros)

# Muestra el número más grande y el más pequeño
print(f"El número más grande es: {maximo}")
print(f"El número más pequeño es: {minimo}")
