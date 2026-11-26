#!/bin/bash
# =============================================================
# MercaRed - Script 05: Monitoreo (metricas, alertas y dashboard)
# Ejecutar desde la carpeta mercared-pipeline:
#   bash scripts/05-monitoreo.sh
# =============================================================
P=project-df7f91a3-445f-4d8d-a17
CORREO=brendalescano4002@gmail.com
mkdir -p monitoreo

echo ">> 1. Metricas basadas en logs (cuentan archivos procesados y rechazados)"
gcloud logging metrics create archivos_procesados \
  --description="Archivos de ventas procesados correctamente" \
  --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="procesador" AND jsonPayload.message="Archivo procesado"'
gcloud logging metrics create archivos_rechazados \
  --description="Archivos de ventas rechazados por errores" \
  --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="procesador" AND jsonPayload.message="Archivo rechazado"'

echo ">> 2. Canal de notificacion por correo"
CANAL=$(gcloud beta monitoring channels create \
  --display-name="Correo MercaRed" --type=email \
  --channel-labels=email_address=$CORREO --format="value(name)")
echo "Canal creado: $CANAL"

echo ">> 3. Politicas de alerta"
cat > monitoreo/alerta-rechazados.json << EOF
{
  "displayName": "MercaRed - Muchos archivos rechazados",
  "combiner": "OR",
  "conditions": [{
    "displayName": "Mas de 3 archivos rechazados en 10 minutos",
    "conditionThreshold": {
      "filter": "metric.type=\"logging.googleapis.com/user/archivos_rechazados\" AND resource.type=\"cloud_run_revision\"",
      "aggregations": [{"alignmentPeriod": "600s", "perSeriesAligner": "ALIGN_SUM", "crossSeriesReducer": "REDUCE_SUM"}],
      "comparison": "COMPARISON_GT",
      "thresholdValue": 3,
      "duration": "0s",
      "trigger": {"count": 1}
    }
  }],
  "notificationChannels": ["$CANAL"],
  "documentation": {"content": "Varias sucursales estan enviando archivos con errores. Revisar el bucket de rechazados.", "mimeType": "text/markdown"}
}
EOF
cat > monitoreo/alerta-cpu.json << EOF
{
  "displayName": "MercaRed - CPU alta en el procesador",
  "combiner": "OR",
  "conditions": [{
    "displayName": "CPU del procesador mayor a 80% por 1 minuto",
    "conditionThreshold": {
      "filter": "metric.type=\"run.googleapis.com/container/cpu/utilizations\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"procesador\"",
      "aggregations": [{"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_PERCENTILE_99", "crossSeriesReducer": "REDUCE_MAX"}],
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0.8,
      "duration": "60s",
      "trigger": {"count": 1}
    }
  }],
  "notificationChannels": ["$CANAL"],
  "documentation": {"content": "El procesador esta con carga alta de CPU. Verificar el autoescalado en el dashboard.", "mimeType": "text/markdown"}
}
EOF
gcloud alpha monitoring policies create --policy-from-file=monitoreo/alerta-rechazados.json
gcloud alpha monitoring policies create --policy-from-file=monitoreo/alerta-cpu.json

echo ">> 4. Dashboard"
cat > monitoreo/dashboard.json << 'EOF'
{
  "displayName": "MercaRed - Pipeline de ventas",
  "gridLayout": {
    "columns": "2",
    "widgets": [
      {"title": "Instancias activas del procesador (autoescalado)",
       "xyChart": {"dataSets": [{"plotType": "LINE", "legendTemplate": "Instancias",
         "timeSeriesQuery": {"timeSeriesFilter": {
           "filter": "metric.type=\"run.googleapis.com/container/instance_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"procesador\"",
           "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_MAX", "crossSeriesReducer": "REDUCE_SUM"}}}}]}},
      {"title": "Archivos procesados vs rechazados (por minuto)",
       "xyChart": {"dataSets": [
         {"plotType": "STACKED_BAR", "legendTemplate": "Procesados",
          "timeSeriesQuery": {"timeSeriesFilter": {
            "filter": "metric.type=\"logging.googleapis.com/user/archivos_procesados\" AND resource.type=\"cloud_run_revision\"",
            "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_SUM", "crossSeriesReducer": "REDUCE_SUM"}}}},
         {"plotType": "STACKED_BAR", "legendTemplate": "Rechazados",
          "timeSeriesQuery": {"timeSeriesFilter": {
            "filter": "metric.type=\"logging.googleapis.com/user/archivos_rechazados\" AND resource.type=\"cloud_run_revision\"",
            "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_SUM", "crossSeriesReducer": "REDUCE_SUM"}}}}]}},
      {"title": "Solicitudes al procesador por codigo de respuesta",
       "xyChart": {"dataSets": [{"plotType": "STACKED_BAR",
         "timeSeriesQuery": {"timeSeriesFilter": {
           "filter": "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"procesador\"",
           "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_SUM", "crossSeriesReducer": "REDUCE_SUM", "groupByFields": ["metric.label.response_code_class"]}}}}]}},
      {"title": "Latencia del procesador (percentil 95, ms)",
       "xyChart": {"dataSets": [{"plotType": "LINE", "legendTemplate": "p95",
         "timeSeriesQuery": {"timeSeriesFilter": {
           "filter": "metric.type=\"run.googleapis.com/request_latencies\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"procesador\"",
           "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_PERCENTILE_95", "crossSeriesReducer": "REDUCE_MAX"}}}}]}},
      {"title": "Uso de CPU del procesador (p99)",
       "xyChart": {"dataSets": [{"plotType": "LINE", "legendTemplate": "CPU",
         "timeSeriesQuery": {"timeSeriesFilter": {
           "filter": "metric.type=\"run.googleapis.com/container/cpu/utilizations\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"procesador\"",
           "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_PERCENTILE_99", "crossSeriesReducer": "REDUCE_MAX"}}}}]}},
      {"title": "Visitas a la pagina web",
       "xyChart": {"dataSets": [{"plotType": "LINE", "legendTemplate": "Solicitudes",
         "timeSeriesQuery": {"timeSeriesFilter": {
           "filter": "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"webapp\"",
           "aggregation": {"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_SUM", "crossSeriesReducer": "REDUCE_SUM"}}}}]}}
    ]
  }
}
EOF
gcloud monitoring dashboards create --config-from-file=monitoreo/dashboard.json

echo ""
echo "=== Monitoreo listo ==="
echo "Dashboard: https://console.cloud.google.com/monitoring/dashboards?project=$P"