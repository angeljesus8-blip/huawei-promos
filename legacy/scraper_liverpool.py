import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

DATA_FILE = "liverpool.json"
_cache_liverpool = None

URLS_LIVERPOOL = [
    "https://www.liverpool.com.mx/tienda/marcas/huawei?Nrpp=96",
]


def limpiar_precio(texto):
    if not texto:
        return None
    limpio = texto.replace("$", "").replace(",", "").replace("MXN", "").replace("\xa0", "").strip()
    try:
        return int(float(limpio))
    except ValueError:
        return None


def scrape_liverpool():
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

        for url in URLS_LIVERPOOL:
            print(f"[liverpool] Visitando {url}")
            try:
                page.goto(url, timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(7000)

                # Selectores comunes de Liverpool
                tarjetas = page.query_selector_all(
                    ".product-item, .product-card, [class*='ProductItem'], "
                    "[class*='product-item'], [class*='productCard'], "
                    "li[class*='item'], [data-id]"
                )
                print(f"[liverpool] {len(tarjetas)} tarjetas encontradas")

                # Si no encontró tarjetas, guarda el texto para debug
                if not tarjetas:
                    texto = page.inner_text("body")[:2000]
                    print(f"[liverpool] Sin tarjetas. Texto: {texto}")

                vistos = set()
                for tarjeta in tarjetas:
                    try:
                        nombre_el = tarjeta.query_selector(
                            ".product-name, .name, h2, h3, [class*='name'], [class*='Name'], [class*='title']"
                        )
                        precio_el = tarjeta.query_selector(
                            "[class*='price']:not([class*='original']):not([class*='old']), "
                            ".price, .current-price, [class*='Price']:not([class*='Original'])"
                        )
                        precio_original_el = tarjeta.query_selector(
                            ".original-price, .old-price, del, s, [class*='original'], [class*='tachado']"
                        )
                        link_el = tarjeta.query_selector("a")

                        nombre = nombre_el.inner_text().strip() if nombre_el else None
                        if not nombre or nombre in vistos or "huawei" not in nombre.lower():
                            continue
                        vistos.add(nombre)

                        precio_actual = limpiar_precio(precio_el.inner_text() if precio_el else None)
                        precio_original = limpiar_precio(precio_original_el.inner_text() if precio_original_el else None)

                        descuento = None
                        if precio_actual and precio_original and precio_original > precio_actual:
                            descuento = round((1 - precio_actual / precio_original) * 100)

                        href = link_el.get_attribute("href") if link_el else None
                        link = None
                        if href:
                            link = href if href.startswith("http") else f"https://www.liverpool.com.mx{href}"

                        productos.append({
                            "nombre": nombre,
                            "precio_actual": precio_actual,
                            "precio_original": precio_original,
                            "descuento_pct": descuento,
                            "link": link,
                        })

                    except Exception as e:
                        print(f"[liverpool] Error tarjeta: {e}")

            except Exception as e:
                print(f"[liverpool] Error visitando {url}: {e}")

        browser.close()

    return productos


def ejecutar_scraping_liverpool():
    global _cache_liverpool
    print(f"[liverpool] Iniciando — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    productos = scrape_liverpool()

    data = {
        "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(productos),
        "productos": productos,
    }
    _cache_liverpool = data

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[liverpool] No se pudo guardar: {e}")

    print(f"[liverpool] Guardados {len(productos)} productos")
    return data


def cargar_datos_liverpool():
    global _cache_liverpool
    if _cache_liverpool and _cache_liverpool.get("total", 0) > 0:
        return _cache_liverpool
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                data = json.load(f)
                _cache_liverpool = data
                return data
        except Exception:
            pass
    return {"ultima_actualizacion": None, "total": 0, "productos": []}
