"""Seguimiento diario de precios: docs/historico.csv (se abre directo en Excel).

    python historico.py               → agrega (o reemplaza) el día de los JSON actuales
    python historico.py --reconstruir → lo arma desde cero con el historial de git

Una fila por producto, por fuente y por día medido. La fecha es la de la medición
(`ultima_actualizacion` del JSON), no la del commit: si una corrida sale vacía, el
JSON conserva los precios de ayer con su fecha de ayer, y ese día NO se cuenta como
medido. Así no se inventa un "sin cambio" (Liverpool estuvo congelado del 31-ago al
28-sep de 2026 y esos días no aparecen).
"""
import csv
import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(AQUI, "docs", "historico.csv")
FUENTES = {
    "huawei.com": "docs/promos.json",
    "Liverpool": "docs/liverpool.json",
}
CAMPOS = ["fecha", "fuente", "id", "producto", "precio", "precio_lista", "descuento_pct", "url"]


def _limpio(nombre):
    # Las laptops llegan como "14.2 pulgadas\n\nMateBook X Pro": un renglón, sin saltos.
    return " ".join(str(nombre or "").split())


def filas_de(fuente, data):
    fecha = str(data.get("ultima_actualizacion") or "")[:10]
    if not fecha:
        return []
    filas = []
    for p in data.get("productos") or []:
        if fuente == "Liverpool":
            pid = p["url"].rstrip("/").split("/")[-1]
            precio, lista, url = p.get("precio"), p.get("precio_lista"), p.get("url")
        else:
            # En huawei.com el nombre es lo estable: el productId del link puede cambiar.
            pid = _limpio(p.get("nombre"))
            precio, lista = p.get("precio_actual"), p.get("precio_original")
            url = p.get("link_compra") or p.get("link")
        filas.append({
            "fecha": fecha, "fuente": fuente, "id": pid, "producto": _limpio(p.get("nombre")),
            "precio": precio if precio else "", "precio_lista": lista if lista else "",
            "descuento_pct": p.get("descuento_pct") or "", "url": url or "",
        })
    return filas


def leer():
    if not os.path.exists(CSV):
        return []
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def escribir(filas):
    filas.sort(key=lambda r: (r["fecha"], r["fuente"], r["producto"]))
    # utf-8-sig: con el BOM, Excel abre los acentos bien al darle doble clic.
    with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    escribir_cambios(filas)


def escribir_cambios(filas):
    """docs/historico_cambios.json: lo que lee la pestaña Historial.

    El CSV crece ~160 renglones al día; el celular no tiene por qué bajarlo entero.
    Aquí va cada producto solo con los días en que su precio CAMBIÓ (más el primero
    y el último medido). Precio vacío = ese día no tenía precio (sin venta online).
    """
    series = {}
    for r in filas:   # ya vienen ordenadas por fecha
        s = series.setdefault((r["fuente"], r["id"]), {
            "fuente": r["fuente"], "producto": r["producto"], "puntos": []})
        s["producto"], s["url"] = r["producto"], r["url"]   # se queda el nombre más reciente
        precio = int(float(r["precio"])) if r["precio"] else None
        lista = int(float(r["precio_lista"])) if r["precio_lista"] else None
        pts = s["puntos"]
        if not pts or pts[-1][1] != precio:
            pts.append([r["fecha"], precio, lista])
        s["ultima"] = r["fecha"]
    dias = sorted({r["fecha"] for r in filas})
    salida = {"desde": dias[0] if dias else None, "hasta": dias[-1] if dias else None,
              "productos": list(series.values())}
    with open(os.path.join(AQUI, "docs", "historico_cambios.json"), "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))


def registrar():
    """Mete el día de los JSON actuales; si ese día ya estaba (corrida manual), lo reemplaza."""
    filas = leer()
    for fuente, ruta in FUENTES.items():
        try:
            with open(os.path.join(AQUI, ruta), encoding="utf-8") as f:
                nuevas = filas_de(fuente, json.load(f))
        except (OSError, ValueError) as e:
            print(f"[historico] {fuente}: no se pudo leer {ruta}: {e}")
            continue
        if not nuevas:
            continue
        fecha = nuevas[0]["fecha"]
        filas = [r for r in filas if not (r["fecha"] == fecha and r["fuente"] == fuente)] + nuevas
        print(f"[historico] {fuente} {fecha}: {len(nuevas)} productos")
    escribir(filas)


def _git(*args):
    return subprocess.run(["git", *args], cwd=AQUI, capture_output=True, check=True).stdout


def reconstruir():
    """Recorre cada versión de los JSON en git; por día gana la última medición."""
    por_dia = {}
    for fuente, ruta in FUENTES.items():
        commits = _git("log", "--reverse", "--format=%H", "--", ruta).decode().split()
        for c in commits:
            try:
                data = json.loads(_git("show", f"{c}:{ruta}").decode("utf-8"))
            except (subprocess.CalledProcessError, ValueError):
                continue
            nuevas = filas_de(fuente, data)
            if nuevas:
                por_dia[(fuente, nuevas[0]["fecha"])] = nuevas
        dias = sorted(f for (fu, f) in por_dia if fu == fuente)
        print(f"[historico] {fuente}: {len(commits)} versiones → {len(dias)} días medidos "
              f"({dias[0] if dias else '-'} a {dias[-1] if dias else '-'})")
    escribir([fila for filas in por_dia.values() for fila in filas])


if __name__ == "__main__":
    reconstruir() if "--reconstruir" in sys.argv else registrar()
