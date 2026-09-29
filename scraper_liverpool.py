"""Precios de Huawei en Liverpool, y cuántas piezas hay en Liverpool Angelópolis.

Liverpool cambió su sitio a Next.js: el listado ya no vive en /tienda/marcas/huawei
(esa URL da 404) sino en /tienda?s=<búsqueda>, y los datos vienen embebidos en el
propio HTML como JSON. O sea que basta una petición normal — ya no hace falta
ScraperAPI, ni navegador, ni pegar links a mano.

Sep-2026: el JSON de la búsqueda cambió de forma (ahora es un arreglo "records" con
priceInfo y variantsColor). El lector viejo buscaba "prices":{...}, encontró cero
productos desde el 31-ago y la regla de "corrida vacía no borra" dejó la app con
precios de agosto sin que nada avisara. Por eso la página ahora avisa si el dato es viejo.
"""
import json
import os
import re
import time
from datetime import datetime

import requests

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "liverpool.json")
_cache = None

BASE = "https://www.liverpool.com.mx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9"}

# Buscar "huawei" a secas redirige a una landing de marca sin precios,
# así que preguntamos por categoría.
QUERIES = [
    "huawei celular",
    "huawei tablet",
    "huawei smartwatch",
    "huawei audifonos",
    "huawei laptop",
]

# Inventario por sucursal: es lo que consulta el botón "Ver disponibilidad en tienda"
# de la ficha. Va por estado y por SKU de la variante (color), NO por producto:
# con el id del producto regresa vacío aunque haya piezas.
# La respuesta solo lista las sucursales CON piezas: si la 72 no sale, tiene 0.
ESTADO_PUEBLA = "21"
SUCURSAL = "72"  # Liverpool Angelópolis
STOCK_URL = BASE + "/web-bff/product/{sku}/stock?state=" + ESTADO_PUEBLA


def _bajar(query, pagina=1):
    ruta = "/tienda" if pagina == 1 else f"/tienda/page-{pagina}"
    r = requests.get(BASE + ruta, params={"s": query}, headers=HEADERS, timeout=45)
    r.raise_for_status()
    return r.text


def _records(html):
    """Saca el arreglo "records" y el número de páginas del HTML de la búsqueda.

    Next.js manda los datos como strings de JS dentro de self.__next_f.push([1,"..."]):
    primero se decodifica ese string y luego el JSON de adentro.
    """
    i = html.find('\\"records\\":[')
    if i < 0:
        return [], 1
    inicio = html.rfind('self.__next_f.push([1,', 0, i) + len('self.__next_f.push([1,')
    bloque, _ = json.JSONDecoder().raw_decode(html[inicio:])
    j = bloque.find('"records":')
    records, _ = json.JSONDecoder().raw_decode(bloque[j + len('"records":'):])
    paginas = re.search(r'"noOfPages":(\d+)', bloque)
    return records, int(paginas.group(1)) if paginas else 1


# Liverpool abre el título con el tipo de producto ("Funda para tablet Huawei…"),
# así que basta mirar el inicio. Ojo: "Tablet … con teclado magnético" NO es accesorio.
# Los "Kit/Set/Smartwatch…" SÍ son equipos (reloj + banda): no filtrar "kit".
ACCESORIOS = (
    "funda", "case", "mica", "protector", "cristal", "película", "pelicula", "film",
    "adaptador", "cable", "cargador", "correa", "extensible", "soporte", "base",
    "lápiz", "lapiz", "stylus", "memoria", "micro sd", "microsd", "bocina para",
)


def _es_accesorio(titulo):
    t = titulo.strip().lower()
    return any(t.startswith(a) for a in ACCESORIOS)


def _num(valor):
    try:
        return round(float(valor))
    except (TypeError, ValueError):
        return None


def _precio(bloque):
    """{'price': X} o, si las variantes cuestan distinto, {'minPrice': X, 'maxPrice': Y}."""
    if not isinstance(bloque, dict):
        return _num(bloque)
    return _num(bloque.get("price") or bloque.get("minPrice"))


def scrape_liverpool():
    productos = {}

    for query in QUERIES:
        print(f"[liverpool] Buscando: {query}")
        pagina, paginas, encontrados = 1, 1, 0
        while pagina <= paginas:
            try:
                html = _bajar(query, pagina)
                records, paginas = _records(html)
            except Exception as e:
                print(f"[liverpool] Error en '{query}' pág. {pagina}: {e}")
                break

            # Links exactos (/tienda/pdp/<slug>/<id>) indexados por id del producto.
            links = {
                pid: f"{BASE}/tienda/pdp/{slug}/{pid}"
                for slug, pid in re.findall(r'href="/tienda/pdp/([^"/?]+)/(\d+)', html)
            }

            for r in records:
                pid = r.get("productId")
                titulo = (r.get("title") or "").strip()
                flags = r.get("featureFlags") or {}
                # Solo lo que vende Liverpool: el marketplace son terceros (reacondicionados,
                # fundas de otras marcas) y no tiene piezas en sucursal.
                if not pid or pid in productos or not titulo:
                    continue
                if (r.get("brand") or "").upper() != "HUAWEI" or flags.get("isMarketPlace"):
                    continue
                if _es_accesorio(titulo):
                    continue

                info = r.get("priceInfo") or {}
                precio = _precio(info.get("promoPrice")) or _num(info.get("salePrice"))
                lista = _precio(info.get("listPrice"))
                if not precio:
                    continue

                colores = [
                    {"sku": v["skuId"], "color": v.get("colorName") or ""}
                    for v in (r.get("variantsColor") or []) if v.get("skuId")
                ] or [{"sku": pid, "color": ""}]

                productos[pid] = {
                    "nombre": titulo,
                    "precio": precio,
                    "precio_lista": lista if lista and lista > precio else None,
                    "descuento_pct": round((lista - precio) * 100 / lista) if lista and lista > precio else None,
                    "url": links.get(pid, f"{BASE}/tienda/pdp/p/{pid}"),
                    "_colores": colores,
                }
                encontrados += 1
            pagina += 1

        print(f"[liverpool] '{query}': {encontrados} nuevos (total {len(productos)})")

    return sorted(productos.values(), key=lambda p: p["nombre"])


def _piezas_sucursal(sku):
    """Piezas del SKU en la sucursal. None si la consulta falló (≠ 0 piezas)."""
    try:
        r = requests.get(STOCK_URL.format(sku=sku), headers=HEADERS, timeout=30)
        r.raise_for_status()
        tiendas = r.json()["stores"]
    except Exception as e:
        print(f"[liverpool] Stock {sku}: {e}")
        return None
    for t in tiendas:
        if str(t.get("storeId")) == SUCURSAL:
            return _num(t.get("stock")) or 0
    return 0


def agregar_inventario(productos):
    """Agrega a cada producto las piezas en Angelópolis, desglosadas por color.

    Si alguna variante no se pudo consultar, el producto queda con "angelopolis": null
    (la página dice "sin dato"): un total al que le falta un color diría menos
    piezas de las que hay.
    """
    fallos = 0
    for p in productos:
        colores = p.pop("_colores")
        detalle = []
        for c in colores:
            piezas = _piezas_sucursal(c["sku"])
            time.sleep(0.2)
            if piezas is None:
                detalle = None
                break
            detalle.append({"color": c["color"], "piezas": piezas})
        if detalle is None:
            fallos += 1
            p["angelopolis"] = None
        else:
            p["angelopolis"] = {
                "piezas": sum(c["piezas"] for c in detalle),
                "colores": [c for c in detalle if c["piezas"] and c["color"]],
            }
    con = sum(1 for p in productos if p["angelopolis"] and p["angelopolis"]["piezas"])
    print(f"[liverpool] Angelópolis: {con} productos con piezas, {fallos} sin dato")
    return fallos


def ejecutar_scraping_liverpool():
    global _cache
    print(f"[liverpool] Iniciando — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    productos = scrape_liverpool()

    # Una corrida vacía no debe borrar los precios de ayer (la página avisa que son viejos).
    if not productos:
        print("[liverpool] Corrida vacía — se conservan los datos anteriores")
        return cargar_datos_liverpool()

    fallos = agregar_inventario(productos)

    data = {
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(productos),
        "sucursal": "Liverpool Angelópolis",
        "inventario_sin_dato": fallos,
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
