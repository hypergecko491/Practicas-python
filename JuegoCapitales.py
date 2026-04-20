import random

# Capitales de América y Europa
capitales_america = {
    "brasil": "brasilia",
    "canadá": "ottawa",
    "el salvador": "san salvador",
    "honduras": "tegucigalpa",
    "jamaica": "kingston",
    "méxico": "ciudad de méxico",
    "nicaragua": "managua",
    "república dominicana": "santo domingo",
    "uruguay": "montevideo",
    "venezuela": "caracas"
}

capitales_europa = {
    "grecia": "atenas",
    "alemania": "berlín",
    "austria": "viena",
    "bélgica": "bruselas",
    "francia": "parís",
    "portugal": "lisboa",
    "italia": "roma",
    "noruega": "oslo",
    "finlandia": "helsinki",
    "suiza": "berna"
}

# Función para practicar en modo principiante
def modo_principiante(capitales):
    correctas = 0
    for pais, capital in capitales.items():
        respuesta = input(f"¿Cuál es la capital de {pais.title()}? ").strip().lower()
        if respuesta == capital:
            print("¡Correcto!")
            correctas += 1
        else:
            print(f"Incorrecto, la capital de {pais.title()} es {capital.title()}.")
    print(f"\nObtuviste {correctas} respuestas correctas de 10.\n")

# Función para practicar en modo avanzado
def modo_avanzado(capitales):
    preguntas = list(capitales.items())
    random.shuffle(preguntas)
    intentos = 0
    for pais, capital in preguntas:
        while True:
            tipo_pregunta = random.choice([0, 1])  # 0 = ¿Cuál es la capital de...?, 1 = ...es la capital de...
            if tipo_pregunta == 0:
                respuesta = input(f"¿Cuál es la capital de {pais.title()}? ").strip().lower()
                pregunta = capital
            else:
                respuesta = input(f"{capital.title()} es la capital de: ").strip().lower()
                pregunta = pais

            intentos += 1
            if respuesta == pregunta:
                print("¡Correcto!")
                break
            else:
                print("Incorrecto, intenta de nuevo.")
    print(f"\nTe tomó {intentos} intentos contestar correctamente las 10 preguntas.\n")

# Función principal
def main():
    while True:
        print("\n--- Menú ---")
        print("1. Practicar capitales de América")
        print("2. Practicar capitales de Europa")
        print("0. Salir")
        opcion = input("Elige una opción: ").strip()

        if opcion == "0":
            print("Saliendo del programa...")
            break
        elif opcion in ["1", "2"]:
            if opcion == "1":
                capitales = capitales_america
            else:
                capitales = capitales_europa

            # Pedir el modo de juego
            while True:
                modo = input("¿Quieres practicar en modo 'principiante' o 'avanzado'? ").strip().lower()
                if modo in ["principiante", "avanzado"]:
                    break
                else:
                    print("Por favor, elige una opción válida: 'principiante' o 'avanzado'.")

            # Ejecutar el modo elegido
            if modo == "principiante":
                modo_principiante(capitales)
            else:
                modo_avanzado(capitales)
        else:
            print("Opción no válida. Intenta de nuevo.")

# Ejecutar el programa
if __name__ == "__main__":
    main()
