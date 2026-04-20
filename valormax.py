# Solicita al usuario que ingrese los números separados por comas
entrada = input("Introduce una lista de números separados por comas: ")

# Convierte la entrada en una lista de enteros
numeros = [int(num) for num in entrada.split(",")]

# Encuentra el valor máximo en la lista
max_valor = max(numeros)

# Encuentra el índice de la primera aparición del valor máximo
indice_max = numeros.index(max_valor)

# Imprime el valor máximo y su índice
print(f"El valor más grande es: {max_valor}")
print(f"El índice de su primera aparición es: {indice_max}")
