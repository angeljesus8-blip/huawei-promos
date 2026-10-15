"""Prueba local del parser, sin navegador ni red: python test_parser.py

El texto de muestra es el que rinde la página de compra del Pura 90s Pro Max
(capturado el 28-jul-2026).
"""
from parser_compra import leer_pagina_compra, producto_por_nombre

# Página de compra compartida del FIT 4 / FIT 4 Pro (así viene en el HTML, escapado).
COMPRA_FIT4 = (
    '{&quot;productId&quot;:&quot;10052515051898&quot;,&quot;popLoc&quot;:&quot;x&quot;,'
    '&quot;productName&quot;:&quot;HUAWEI WATCH FIT 4&quot;}'
    '{&quot;productId&quot;:&quot;10052860498180&quot;,&quot;popLoc&quot;:&quot;x&quot;,'
    '&quot;productName&quot;:&quot;HUAWEI WATCH FIT 4 Pro&quot;}'
)

CON_REGALO = """Obtén $1,000 off con cupón: APURA1000
Modelo
HUAWEI Pura 90s Pro
Desde $ 15,999
cupón $ 1,000 dto.
Cupón $1,000 de la serie Pura 90s Pro
2026.07.22 02:30 - 2026.08.07 05:59
Código: APURA1000
Copiar
Regalo gratis

HUAWEI FreeBuds Pro 5 Gris, Sonido ultra-inmersivo, driver dual e IA para cancelación de ruido
Gris
$ 0
$ 2,999
Cantidad:1
HUAWEI Servicio Premium (Pura 90s Pro Max)
12 Meses
$ 0
$ 5,899
Cantidad:1
HUAWEI Care
La cobertura de servicios y los pagos mensuales recurrentes comienzan cuando el dispositivo se envía.
$ 19,999 o hasta 12 pagos de $ 1,666 (Sin intereses )
Detalles
$ 28,499 Ahorra$ 8,500
Añadir a la cesta
Comprar"""

SIN_REGALO = """HUAWEI MatePad Pro 13.2-inch 2025
Envío gratis desde $ 2,000
Por favor, selecciona tu regalo
$ 29,999 o hasta 12 pagos de $ 2,499 (Sin intereses )
Detalles
Añadir a la cesta
Comprar"""


# Caso real del 29-jul: el bloque lista cada color del regalo y además las
# variantes del propio equipo, que no son regalo.
CON_VARIANTES = """Regalo gratis

HUAWEI FreeBuds Pro 5 Gris, Sonido ultra-inmersivo
Gris
$ 0
HUAWEI FreeBuds Pro 5 Blanco, Sonido ultra-inmersivo
Blanco
$ 0
HUAWEI WATCH GT 6 Pro 46mm Correa de Fluoroelastómero
$ 0
HUAWEI WATCH FIT 5 Pro Blanco Fluoroelastomer Strap
$ 0
$ 5,999 o hasta 12 pagos de $ 499 (Sin intereses )"""


def main():
    fallos = 0

    d = leer_pagina_compra(CON_VARIANTES, "HUAWEI WATCH FIT 5 Pro")
    esperado_variantes = ["HUAWEI FreeBuds Pro 5", "HUAWEI WATCH GT 6 Pro"]
    if d["regalos"] != esperado_variantes:
        print(f"FALLA variantes: esperaba {esperado_variantes!r}, salió {d['regalos']!r}")
        fallos += 1

    d = leer_pagina_compra(CON_REGALO)
    esperado = {
        "precio": 19999,
        "precio_original": 28499,
        # sin el color: el bloque repite el mismo regalo una vez por variante
        "regalos": ["HUAWEI FreeBuds Pro 5", "HUAWEI Servicio Premium (Pura 90s Pro Max)"],
        "cupon": {"codigo": "APURA1000", "monto": 1000},
    }
    for clave, valor in esperado.items():
        if d[clave] != valor:
            print(f"FALLA {clave}: esperaba {valor!r}, salió {d[clave]!r}")
            fallos += 1

    d = leer_pagina_compra(SIN_REGALO)
    if d["regalos"]:
        print(f"FALLA: inventó regalos donde no hay: {d['regalos']}")
        fallos += 1
    if d["precio"] != 29999:
        print(f"FALLA precio sin regalo: {d['precio']}")
        fallos += 1
    if d["cupon"] is not None:
        print(f"FALLA: inventó cupón: {d['cupon']}")
        fallos += 1

    # El id se elige por nombre EXACTO: el FIT 4 no puede tomar el del FIT 4 Pro.
    for nombre, esperado in (("HUAWEI WATCH FIT 4 Pro", "10052860498180"),
                             ("HUAWEI WATCH FIT 4", "10052515051898"),
                             ("HUAWEI WATCH FIT 5", None)):
        pid = producto_por_nombre(COMPRA_FIT4, nombre)
        if pid != esperado:
            print(f"FALLA productId de {nombre}: esperaba {esperado}, salió {pid}")
            fallos += 1

    print("Todo bien" if not fallos else f"{fallos} fallas")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
