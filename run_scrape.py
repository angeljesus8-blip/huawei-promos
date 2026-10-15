"""Punto de entrada del scraping. Lo corre GitHub Actions una vez al día.

    python run_scrape.py            → Huawei + Liverpool
    python run_scrape.py huawei     → solo huawei.com/mx
    python run_scrape.py liverpool  → solo Liverpool

Escribe docs/promos.json y docs/liverpool.json, que son los que lee la página.
"""
import json
import sys
import traceback

import scraper
import scraper_liverpool

TAREAS = {
    "huawei": ("huawei.com/mx", scraper.ejecutar_scraping, scraper.DATA_FILE),
    "liverpool": ("Liverpool", scraper_liverpool.ejecutar_scraping_liverpool, scraper_liverpool.DATA_FILE),
}


def _estado(ruta):
    """(fecha de la medición, productos, productos con precio) del JSON publicado."""
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    productos = data.get("productos") or []
    con_precio = sum(1 for p in productos if p.get("precio_actual") or p.get("precio"))
    return data.get("ultima_actualizacion"), len(productos), con_precio


def revisar(etiqueta, antes, despues):
    """Por qué esta corrida NO sirvió, o None si sirvió.

    Una corrida vacía no borra los datos de ayer (mejor precios viejos que pantalla en
    blanco), pero tampoco puede pasar callada: del 31-ago al 28-sep-2026 Liverpool no
    leyó nada, el workflow salió verde todos los días y nadie se enteró en un mes.
    """
    if despues is None:
        return f"{etiqueta}: no hay JSON después de la corrida"
    if antes and despues[0] == antes[0]:
        return f"{etiqueta}: no se actualizó, sigue con los datos del {despues[0]}"
    if antes and despues[1] < antes[1] / 2:
        return f"{etiqueta}: trajo {despues[1]} productos y la corrida anterior {antes[1]}"
    if antes and despues[2] < antes[2] / 2:
        return f"{etiqueta}: {despues[2]} productos con precio y la corrida anterior {antes[2]}"
    return None


def main():
    pedidas = sys.argv[1:] or list(TAREAS)
    fallos = []

    for nombre in pedidas:
        if nombre not in TAREAS:
            print(f"[run] Tarea desconocida: {nombre}")
            continue
        etiqueta, funcion, ruta = TAREAS[nombre]
        antes = _estado(ruta)
        try:
            data = funcion()
            print(f"[run] {etiqueta}: {data.get('total', 0)} productos")
        except Exception:
            # Que una fuente truene no debe impedir que la otra se actualice.
            print(f"[run] {etiqueta} falló:")
            traceback.print_exc()
            fallos.append(f"{etiqueta}: error (ver arriba)")
            continue
        problema = revisar(etiqueta, antes, _estado(ruta))
        if problema:
            print(f"[run] ⚠️ {problema}")
            fallos.append(problema)

    if fallos:
        print("[run] Terminó con fallos:\n  " + "\n  ".join(fallos))
        sys.exit(1)


if __name__ == "__main__":
    main()
