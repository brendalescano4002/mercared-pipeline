"""Procesador de archivos de ventas - MercaRed Peru S.A.C.
Recibe el evento de Eventarc cuando llega un CSV al bucket de entrada,
valida las filas y guarda las ventas en Firestore.
Si el archivo tiene errores, lo mueve al bucket de rechazados.
"""
import csv
import datetime
import io
import json
import os
import time

from flask import Flask, request
from google.cloud import firestore, storage

app = Flask(__name__)
storage_client = storage.Client()
db = firestore.Client()

BUCKET_RECHAZADOS = os.environ["BUCKET_RECHAZADOS"]
COLUMNAS = ["fecha", "sucursal", "producto", "cantidad", "precio_unitario"]


def log(severidad, mensaje, **campos):
    """Escribe un log estructurado que Cloud Logging entiende."""
    print(json.dumps({"severity": severidad, "message": mensaje, **campos}), flush=True)


def validar_fila(fila, n):
    """Revisa una fila del CSV y devuelve (errores, cantidad, precio)."""
    errores = []
    cantidad = precio = None
    try:
        datetime.date.fromisoformat(fila.get("fecha", ""))
    except ValueError:
        errores.append(f"fila {n}: fecha invalida (usar AAAA-MM-DD)")
    if not fila.get("sucursal"):
        errores.append(f"fila {n}: falta la sucursal")
    if not fila.get("producto"):
        errores.append(f"fila {n}: falta el producto")
    try:
        cantidad = int(fila.get("cantidad", ""))
        if cantidad <= 0:
            errores.append(f"fila {n}: la cantidad debe ser mayor a 0")
    except ValueError:
        errores.append(f"fila {n}: cantidad no numerica")
    try:
        precio = float(fila.get("precio_unitario", ""))
        if precio < 0:
            errores.append(f"fila {n}: precio negativo")
    except ValueError:
        errores.append(f"fila {n}: precio no numerico")
    return errores, cantidad, precio


@app.post("/")
def procesar():
    evento = request.get_json(silent=True) or {}
    bucket_nombre = evento.get("bucket")
    archivo = evento.get("name")
    if not bucket_nombre or not archivo:
        return ("Evento sin archivo", 400)
    if not archivo.lower().endswith(".csv"):
        log("INFO", "Archivo ignorado (no es CSV)", archivo=archivo)
        return ("Ignorado", 200)

    inicio = time.time()
    bucket = storage_client.bucket(bucket_nombre)
    blob = bucket.blob(archivo)
    if not blob.exists():
        # Reintento de un evento ya procesado (el archivo ya fue movido)
        return ("Ya procesado", 200)

    contenido = blob.download_as_text(encoding="utf-8-sig")
    lector = csv.DictReader(io.StringIO(contenido))
    errores, ventas = [], []

    cabecera = [c.strip().lower() for c in (lector.fieldnames or [])]
    if cabecera != COLUMNAS:
        errores.append("cabecera invalida, se esperaba: " + ",".join(COLUMNAS))
    else:
        for n, fila in enumerate(lector, start=2):
            fila = {k.strip().lower(): (v or "").strip() for k, v in fila.items() if k}
            errs, cantidad, precio = validar_fila(fila, n)
            if errs:
                errores.extend(errs)
                continue
            ventas.append({
                "fecha": fila["fecha"],
                "sucursal": fila["sucursal"],
                "producto": fila["producto"],
                "cantidad": cantidad,
                "precio_unitario": precio,
                "total": round(cantidad * precio, 2),
                "archivo": archivo,
            })
        if not ventas and not errores:
            errores.append("el archivo no tiene filas de datos")

    id_archivo = archivo.replace("/", "_")
    doc_archivo = db.collection("archivos").document(id_archivo)
    duracion = round(time.time() - inicio, 3)

    if errores:
        # Archivo rechazado: se mueve completo al bucket de rechazados
        bucket.copy_blob(blob, storage_client.bucket(BUCKET_RECHAZADOS), archivo)
        blob.delete()
        doc_archivo.set({
            "archivo": archivo,
            "estado": "rechazado",
            "errores": errores[:20],
            "total_errores": len(errores),
            "procesado_en": firestore.SERVER_TIMESTAMP,
        })
        log("WARNING", "Archivo rechazado", archivo=archivo,
            total_errores=len(errores), duracion_seg=duracion)
        return ("Rechazado", 200)

    # Archivo valido: se guardan las ventas en lotes de 400
    lote = db.batch()
    for i, venta in enumerate(ventas):
        lote.set(db.collection("ventas").document(f"{id_archivo}-{i}"), venta)
        if (i + 1) % 400 == 0:
            lote.commit()
            lote = db.batch()
    lote.commit()

    total = round(sum(v["total"] for v in ventas), 2)
    doc_archivo.set({
        "archivo": archivo,
        "estado": "procesado",
        "filas": len(ventas),
        "monto_total": total,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    log("INFO", "Archivo procesado", archivo=archivo, filas=len(ventas),
        monto_total=total, duracion_seg=duracion)
    return ("OK", 200)