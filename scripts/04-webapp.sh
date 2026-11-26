#!/bin/bash
# =============================================================
# MercaRed - Script 04: Despliegue de la pagina web (publica)
# Uso: bash scripts/04-webapp.sh
# =============================================================
source "$(dirname "$0")/00-variables.sh"

gcloud run deploy webapp --source=webapp --region="$REGION" \
  --service-account="$SA_WEBAPP" --allow-unauthenticated \
  --set-env-vars="BUCKET_ENTRADA=$BUCKET_ENTRADA" \
  --network="$VPC" --subnet="$SUBRED" --vpc-egress=private-ranges-only \
  --max-instances=3 --memory=512Mi --quiet

echo "=== Script 04 terminado ==="
gcloud run services describe webapp --region="$REGION" --format="value(status.url)"
