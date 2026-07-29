"""Diagnóstico temporal: dónde viaja el obsequio en la página de producto.

Registra las respuestas de red (el precio y las promos llegan por API, no en el HTML)
y revisa el texto ya renderizado, con scroll para disparar la carga diferida.
"""
import json
import re
import sys

from playwright.sync_api import sync_playwright

URLS = [
    "https://consumer.huawei.com/mx/phones/pura90s-pro-max/",
    "https://consumer.huawei.com/mx/tablets/matepad-pro-13-2/",
]

TERMINOS = ["regalo", "obsequio", "gratis", "cortes", "llévate", "llevate",
            "gift", "promoc", "bundle", "combo"]

capturas = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            locale="es-MX",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "es-MX,es;q=0.9"},
        )
        page = ctx.new_page()

        def on_response(resp):
            url = resp.url
            if not re.search(r"api|product|price|prd|sku|promo", url, re.I):
                return
            try:
                if "json" not in (resp.headers.get("content-type") or ""):
                    return
                cuerpo = resp.text()
            except Exception:
                return
            marcas = [t for t in TERMINOS if t in cuerpo.lower()]
            tiene_precio = bool(re.search(r'"(price|salePrice|obligatePrice)"\s*:', cuerpo))
            if marcas or tiene_precio:
                capturas.append((url, resp.status, marcas, tiene_precio, len(cuerpo), cuerpo))

        page.on("response", on_response)

        for url in URLS:
            print("=" * 78)
            print(url)
            capturas.clear()
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                # El buy box carga tarde y por scroll
                for _ in range(6):
                    page.mouse.wheel(0, 1200)
                    page.wait_for_timeout(1500)
                page.wait_for_timeout(8000)
                texto = page.inner_text("body")
            except Exception as e:
                print("  ERROR:", e)
                continue

            print(f"  texto renderizado: {len(texto)} caracteres")
            for t in TERMINOS:
                m = re.search(re.escape(t), texto, re.I)
                if m:
                    frag = re.sub(r"\s+", " ", texto[max(0, m.start() - 80):m.start() + 160])
                    print(f"  TEXTO [{t}] …{frag}…")

            print(f"  respuestas JSON interesantes: {len(capturas)}")
            for url_r, status, marcas, precio, largo, cuerpo in capturas[:6]:
                print(f"   - {status} {url_r[:110]}")
                print(f"     marcas={marcas} precio={precio} bytes={largo}")
                for t in marcas[:2]:
                    m = re.search(re.escape(t), cuerpo, re.I)
                    print(f"     ...{re.sub(chr(92)+'s+', ' ', cuerpo[max(0,m.start()-140):m.start()+200])}...")

        browser.close()


if __name__ == "__main__":
    sys.exit(main())
