"""Punto de entrada del scraping. Lo corre GitHub Actions una vez al día.

    python run_scrape.py            → Huawei + Liverpool
    python run_scrape.py huawei     → solo huawei.com/mx
    python run_scrape.py liverpool  → solo Liverpool

Escribe docs/promos.json y docs/liverpool.json, que son los que lee la página.
"""
import sys
import traceback

from scraper import ejecutar_scraping
from scraper_liverpool_api import ejecutar_scraping_liverpool

TAREAS = {
    "huawei": ("huawei.com/mx", ejecutar_scraping),
    "liverpool": ("Liverpool", ejecutar_scraping_liverpool),
}


def main():
    pedidas = sys.argv[1:] or list(TAREAS)
    fallos = []

    for nombre in pedidas:
        if nombre not in TAREAS:
            print(f"[run] Tarea desconocida: {nombre}")
            continue
        etiqueta, funcion = TAREAS[nombre]
        try:
            data = funcion()
            print(f"[run] {etiqueta}: {data.get('total', 0)} productos")
        except Exception:
            # Que una fuente truene no debe impedir que la otra se actualice.
            print(f"[run] {etiqueta} falló:")
            traceback.print_exc()
            fallos.append(etiqueta)

    if fallos:
        print(f"[run] Terminó con fallos en: {', '.join(fallos)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
