from datetime import date
from calibracion import correr_calibracion

correr_calibracion(
    date(2024, 4, 1),
    date(2025, 7, 1),
    archivo_salida="calibracion.csv"
)

print("Calibración completada.")
