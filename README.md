# Promos Huawei · HES Angelópolis 1217

Consulta de precios, descuentos y regalos vigentes de HUAWEI México, para el equipo de piso.

**App:** https://angeljesus8-blip.github.io/huawei-promos/

Tres pestañas:
- **📡 Online** — precios de consumer.huawei.com/mx (smartphones, tablets, wearables, laptops)
- **⚖️ vs Tienda** — compara esos precios contra las promos vigentes de la tienda (las lee del mismo Apps Script que el tablero)
- **🛍️ Liverpool** — precios de Huawei en liverpool.com.mx

## Cómo se actualiza

No hay servidor. **GitHub Actions** corre el scraping todos los días a las **15:00 UTC (9:00 AM CDMX)**,
guarda los resultados en `docs/promos.json` y `docs/liverpool.json`, y los commitea al repo.
GitHub Pages sirve `docs/` como sitio estático.

**Para actualizar a mano:** pestaña *Actions* → *Actualizar promos* → *Run workflow*. Tarda ~10-20 min.

Como cada corrida es un commit, el historial de git guarda cómo se movieron los precios día con día.

## Piezas

| Archivo | Qué hace |
|---|---|
| `scraper.py` | Playwright/Chromium sobre consumer.huawei.com/mx: precio, precio tachado, descuento y regalos |
| `scraper_liverpool.py` | Liverpool: lee `/tienda?s=<búsqueda>`, que trae los productos como JSON dentro del HTML |
| `run_scrape.py` | Entrypoint; si una fuente falla, la otra igual se actualiza |
| `docs/` | La app publicada (HTML + los JSON de datos) |
| `.github/workflows/scrape.yml` | El cron diario |
| `legacy/` | La versión anterior en Flask, que vivía en Railway (ya no se usa) |

Una corrida que sale vacía **no** sobrescribe los datos del día anterior: es preferible mostrar
precios de ayer que una pantalla en blanco.

## Sin llaves ni cuentas

No necesita secrets. Liverpool se leía antes con ScraperAPI (de paga, y su llave estaba
escrita en el código); al cambiar Liverpool a Next.js resultó que los productos vienen
en el HTML como JSON, así que una petición normal basta.

Buscar `huawei` a secas redirige a una landing sin precios: por eso se consulta por
categoría (`huawei celular`, `huawei tablet`, …) y se juntan los resultados.
