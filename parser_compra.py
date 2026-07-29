"""Lectura de la página de compra de Huawei (precio, regalos, cupón).

Vive aparte de scraper.py para poder probarlo sin Playwright:
    python -c "from parser_compra import leer_pagina_compra; ..."
"""
import re
import unicodedata

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def limpiar_precio(texto):
    if not texto:
        return None
    limpio = (
        texto.replace("Desde", "").replace("$", "").replace(",", "")
        .replace("MXN", "").replace("\xa0", "").replace("desde", "").strip()
    )
    try:
        return int(float(limpio))
    except ValueError:
        return None


def buscar_pagina_compra(url_ficha):
    """De la ficha de marketing saca el link de su página de compra.

    Se hace con requests (no con el navegador) porque ese link sí viene en el HTML
    y así nos ahorramos una navegación por producto.
    """
    try:
        html = requests.get(
            url_ficha,
            headers={"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9"},
            timeout=30,
        ).text
    except Exception as e:
        print(f"[scraper]   no se pudo leer la ficha: {e}")
        return None

    m = re.search(r"/mx/offer/[a-z0-9\-/]+-buy/", html, re.I)
    if not m:
        return None

    url = "https://consumer.huawei.com" + m.group(0)
    pid = re.search(r"productId=(\d+)", html)
    return f"{url}?productId={pid.group(1)}" if pid else url


# El bloque de regalos lista una línea por variante ("FreeBuds Pro 5 Gris",
# "FreeBuds Pro 5 Blanco", …). Recortamos el color/talla para quedarnos con el modelo.
COLORES = {
    "negro", "negra", "blanco", "blanca", "gris", "dorado", "dorada", "oro", "plata",
    "plateado", "azul", "verde", "morado", "morada", "púrpura", "purpura", "rosa",
    "rojo", "roja", "celeste", "naranja", "beige", "titanio", "cerámico", "ceramico",
    "lila", "café", "cafe", "marrón", "marron", "amarillo", "turquesa", "violeta",
    "grafito", "arena", "cian", "coral", "menta",
}


def _normalizar(texto):
    """Para comparar nombres sin pelearse por comillas, acentos ni mayúsculas."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", t).strip()


def _modelo_del_regalo(nombre):
    """'HUAWEI WATCH GT 6 Pro 46mm Correa de Fluoroelastómero' -> 'HUAWEI WATCH GT 6 Pro'"""
    palabras = nombre.split()
    corte = len(palabras)
    for i, palabra in enumerate(palabras):
        limpia = palabra.strip("(),.").lower()
        if i and (limpia in COLORES or re.fullmatch(r"\d+mm", limpia) or limpia in ("correa", "strap")):
            corte = i
            break
    return " ".join(palabras[:corte]).strip(" ,-") or nombre


def leer_pagina_compra(texto, nombre_producto=None):
    """Precio, precio de lista, regalos y cupón del texto ya renderizado.

    `nombre_producto` sirve para no listar el propio equipo como si fuera su regalo:
    el bloque incluye las variantes del producto que estás comprando.
    """
    def num(patron):
        m = re.search(patron, texto)
        return limpiar_precio(m.group(1)) if m else None

    # "$ 19,999 o hasta 12 pagos de $ 1,666" / "$ 28,499 Ahorra$ 8,500"
    precio = num(r"\$\s?([\d,]+)\s+o hasta")
    original = num(r"\$\s?([\d,]+)\s*Ahorra")

    regalos = []
    if "Regalo gratis" in texto:
        inicio = texto.index("Regalo gratis")
        bloque = texto[inicio:inicio + 1200]
        # El bloque de regalos termina donde empiezan los servicios de paga
        for corte in ("HUAWEI Care", "Añadir a la cesta", "Deseo servicios"):
            if corte in bloque:
                bloque = bloque[:bloque.index(corte)]
        propio = _normalizar(nombre_producto) if nombre_producto else None

        for linea in bloque.split("\n"):
            linea = linea.strip()
            if not linea.upper().startswith("HUAWEI ") or len(linea) < 10:
                continue

            nombre = linea.split(",")[0].strip()   # "FreeBuds Pro 5 Gris, Sonido…" → sin la descripción
            nombre = _modelo_del_regalo(nombre)

            # El propio equipo aparece listado con sus variantes: no es un regalo.
            if propio and _normalizar(nombre) in (propio, ""):
                continue
            if propio and propio in _normalizar(nombre):
                continue

            if nombre not in regalos:
                regalos.append(nombre)
            if len(regalos) >= 4:
                break

    cupon = None
    m = re.search(r"Código:\s*([A-Z0-9]{4,20})", texto)
    if m:
        monto = re.search(r"cupón\s*\$\s?([\d,]+)", texto, re.I)
        cupon = {"codigo": m.group(1), "monto": limpiar_precio(monto.group(1)) if monto else None}

    return {"precio": precio, "precio_original": original, "regalos": regalos, "cupon": cupon}
