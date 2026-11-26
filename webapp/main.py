"""Web app de MercaRed Peru S.A.C.
Permite a las sucursales subir su CSV de ventas al bucket de entrada
y muestra los resultados que el procesador guardo en Firestore.
"""
import datetime
import os
from zoneinfo import ZoneInfo

from flask import Flask, redirect, render_template_string, request, url_for
from google.cloud import firestore, storage
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # maximo 5 MB por archivo
storage_client = storage.Client()
db = firestore.Client()

BUCKET_ENTRADA = os.environ["BUCKET_ENTRADA"]
LIMA = ZoneInfo("America/Lima")

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MercaRed - Ventas por sucursal</title>
<style>
 body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1f2937}
 header{background:#0f766e;color:#fff;padding:18px 32px}
 header h1{margin:0;font-size:22px} header p{margin:4px 0 0;opacity:.85;font-size:14px}
 main{max-width:1050px;margin:24px auto;padding:0 16px;display:grid;gap:20px}
 .card{background:#fff;border-radius:12px;padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
 h2{font-size:17px;margin:0 0 14px}
 .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
 .kpi{background:#f0fdfa;border-radius:10px;padding:14px}
 .kpi span{font-size:13px;color:#475569} .kpi b{display:block;font-size:22px;margin-top:4px;color:#0f766e}
 form{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
 button{background:#0f766e;color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:14px;cursor:pointer}
 .msg{padding:10px 14px;border-radius:8px;font-size:14px}
 .ok{background:#dcfce7;color:#166534} .err{background:#fee2e2;color:#991b1b}
 table{width:100%;border-collapse:collapse;font-size:14px}
 th,td{text-align:left;padding:8px 6px;border-bottom:1px solid #e5e7eb} th{color:#64748b;font-weight:600}
 .tag{padding:2px 8px;border-radius:999px;font-size:12px}
 .procesado{background:#dcfce7;color:#166534} .rechazado{background:#fee2e2;color:#991b1b}
 .bar{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:14px}
 .bar .name{width:130px} .bar .track{flex:1;background:#e2e8f0;border-radius:6px;height:18px}
 .bar .fill{background:#14b8a6;height:18px;border-radius:6px} .bar .val{width:110px;text-align:right}
 small{color:#64748b}
 @media(max-width:700px){.kpis{grid-template-columns:repeat(2,1fr)}}
</style></head><body>
<header><h1>MercaRed Peru S.A.C.</h1>
<p>Consolidacion automatica de ventas por sucursal &middot; Google Cloud (Cloud Run + Eventarc + Firestore)</p></header>
<main>
 <section class="card">
  <h2>Subir archivo de ventas (CSV)</h2>
  {% if mensaje %}<p class="msg {{ tipo }}">{{ mensaje }}</p>{% endif %}
  <form method="post" action="{{ url_for('subir') }}" enctype="multipart/form-data">
   <input type="file" name="archivo" accept=".csv" required>
   <button type="submit">Subir y procesar</button>
  </form>
  <p><small>Formato: fecha,sucursal,producto,cantidad,precio_unitario &middot; fecha AAAA-MM-DD &middot; maximo 5 MB.
  El procesamiento tarda unos segundos; esta pagina se actualiza sola.</small></p>
 </section>
 <section class="kpis">
  <div class="kpi"><span>Archivos procesados</span><b>{{ kpi.procesados }}</b></div>
  <div class="kpi"><span>Archivos rechazados</span><b>{{ kpi.rechazados }}</b></div>
  <div class="kpi"><span>Ventas registradas</span><b>{{ kpi.ventas }}</b></div>
  <div class="kpi"><span>Monto total</span><b>S/ {{ "{:,.2f}".format(kpi.monto) }}</b></div>
 </section>
 <section class="card">
  <h2>Ventas por sucursal</h2>
  {% for s in sucursales %}
   <div class="bar"><span class="name">{{ s.nombre }}</span>
    <div class="track"><div class="fill" style="width:{{ s.pct }}%"></div></div>
    <span class="val">S/ {{ "{:,.2f}".format(s.monto) }}</span></div>
  {% else %}<p><small>Aun no hay ventas procesadas.</small></p>{% endfor %}
 </section>
 <section class="card">
  <h2>Ultimos archivos recibidos</h2>
  <table><tr><th>Archivo</th><th>Estado</th><th>Detalle</th><th>Procesado (hora Lima)</th></tr>
  {% for a in archivos %}
   <tr><td>{{ a.archivo }}</td>
    <td><span class="tag {{ a.estado }}">{{ a.estado }}</span></td>
    <td>{% if a.estado == 'procesado' %}{{ a.filas }} filas &middot; S/ {{ "{:,.2f}".format(a.monto_total or 0) }}
        {% else %}{{ (a.errores or [])[:2]|join('; ') }}{% if (a.total_errores or 0) > 2 %} (+{{ a.total_errores - 2 }} mas){% endif %}{% endif %}</td>
    <td>{{ a.hora }}</td></tr>
  {% else %}<tr><td colspan="4"><small>Todavia no se ha recibido ningun archivo.</small></td></tr>{% endfor %}
  </table>
 </section>
</main>
<script>setTimeout(function(){ location.href = location.pathname; }, 15000);</script>
</body></html>"""


def resumen():
    """Lee Firestore y arma los datos que muestra la pagina."""
    archivos = []
    consulta = (db.collection("archivos")
                .order_by("procesado_en", direction=firestore.Query.DESCENDING)
                .limit(15))
    for doc in consulta.stream():
        a = doc.to_dict()
        fecha = a.get("procesado_en")
        a["hora"] = fecha.astimezone(LIMA).strftime("%d/%m/%Y %H:%M:%S") if fecha else "-"
        archivos.append(a)

    procesados = rechazados = 0
    for doc in db.collection("archivos").select(["estado"]).stream():
        if doc.to_dict().get("estado") == "procesado":
            procesados += 1
        else:
            rechazados += 1

    por_sucursal, n_ventas, monto = {}, 0, 0.0
    for doc in db.collection("ventas").select(["sucursal", "total"]).stream():
        v = doc.to_dict()
        por_sucursal[v["sucursal"]] = por_sucursal.get(v["sucursal"], 0) + v["total"]
        n_ventas += 1
        monto += v["total"]

    maximo = max(por_sucursal.values(), default=0) or 1
    sucursales = [{"nombre": k, "monto": m, "pct": round(m * 100 / maximo, 1)}
                  for k, m in sorted(por_sucursal.items(), key=lambda x: -x[1])]
    kpi = {"procesados": procesados, "rechazados": rechazados,
           "ventas": n_ventas, "monto": monto}
    return archivos, sucursales, kpi


@app.get("/")
def inicio():
    archivos, sucursales, kpi = resumen()
    return render_template_string(PAGINA, archivos=archivos, sucursales=sucursales, kpi=kpi,
                                  mensaje=request.args.get("m"), tipo=request.args.get("t", "ok"))


@app.post("/subir")
def subir():
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename.lower().endswith(".csv"):
        return redirect(url_for("inicio", m="Selecciona un archivo .csv", t="err"))
    marca = datetime.datetime.now(LIMA).strftime("%Y%m%d-%H%M%S")
    nombre = f"{marca}_{secure_filename(archivo.filename)}"
    blob = storage_client.bucket(BUCKET_ENTRADA).blob(nombre)
    blob.upload_from_file(archivo.stream, content_type="text/csv")
    return redirect(url_for("inicio", m=f"Archivo {nombre} recibido. Procesando...", t="ok"))


@app.errorhandler(413)
def muy_grande(_):
    return redirect(url_for("inicio", m="El archivo supera los 5 MB", t="err"))