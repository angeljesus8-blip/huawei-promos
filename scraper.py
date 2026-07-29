import json
import os
from datetime import datetime

from playwright.sync_api import sync_playwright

from parser_compra import UA, buscar_pagina_compra, leer_pagina_compra, limpiar_precio

URLS = [
    ("https://consumer.huawei.com/mx/phones/", "Smartphones"),
    ("https://consumer.huawei.com/mx/tablets/", "Tablets"),
    ("https://consumer.huawei.com/mx/wearables/", "Wearables"),
    ("https://consumer.huawei.com/mx/laptops/", "Laptops"),
]

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "promos.json")
_cache = None


def scrape_con_playwright():
    productos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--single-process", "--disable-extensions", "--disable-gpu",
            ],
        )
        context = browser.new_context(
            locale="es-MX",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = context.new_page()

        def bloquear(route):
            if route.request.resource_type in ("image", "media", "font", "stylesheet"):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", bloquear)

        # PASO 1: Recolectar datos básicos de cada listado (sin navegar fuera)
        items_basicos = []
        for url, categoria in URLS:
            print(f"[scraper] Listado: {url}")
            try:
                page.goto(url, timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(6000)
                tarjetas = page.query_selector_all(".product-item")
                print(f"[scraper] {categoria} → {len(tarjetas)} tarjetas")

                vistos = set()
                for tarjeta in tarjetas:
                    try:
                        nombre_el = tarjeta.query_selector(".product-title")
                        precio_el = tarjeta.query_selector(".price-origin")
                        tachado_el = tarjeta.query_selector(".price-through label")
                        link_el = tarjeta.query_selector("a.product-title, a[href*='/mx/']")
                        badge_el = tarjeta.query_selector(
                            ".product-label, [class*='label'], [class*='badge']"
                        )

                        nombre = nombre_el.inner_text().strip() if nombre_el else None
                        if not nombre or nombre in vistos:
                            continue
                        vistos.add(nombre)

                        href = link_el.get_attribute("href") if link_el else None
                        link = None
                        if href:
                            link = href if href.startswith("http") else f"https://consumer.huawei.com{href}"

                        items_basicos.append({
                            "nombre": nombre,
                            "categoria": categoria,
                            "precio_actual": limpiar_precio(precio_el.inner_text() if precio_el else None),
                            "precio_original": limpiar_precio(tachado_el.inner_text() if tachado_el else None),
                            "badge": badge_el.inner_text().strip() if badge_el else None,
                            "link": link,
                        })
                    except Exception as e:
                        print(f"[scraper] Error tarjeta: {e}")

            except Exception as e:
                print(f"[scraper] Error listado {url}: {e}")

        print(f"[scraper] Total básicos: {len(items_basicos)}")

        # PASO 2: Visitar la PÁGINA DE COMPRA de cada producto.
        # La ficha de marketing (/mx/phones/x/) no sirve: precio, regalos y cupón se
        # arman en /mx/offer/<cat>/<slug>-buy/, que es a donde manda el botón Comprar.
        for item in items_basicos:
            if not item["link"]:
                productos.append({**item, "descuento_pct": None, "es_bundle": False, "regalos": []})
                continue

            try:
                print(f"[scraper] {item['nombre']}")
                url_compra = buscar_pagina_compra(item["link"])
                if not url_compra:
                    print("[scraper]   sin página de compra")
                    productos.append({**item, "descuento_pct": None, "es_bundle": False, "regalos": []})
                    continue

                page.goto(url_compra, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(11000)
                texto = page.inner_text("body")

                datos = leer_pagina_compra(texto)
                if datos["precio"]:
                    item["precio_actual"] = datos["precio"]
                if datos["precio_original"]:
                    item["precio_original"] = datos["precio_original"]

                p_act = item["precio_actual"]
                p_ori = item["precio_original"]
                descuento = None
                if p_act and p_ori and p_ori > p_act:
                    descuento = round((1 - p_act / p_ori) * 100)

                if datos["regalos"]:
                    print(f"[scraper]   regalos: {', '.join(datos['regalos'])}")

                productos.append({
                    "nombre": item["nombre"],
                    "categoria": item["categoria"],
                    "precio_actual": p_act,
                    "precio_original": p_ori,
                    "descuento_pct": descuento,
                    "es_bundle": bool(datos["regalos"]),
                    "badge": item["badge"],
                    "regalos": datos["regalos"],
                    "cupon": datos["cupon"],
                    "imagen": None,
                    "link": item["link"],
                    "link_compra": url_compra,
                })

            except Exception as e:
                print(f"[scraper] Error en {item['nombre']}: {e}")
                productos.append({**item, "descuento_pct": None, "es_bundle": False, "regalos": []})

        browser.close()

    return productos


def ejecutar_scraping():
    global _cache
    print(f"[scraper] Iniciando — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    productos = scrape_con_playwright()

    # Si la corrida salió vacía (bloqueo, cambio de HTML, caída de red) NO pisamos
    # los datos buenos del día anterior: mejor mostrar precios de ayer que nada.
    if not productos:
        print("[scraper] Corrida vacía — se conservan los datos anteriores")
        return cargar_datos()

    data = {
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(productos),
        "productos": productos,
    }
    _cache = data

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[scraper] No se pudo guardar: {e}")

    print(f"[scraper] Guardados {len(productos)} productos")
    return data


def cargar_datos():
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
