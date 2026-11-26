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
<title>MercaRed | Consolidado de ventas</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
 body{background:#eef1f5;font-size:.92rem}
 .navbar{background:#16233d}
 .navbar-brand b{color:#fff;letter-spacing:.5px} .navbar-brand small{color:#9fb0cc;font-size:.75rem}
 .titulo{border-bottom:2px solid #16233d}
 .card-header{background:#f7f8fa;font-weight:600;color:#16233d}
 .indicador{border-left:4px solid #1f4e8c}
 .indicador .valor{font-size:1.45rem;font-weight:600;color:#16233d}
 .progress{height:.9rem} .progress-bar{background:#1f4e8c}
 .btn-primary{background:#1f4e8c;border-color:#1f4e8c}
 footer{color:#6c7a91;font-size:.8rem}
</style></head><body>
<nav class="navbar navbar-dark px-4 py-2">
 <span class="navbar-brand mb-0"><b>MercaRed</b> <small>Sistema de Consolidacion de Ventas</small></span>
 <span class="text-light small">Area de Operaciones &middot; Sede Central</span>
</nav>
<div class="container-lg py-4">
 <div class="d-flex justify-content-between align-items-end titulo pb-2 mb-4">
  <div><h5 class="mb-0">Consolidado de ventas por sucursal</h5>
   <span class="text-muted small">Ultima actualizacion: {{ actualizado }} (hora Lima)</span></div>
  <a href="/" class="btn btn-outline-secondary btn-sm">Actualizar</a>
 </div>
 {% if mensaje %}<div class="alert alert-{{ 'danger' if tipo == 'err' else 'success' }} py-2">{{ mensaje }}</div>{% endif %}
 <div class="row g-3 mb-4">
  <div class="col-lg-5">
   <div class="card h-100"><div class="card-header">Cargar archivo de ventas</div>
    <div class="card-body">
     <form method="post" action="{{ url_for('subir') }}" enctype="multipart/form-data">
      <input class="form-control form-control-sm mb-2" type="file" name="archivo" accept=".csv" required>
      <button class="btn btn-primary btn-sm" type="submit">Enviar archivo</button>
     </form>
     <ul class="small text-muted mt-3 mb-0 ps-3">
      <li>Columnas: fecha, sucursal, producto, cantidad, precio_unitario</li>
      <li>Fecha en formato AAAA-MM-DD. Tamano maximo: 5 MB</li>
      <li>El archivo se procesa automaticamente en pocos segundos</li>
     </ul>
    </div></div>
  </div>
  <div class="col-lg-7">
   <div class="row g-3">
    <div class="col-6"><div class="card indicador"><div class="card-body py-2">
     <div class="text-muted small">Archivos procesados</div><div class="valor">{{ kpi.procesados }}</div></div></div></div>
    <div class="col-6"><div class="card indicador" style="border-left-color:#b02a37"><div class="card-body py-2">
     <div class="text-muted small">Archivos rechazados</div><div class="valor">{{ kpi.rechazados }}</div></div></div></div>
    <div class="col-6"><div class="card indicador"><div class="card-body py-2">
     <div class="text-muted small">Lineas de venta registradas</div><div class="valor">{{ "{:,}".format(kpi.ventas) }}</div></div></div></div>
    <div class="col-6"><div class="card indicador"><div class="card-body py-2">
     <div class="text-muted small">Monto total vendido</div><div class="valor">S/ {{ "{:,.2f}".format(kpi.monto) }}</div></div></div></div>
   </div>
  </div>
 </div>
 <div class="card mb-4"><div class="card-header">Ventas por sucursal</div>
  <div class="card-body p-0">
   <table class="table table-sm align-middle mb-0">
    <thead class="table-light"><tr><th class="ps-3">Sucursal</th><th style="width:50%">Participacion</th><th class="text-end pe-3">Monto (S/)</th></tr></thead>
    <tbody>
    {% for s in sucursales %}
     <tr><td class="ps-3">{{ s.nombre }}</td>
      <td><div class="progress"><div class="progress-bar" style="width:{{ s.pct }}%"></div></div></td>
      <td class="text-end pe-3">{{ "{:,.2f}".format(s.monto) }}</td></tr>
    {% else %}<tr><td colspan="3" class="ps-3 text-muted">Aun no hay ventas procesadas.</td></tr>{% endfor %}
    </tbody></table>
  </div></div>
 <div class="card"><div class="card-header">Ultimos archivos recibidos</div>
  <div class="card-body p-0">
   <table class="table table-sm table-striped mb-0">
    <thead class="table-light"><tr><th class="ps-3">Archivo</th><th>Estado</th><th>Detalle</th><th class="pe-3">Fecha y hora</th></tr></thead>
    <tbody>
    {% for a in archivos %}
     <tr><td class="ps-3">{{ a.archivo }}</td>
      <td>{% if a.estado == 'procesado' %}<span class="badge text-bg-success">Procesado</span>{% else %}<span class="badge text-bg-danger">Rechazado</span>{% endif %}</td>
      <td>{% if a.estado == 'procesado' %}{{ a.filas }} lineas &middot; S/ {{ "{:,.2f}".format(a.monto_total or 0) }}
          {% else %}{{ (a.errores or [])[:2]|join('; ') }}{% if (a.total_errores or 0) > 2 %} (+{{ a.total_errores - 2 }} mas){% endif %}{% endif %}</td>
      <td class="pe-3 text-nowrap">{{ a.hora }}</td></tr>
    {% else %}<tr><td colspan="4" class="ps-3 text-muted">Todavia no se ha recibido ningun archivo.</td></tr>{% endfor %}
    </tbody></table>
  </div></div>
 <footer class="text-center mt-4">MercaRed Peru S.A.C. &middot; Area de Tecnologia &middot; v1.1</footer>
</div>
<script>setTimeout(function(){ location.href = location.pathname; }, 30000);</script>
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
    actualizado = datetime.datetime.now(LIMA).strftime("%d/%m/%Y %H:%M:%S")
    return render_template_string(PAGINA, archivos=archivos, sucursales=sucursales, kpi=kpi,
                                  actualizado=actualizado, mensaje=request.args.get("m"),
                                  tipo=request.args.get("t", "ok"))


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