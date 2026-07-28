import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "liverpool.json")
_cache = None

PAGINAS = [
    "https://www.liverpool.com.mx/tienda/marcas/huawei?Nrpp=96",
    "https://www.liverpool.com.mx/tienda/marcas/huawei?Nrpp=96&No=96",
]


def _scraper_get(url):
    api_url = (
        f"http://api.scraperapi.com"
        f"?api_key={SCRAPER_API_KEY}"
        f"&url={requests.utils.quote(url, safe=':/?=&')}"
        f"&render=true"
        f"&country_code=mx"
    )
    r = requests.get(api_url, timeout=90)
    r.raise_for_status()
    return r.text


def _limpiar_precio(texto):
    if not texto:
        return None
    limpio = re.sub(r"[^\d.]", "", texto.replace(",", ""))
    try:
        return int(float(limpio))
    except ValueError:
        return None


def scrape_liverpool():
    productos = []
    vistos = set()

    for url in PAGINAS:
        print(f"[liverpool] Scraping: {url}")
        try:
            html = _scraper_get(url)
        except Exception as e:
            print(f"[liverpool] Error fetching {url}: {e}")
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Liverpool usa diferentes clases según versión; probamos varias
        candidatos = soup.select(
            "[class*='ProductCard'], [class*='productCard'], "
            "[class*='product-card'], [class*='ProductItem'], "
            "[class*='product-item'], [class*='VitrinaGrid']"
        )

        # Fallback: buscar links a /tienda/pdp/
        if len(candidatos) < 3:
            candidatos = [a.parent for a in soup.select("a[href*='/tienda/pdp/']")]
            print(f"[liverpool] Fallback: {len(candidatos)} contenedores por link pdp")
        else:
            print(f"[liverpool] {len(candidatos)} tarjetas encontradas")

        for card in candidatos:
            try:
                # Nombre
                nombre_el = card.select_one(
                    "[class*='name'], [class*='Name'], [class*='title'], [class*='Title'], h2, h3, p"
                )
                nombre = nombre_el.get_text(strip=True) if nombre_el else None
                if not nombre or len(nombre) < 4:
                    continue
                if nombre in vistos:
                    continue

                # Link
                link_el = card.select_one("a[href*='/tienda/pdp/']") or card.find("a")
                href = link_el["href"] if link_el and link_el.get("href") else None
                if not href:
                    continue
                link = href if href.startswith("http") else f"https://www.liverpool.com.mx{href}"

                # Precio — buscar el más bajo visible (precio con descuento)
                precio = None
                for el in card.select("[class*='price'], [class*='Price'], [class*='costo'], [class*='Costo']"):
                    txt = el.get_text(strip=True)
                    p = _limpiar_precio(txt)
                    if p and p > 100:
                        if precio is None or p < precio:
                            precio = p

                if not precio:
                    continue

                vistos.add(nombre)
                productos.append({
                    "nombre": nombre,
                    "precio": precio,
                    "url": link,
                })

            except Exception as e:
                print(f"[liverpool] Error tarjeta: {e}")

        print(f"[liverpool] Acumulados: {len(productos)} productos")

    return productos


def ejecutar_scraping_liverpool():
    global _cache
    print(f"[liverpool] Iniciando — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if not SCRAPER_API_KEY:
        print("[liverpool] Sin SCRAPER_API_KEY — se omite (los datos previos se conservan)")
        return cargar_datos_liverpool()

    productos = scrape_liverpool()

    # Igual que en Huawei: una corrida vacía no debe borrar los precios de ayer.
    if not productos:
        print("[liverpool] Corrida vacía — se conservan los datos anteriores")
        return cargar_datos_liverpool()

    data = {
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(productos),
        "productos": productos,
    }
    _cache = data

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[liverpool] Guardados {len(productos)} productos")
    except Exception as e:
        print(f"[liverpool] No se pudo guardar: {e}")

    return data


def cargar_datos_liverpool():
    global _cache
    if _cache and _cache.get("total", 0) > 0:
        return _cache
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                data = json.load(f)
                _cache = data
                return data
        except Exception:
            pass
    return {"ultima_actualizacion": None, "total": 0, "productos": []}
