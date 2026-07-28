from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import ejecutar_scraping, cargar_datos
from scraper_liverpool_api import ejecutar_scraping_liverpool, cargar_datos_liverpool
import threading
import os
import requests as req

app = Flask(__name__)

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwbZFsiDqZrNitPKNLqr4r6xOFu3VKprtXJacScftIJmcQdAl_yytjxK8BymWvy8I1gjA/exec"

_scraping_en_progreso = False

def _scraping_diario():
    global _scraping_en_progreso
    if _scraping_en_progreso:
        return
    _scraping_en_progreso = True
    try:
        ejecutar_scraping()
        ejecutar_scraping_liverpool()
    finally:
        _scraping_en_progreso = False

scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(_scraping_diario, "cron", hour=15, minute=0)
scheduler.start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/promos")
def api_promos():
    categoria = request.args.get("categoria", "todas")
    solo_descuento = request.args.get("descuento") == "1"
    solo_regalo = request.args.get("regalo") == "1"

    data = cargar_datos()
    productos = data.get("productos", [])

    if categoria != "todas":
        productos = [p for p in productos if p["categoria"].lower() == categoria.lower()]
    if solo_descuento:
        productos = [p for p in productos if p.get("descuento_pct")]
    if solo_regalo:
        productos = [p for p in productos if p.get("regalos")]

    return jsonify({
        "ultima_actualizacion": data.get("ultima_actualizacion"),
        "total": len(productos),
        "productos": productos,
        "scraping_en_progreso": _scraping_en_progreso,
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    global _scraping_en_progreso
    if _scraping_en_progreso:
        return jsonify({"ok": False, "mensaje": "Ya hay un scraping en progreso"})

    def _run():
        global _scraping_en_progreso
        _scraping_en_progreso = True
        try:
            ejecutar_scraping()
            ejecutar_scraping_liverpool()
        finally:
            _scraping_en_progreso = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"ok": True, "mensaje": "Scraping iniciado, espera ~3 minutos y recarga"})


@app.route("/api/liverpool")
def api_liverpool():
    data = cargar_datos_liverpool()
    return jsonify(data)


@app.route("/api/comparativa")
def api_comparativa():
    from datetime import date

    try:
        r_promos = req.get(APPS_SCRIPT_URL + "?modo=promos", timeout=10)
        promos_tienda = r_promos.json()
    except Exception as e:
        return jsonify({"error": f"No se pudo obtener promos de tienda: {e}"}), 500

    try:
        r_cat = req.get(APPS_SCRIPT_URL + "?modo=catalogo", timeout=10)
        catalogo = r_cat.json()
    except Exception:
        catalogo = {}

    sku_a_nombre = {}
    for upc, info in catalogo.items():
        sku = info.get("s", "")
        desc = info.get("d", "")
        if sku and desc:
            sku_a_nombre[sku] = desc

    hoy = date.today().isoformat()
    tienda = []
    for sku, pr in promos_tienda.items():
        if pr.get("d2") and hoy > pr["d2"]:
            continue
        nombre = sku_a_nombre.get(sku, sku)
        tienda.append({
            "sku": sku,
            "nombre": nombre,
            "precio_tienda": pr.get("pp"),
            "vigencia": pr.get("d2"),
        })

    data_online = cargar_datos()
    productos_online = data_online.get("productos", [])

    def palabras_clave(nombre):
        stop = {"huawei", "de", "y", "el", "la", "pro", "ultra", "max", "nuevo", "nueva", "series"}
        return {w.lower() for w in nombre.replace("-", " ").split() if w.lower() not in stop and len(w) > 2}

    comparativa = []
    for item in tienda:
        claves_tienda = palabras_clave(item["nombre"])
        mejor = None
        mejor_score = 0
        for p in productos_online:
            claves_online = palabras_clave(p["nombre"])
            score = len(claves_tienda & claves_online)
            if score > mejor_score:
                mejor_score = score
                mejor = p

        precio_online = mejor["precio_actual"] if mejor and mejor_score >= 2 else None
        nombre_online = mejor["nombre"] if mejor and mejor_score >= 2 else None

        try:
            pt = int(float(str(item["precio_tienda"]).replace(",", "").replace("$", "").strip())) if item["precio_tienda"] else None
            item["precio_tienda"] = pt
        except Exception:
            item["precio_tienda"] = None

        diff = None
        if item["precio_tienda"] and precio_online:
            diff = item["precio_tienda"] - precio_online

        comparativa.append({
            "sku": item["sku"],
            "nombre_tienda": item["nombre"],
            "nombre_online": nombre_online,
            "precio_tienda": item["precio_tienda"],
            "precio_online": precio_online,
            "diferencia": diff,
            "vigencia": item["vigencia"],
        })

    return jsonify({"comparativa": comparativa, "total": len(comparativa)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
