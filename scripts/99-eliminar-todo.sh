#!/bin/bash
# =============================================================
# MercaRed - Script 99: ELIMINA todos los recursos del proyecto
# Usar SOLO despues de la sustentacion, para no consumir credito.
# Uso: bash scripts/99-eliminar-todo.sh
# =============================================================
source "$(dirname "$0")/00-variables.sh"
read -p "Esto borra TODO el proyecto MercaRed en $PROJECT_ID. Escribe ELIMINAR para continuar: " R
[ "$R" = "ELIMINAR" ] || { echo "Cancelado."; exit 1; }

gcloud eventarc triggers delete trigger-nuevo-archivo --location="$REGION" --quiet
gcloud run services delete procesador --region="$REGION" --quiet
gcloud run services delete webapp --region="$REGION" --quiet
gcloud storage rm -r "gs://$BUCKET_ENTRADA" "gs://$BUCKET_RECHAZADOS"
gcloud firestore databases delete --database="(default)" --quiet
for D in $(gcloud monitoring dashboards list --filter="displayName~MercaRed" --format="value(name)"); do
  gcloud monitoring dashboards delete "$D" --quiet; done
for A in $(gcloud alpha monitoring policies list --filter="displayName~MercaRed" --format="value(name)"); do
  gcloud alpha monitoring policies delete "$A" --quiet; done
gcloud logging metrics delete archivos_procesados --quiet
gcloud logging metrics delete archivos_rechazados --quiet
gcloud compute firewall-rules delete fw-permitir-interno fw-denegar-ingreso-externo --quiet
gcloud compute networks subnets delete "$SUBRED" --region="$REGION" --quiet
gcloud compute networks delete "$VPC" --quiet
for SA in "$SA_WEBAPP" "$SA_PROCESADOR" "$SA_EVENTARC"; do
  gcloud iam service-accounts delete "$SA" --quiet; done
echo "=== Recursos eliminados ==="
