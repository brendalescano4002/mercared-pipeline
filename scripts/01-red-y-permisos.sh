#!/bin/bash
# =============================================================
# MercaRed - Script 01: APIs, red (VPC), firewall y cuentas de servicio
# Uso (desde la carpeta del repositorio): bash scripts/01-red-y-permisos.sh
# =============================================================
source "$(dirname "$0")/00-variables.sh"

echo ">> 1. Activando APIs"
gcloud services enable compute.googleapis.com run.googleapis.com eventarc.googleapis.com \
  pubsub.googleapis.com storage.googleapis.com firestore.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com logging.googleapis.com \
  monitoring.googleapis.com iam.googleapis.com

echo ">> 2. Red privada (VPC) y subred"
gcloud compute networks create "$VPC" --subnet-mode=custom
gcloud compute networks subnets create "$SUBRED" --network="$VPC" --region="$REGION" \
  --range="$RANGO_SUBRED" --enable-private-ip-google-access

echo ">> 3. Reglas de firewall"
gcloud compute firewall-rules create fw-permitir-interno --network="$VPC" \
  --direction=INGRESS --action=ALLOW --rules=tcp,udp,icmp \
  --source-ranges=10.10.0.0/16 --priority=1000
gcloud compute firewall-rules create fw-denegar-ingreso-externo --network="$VPC" \
  --direction=INGRESS --action=DENY --rules=all \
  --source-ranges=0.0.0.0/0 --priority=65000

echo ">> 4. Cuentas de servicio (una por componente)"
gcloud iam service-accounts create sa-webapp --display-name="MercaRed - Web app"
gcloud iam service-accounts create sa-procesador --display-name="MercaRed - Procesador de archivos"
gcloud iam service-accounts create sa-eventarc --display-name="MercaRed - Disparador Eventarc"

echo ">> 5. Agentes de servicio de Google (se crean la primera vez)"
gcloud beta services identity create --service=eventarc.googleapis.com --project="$PROJECT_ID"
gcloud beta services identity create --service=pubsub.googleapis.com --project="$PROJECT_ID"
GCS_SA="$(gcloud storage service-agent --project="$PROJECT_ID")"

echo ">> 6. Roles a nivel de proyecto (principio de menor privilegio)"
asignar() { gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$1" \
  --role="$2" --condition=None --quiet > /dev/null && echo "   OK $2 -> $1"; }
asignar "$SA_PROCESADOR" roles/datastore.user
asignar "$SA_WEBAPP" roles/datastore.viewer
asignar "$SA_EVENTARC" roles/eventarc.eventReceiver
asignar "$GCS_SA" roles/pubsub.publisher
asignar "service-${PROJECT_NUMBER}@gcp-sa-eventarc.iam.gserviceaccount.com" roles/eventarc.serviceAgent
asignar "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" roles/run.builder

echo "=== Script 01 terminado ==="
