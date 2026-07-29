"""Diagnóstico temporal: cómo se ve el precio en las buy pages que no lo sueltan."""
import re

from playwright.sync_api import sync_playwright

URLS = [
    "https://consumer.huawei.com/mx/offer/telefonos/mate-x6-buy/",
    "https://consumer.huawei.com/mx/offer/telefonos/nova-y73-buy/",
    "https://consumer.huawei.com/mx/offer/telefonos/nova13-buy/",
]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = b.new_context(
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
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(11000)
            texto = page.inner_text("body")
        except Exception as e:
            print("  ERROR:", e)
            continue

        print(f"  {len(texto)} caracteres · precios vistos: {re.findall(r'[$]\s?[0-9][0-9,]{2,}', texto)[:10]}")
        for marca in ["Añadir a la cesta", "Agotado", "Comprar", "o hasta", "Notifícame", "No disponible"]:
            m = re.search(re.escape(marca), texto, re.I)
            if m:
                frag = re.sub(r"\s+", " ", texto[max(0, m.start() - 220):m.start() + 90])
                print(f"  [{marca}] …{frag}…")
    b.close()
