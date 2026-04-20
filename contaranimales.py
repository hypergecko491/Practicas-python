# Solicita al usuario ingresar una lista de 6 animales
animales = input("Ingresa los animales separados por comas: ")

# Convierte la entrada del usuario en una lista de cadenas
lista_animales = [animal.strip() for animal in animales.split(",")]

# Solicita el animal específico a buscar
animal_a_buscar = input("Ingresa el animal a buscar: ")

# Cuenta cuántas veces aparece el animal en la lista
contador = lista_animales.count(animal_a_buscar)

# Muestra el resultado
print(f"El animal '{animal_a_buscar}' aparece {contador} veces en la lista.")
