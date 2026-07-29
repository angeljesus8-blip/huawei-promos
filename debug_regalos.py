"""Diagnóstico temporal: ¿con qué palabras aparece el obsequio en la página renderizada?

Se corre en Actions (donde sí hay Chromium) y vuelca al log los fragmentos de texto
que contengan cualquier término relacionado con regalos, para ver cuál usa Huawei hoy.
"""
import re
import sys

from playwright.sync_api import sync_playwright

URLS = [
    "https://consumer.huawei.com/mx/phones/pura90s-pro-max/",
    "https://consumer.huawei.com/mx/phones/pura80-pro/",
    "https://consumer.huawei.com/mx/tablets/matepad-pro-13-2/",
]

TERMINOS = ["regalo", "obsequio", "gratis", "cortesía", "cortesia",
            "llévate", "llevate", "incluye", "bundle", "gift", "promoción", "promocion"]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_context(
            locale="es-MX",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900},
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
            for termino in TERMINOS:
                for m in re.finditer(re.escape(termino), texto, re.I):
                    frag = re.sub(r"\s+", " ", texto[max(0, m.start() - 90):m.start() + 150])
                    print(f"  [{termino}] …{frag}…")
                    break  # una muestra por término basta

            # Elementos que parezcan etiqueta de promoción
            for sel in [".product-label", "[class*='label']", "[class*='gift']", "[class*='promo']"]:
                try:
                    textos = [t.strip() for t in page.locator(sel).all_inner_texts() if t.strip()]
                except Exception:
                    textos = []
                if textos:
                    print(f"  sel {sel}: {textos[:6]}")

        browser.close()


if __name__ == "__main__":
    sys.exit(main())
