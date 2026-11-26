#!/bin/bash
# =============================================================
# MercaRed - Variables comunes (las usan todos los scripts)
# Si despliegas en otro proyecto, solo cambia estos valores.
# =============================================================
export PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export REGION="${REGION:-us-central1}"
# Sufijo para que los nombres de bucket sean unicos en el mundo
export SUFIJO="${SUFIJO:-$(echo "$PROJECT_ID" | sed 's/^project-//' | cut -c1-8)}"
export BUCKET_ENTRADA="mercared-entrada-${SUFIJO}"
export BUCKET_RECHAZADOS="mercared-rechazados-${SUFIJO}"
export VPC="mercared-vpc"
export SUBRED="subred-app"
export RANGO_SUBRED="10.10.1.0/24"
export CORREO_ALERTAS="${CORREO_ALERTAS:-brendalescano4002@gmail.com}"

export SA_WEBAPP="sa-webapp@${PROJECT_ID}.iam.gserviceaccount.com"
export SA_PROCESADOR="sa-procesador@${PROJECT_ID}.iam.gserviceaccount.com"
export SA_EVENTARC="sa-eventarc@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID" > /dev/null 2>&1
gcloud config set run/region "$REGION" > /dev/null 2>&1
echo "Proyecto: $PROJECT_ID ($PROJECT_NUMBER) | Region: $REGION | Buckets: $BUCKET_ENTRADA, $BUCKET_RECHAZADOS"
