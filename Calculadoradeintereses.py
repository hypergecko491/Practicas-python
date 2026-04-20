# titulo
print("=== CALCULADORA DE INTERESES ===")
# Datos del usuario
nombre = input("Ingresa tu nombre: ")
saldo = float(input("Ingresa tu saldo inicial: "))
tasa_interes = 0.08  # 8% anual

deposito_octubre = float(input("Depósito en octubre: "))
retiro_diciembre = float(input("Retiro en diciembre: "))

# Simulacion del interes
for mes in range(1, 13):
    interes_mensual = saldo * tasa_interes / 12
    saldo += interes_mensual
    # Eventos especiales
    if mes == 10:
        saldo += deposito_octubre
        print("Se agregó depósito en octubre")
    if mes == 12:
        saldo -= retiro_diciembre
        print("Se realizó retiro en diciembre")
#impresion
print("\n--- RESULTADOS ---")
print("Nombre:", nombre)
print("Saldo final después de 1 año:", saldo)
