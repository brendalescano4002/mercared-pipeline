#!/bin/bash
# =============================================================
# MercaRed - Script 06: Prueba de carga (autoescalado)
# Genera muchos CSV de ventas (algunos con errores) y los sube
# de golpe al bucket de entrada para ver escalar al procesador.
# Uso:  bash scripts/06-prueba-carga.sh [cantidad_de_archivos]
# =============================================================
CANTIDAD=${1:-150}
source "$(dirname "$0")/00-variables.sh"
BUCKET=gs://$BUCKET_ENTRADA
CARPETA=pruebas/carga

echo ">> Generando $CANTIDAD archivos en $CARPETA ..."
rm -rf "$CARPETA" && mkdir -p "$CARPETA"
python3 - "$CANTIDAD" "$CARPETA" << 'EOF'
import random, sys, datetime
cantidad, carpeta = int(sys.argv[1]), sys.argv[2]
sucursales = ["Miraflores", "San Isidro", "Surco", "La Molina", "San Borja",
              "Chorrillos", "Los Olivos", "San Miguel", "Ate", "Villa El Salvador"]
productos = {"Arroz 5kg": 22.5, "Aceite 1L": 9.9, "Leche 1L": 4.2, "Azucar 1kg": 4.5,
             "Fideos 500g": 3.8, "Gaseosa 3L": 10.5, "Pan molde": 7.9,
             "Detergente 2kg": 24.0, "Atun lata": 6.3, "Huevos x15": 11.0}
hoy = datetime.date(2026, 11, 26)
for i in range(1, cantidad + 1):
    sucursal = random.choice(sucursales)
    con_error = random.random() < 0.10          # 10% de archivos con errores
    lineas = ["fecha,sucursal,producto,cantidad,precio_unitario"]
    for _ in range(random.randint(10, 30)):
        producto = random.choice(list(productos))
        fecha = (hoy - datetime.timedelta(days=random.randint(0, 6))).isoformat()
        lineas.append(f"{fecha},{sucursal},{producto},{random.randint(1, 30)},{productos[producto]}")
    if con_error:
        lineas.append(f"26/11/2026,{sucursal},Arroz 5kg,-5,22.5")
    nombre = f"{carpeta}/carga_{i:04d}_{sucursal.replace(' ', '')}.csv"
    with open(nombre, "w") as f:
        f.write("\n".join(lineas) + "\n")
EOF

echo ">> Subiendo los archivos en paralelo al bucket de entrada ..."
INICIO=$(date +%s)
gcloud storage cp "$CARPETA"/*.csv "$BUCKET"/
echo ">> Subida terminada en $(( $(date +%s) - INICIO )) segundos."
echo ">> Ahora revisa el dashboard: el grafico de instancias deberia subir en 1-2 minutos."
