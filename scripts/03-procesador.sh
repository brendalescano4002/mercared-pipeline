#!/bin/bash
# =============================================================
# MercaRed - Script 03: Despliegue del procesador y disparador Eventarc
# Uso: bash scripts/03-procesador.sh
# =============================================================
source "$(dirname "$0")/00-variables.sh"

echo ">> 1. Desplegando el procesador en Cloud Run (privado)"
gcloud run deploy procesador --source=procesador --region="$REGION" \
  --service-account="$SA_PROCESADOR" --no-allow-unauthenticated \
  --set-env-vars="BUCKET_RECHAZADOS=$BUCKET_RECHAZADOS" \
  --network="$VPC" --subnet="$SUBRED" --vpc-egress=private-ranges-only \
  --concurrency=1 --max-instances=10 --memory=512Mi --quiet

echo ">> 2. Permitir que Eventarc invoque al procesador"
gcloud run services add-iam-policy-binding procesador --region="$REGION" \
  --member="serviceAccount:$SA_EVENTARC" --role=roles/run.invoker --quiet > /dev/null && echo "   OK run.invoker"

echo ">> 3. Disparador: archivo nuevo en el bucket de entrada -> procesador"
gcloud eventarc triggers create trigger-nuevo-archivo --location="$REGION" \
  --destination-run-service=procesador --destination-run-region="$REGION" \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=$BUCKET_ENTRADA" \
  --service-account="$SA_EVENTARC"

echo "=== Script 03 terminado (el disparador tarda hasta 2 minutos en activarse) ==="
