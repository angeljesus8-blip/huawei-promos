"""Precios de Huawei en Liverpool.

Liverpool cambió su sitio a Next.js: el listado ya no vive en /tienda/marcas/huawei
(esa URL da 404) sino en /tienda?s=<búsqueda>, y los datos vienen embebidos en el
propio HTML como JSON. O sea que basta una petición normal — ya no hace falta
ScraperAPI, ni navegador, ni pegar links a mano.
"""
import json
import os
import re
from datetime import datetime

import requests

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "liverpool.json")
_cache = None

BASE = "https://www.liverpool.com.mx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Buscar "huawei" a secas redirige a una landing de marca sin precios,
# así que preguntamos por categoría.
QUERIES = [
    "huawei celular",
    "huawei tablet",
    "huawei smartwatch",
    "huawei audifonos",
    "huawei laptop",
]


def _bajar(query):
    r = requests.get(
        BASE + "/tienda",
        params={"s": query},
        headers={"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9"},
        timeout=45,
    )
    r.raise_for_status()
    return r.text.replace('\\"', '"')


# Liverpool abre el título con el tipo de producto ("Funda para tablet Huawei…"),
# así que basta mirar el inicio. Ojo: "Tablet … con teclado magnético" NO es accesorio.
ACCESORIOS = (
    "funda", "case", "mica", "protector", "cristal", "película", "pelicula", "film",
    "adaptador", "cable", "cargador", "correa", "extensible", "soporte", "base",
    "kit", "lápiz", "lapiz", "stylus", "memoria", "micro sd", "microsd", "bocina para",
)


def _es_accesorio(titulo):
    t = titulo.strip().lower()
    return any(t.startswith(a) for a in ACCESORIOS)


def _es_variante(titulo):
    """Las variantes de color vienen en mayúsculas y con comas ('HUAWEI FIT 4, MORADO').
    Nos quedamos con el título descriptivo del producto padre."""
    letras = [c for c in titulo if c.isalpha()]
    return "," in titulo and letras and all(c.isupper() for c in letras)


def _num(valor):
    try:
        return round(float(valor))
    except (TypeError, ValueError):
        return None


def scrape_liverpool():
    productos = {}

    for query in QUERIES:
        print(f"[liverpool] Buscando: {query}")
        try:
            html = _bajar(query)
        except Exception as e:
            print(f"[liverpool] Error en '{query}': {e}")
            continue

        # El HTML trae los links completos (/tienda/pdp/<slug>/<id>): los indexamos
        # por id para dar link exacto en vez de adivinar el slug desde el título.
        links = {
            sku: f"{BASE}/tienda/pdp/{slug}/{sku}"
            for slug, sku in re.findall(r"/tienda/pdp/([a-z0-9\-]{6,})/(\d+)", html)
        }
        encontrados = 0

        for m in re.finditer(r'"prices":\{([^}]*)\}', html):
            # El título y el skuId van antes del bloque de precios, dentro del mismo objeto.
            antes = html[max(0, m.start() - 3000):m.start()]
            titulos = re.findall(r'"title":"([^"]{4,150})"', antes)
            skus = re.findall(r'"(?:skuId|primaryProductId)":"(\d+)"', antes)
            if not titulos:
                continue

            titulo = titulos[-1].strip()
            if "huawei" not in titulo.lower() or _es_variante(titulo) or _es_accesorio(titulo):
                continue

            try:
                precios = json.loads("{" + m.group(1) + "}")
            except json.JSONDecodeError:
                continue

            precio = _num(precios.get("promoPrice") or precios.get("salePrice"))
            lista = _num(precios.get("listPrice"))
            if not precio:
                continue

            url = next((links[s] for s in reversed(skus) if s in links), None)
            if not url:
                # Sin link exacto mandamos a la búsqueda por nombre: nunca da 404.
                url = f"{BASE}/tienda?s={requests.utils.quote(titulo)}"

            clave = titulo.lower()
            # Un mismo producto sale en varias búsquedas; nos quedamos con el precio más bajo.
            if clave not in productos or precio < productos[clave]["precio"]:
                productos[clave] = {
                    "nombre": titulo,
                    "precio": precio,
                    "precio_lista": lista if lista and lista > precio else None,
                    "descuento_pct": _num(precios.get("discountPercentage")),
                    "url": url,
                }
                encontrados += 1

        print(f"[liverpool] '{query}': {encontrados} nuevos (total {len(productos)})")

    return sorted(productos.values(), key=lambda p: p["nombre"])


def ejecutar_scraping_liverpool():
    global _cache
    print(f"[liverpool] Iniciando — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    productos = scrape_liverpool()

    # Una corrida vacía no debe borrar los precios de ayer.
    if not productos:
        print("[liverpool] Corrida vacía — se conservan los datos anteriores")
        return cargar_datos_liverpool()

    data = {
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(productos),
        "productos": productos,
    }
    _cache = data

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[liverpool] Guardados {len(productos)} productos")
    return data


def cargar_datos_liverpool():
    global _cache
    if _cache and _cache.get("total", 0) > 0:
        return _cache
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                _cache = json.load(f)
                return _cache
        except (OSError, json.JSONDecodeError):
            pass
    return {"ultima_actualizacion": None, "total": 0, "productos": []}
