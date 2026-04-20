import math

# Parámetros
k = 1.03972
N0 = 50

# Paso 4: Número de bacterias después de 4.5 horas
t_45 = 4.5
N_45 = N0 * math.exp(k * t_45)

# Paso 5: Tasa de crecimiento después de 4.5 horas (derivada de N(t))
rate_45 = N0 * k * math.exp(k * t_45)

# Paso 6: Tiempo cuando la población alcanzará 50,000 bacterias
N_target = 50000
t_target = math.log(N_target / N0) / k

N_45, rate_45, t_target
