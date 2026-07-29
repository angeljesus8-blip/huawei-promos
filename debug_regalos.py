"""Diagnóstico temporal: ¿la página de compra renderiza el regalo desde Actions?

La ficha de marketing (/mx/phones/x/) no trae el bloque de compra. El obsequio vive
en la página de oferta (/mx/offer/<cat>/<slug>-buy/?productId=...), que es a donde
apunta el botón Comprar.
"""
import re
import sys

from playwright.sync_api import sync_playwright

URLS = [
    "https://consumer.huawei.com/mx/offer/telefonos/pura90s-pro-buy/?productId=10052119644151",
    "https://consumer.huawei.com/mx/offer/tablets/matepad-pro-13-2-2025-buy/",
]

TERMINOS = ["regalo gratis", "regalo", "gratis", "freebuds", "servicio premium",
            "ahorra", "cantidad", "comprar"]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_context(
            locale="es-MX",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1400, "height": 950},
            extra_http_headers={"Accept-Language": "es-MX,es;q=0.9"},
        ).new_page()

        for url in URLS:
            print("=" * 78)
            print(url)
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(12000)
                texto = page.inner_text("body")
            except Exception as e:
                print("  ERROR:", e)
                continue

            print(f"  texto renderizado: {len(texto)} caracteres")
            for t in TERMINOS:
                m = re.search(re.escape(t), texto, re.I)
                if m:
                    frag = re.sub(r"\s+", " ", texto[max(0, m.start() - 100):m.start() + 260])
                    print(f"  [{t}] …{frag}…")

            # Precios visibles
            print("  precios:", re.findall(r"\$\s?[0-9][0-9,]{2,}", texto)[:8])

            # Si aparece el bloque, ver con qué clases se llama
            for sel in ["[class*='gift']", "[class*='regalo']", "[class*='promo']",
                        "[class*='present']", "[class*='free']"]:
                try:
                    textos = [t.strip().replace("\n", " | ")[:90]
                              for t in page.locator(sel).all_inner_texts() if t.strip()]
                except Exception:
                    textos = []
                if textos:
                    print(f"  sel {sel}: {textos[:4]}")

        browser.close()


if __name__ == "__main__":
    sys.exit(main())
