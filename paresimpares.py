# Inicializamos la lista donde se almacenarán los números
numeros = []

# Bucle para leer números enteros hasta que se introduzca un número negativo
while True:
    num = int(input("Introduce un número entero (negativo para terminar): "))
    if num < 0:
        break  # Termina el bucle si se introduce un número negativo
    numeros.append(num)  # Agrega el número a la lista

# Inicializamos contadores para pares e impares
pares = 0
impares = 0

# Recorremos la lista para contar pares e impares
for num in numeros:
    if num % 2 == 0:
        pares += 1  # Incrementa el contador de pares si el número es divisible por 2
    else:
        impares += 1  # Incrementa el contador de impares si no es divisible por 2

# Mostramos los resultados
print(f"Números pares: {pares}")
print(f"Números impares: {impares}")
