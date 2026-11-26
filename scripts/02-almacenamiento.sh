#!/bin/bash
# =============================================================
# MercaRed - Script 02: Firestore, buckets, ciclo de vida y permisos por bucket
# Uso: bash scripts/02-almacenamiento.sh
# =============================================================
source "$(dirname "$0")/00-variables.sh"

echo ">> 1. Base de datos Firestore (modo nativo)"
gcloud firestore databases create --location="$REGION" --type=firestore-native

echo ">> 2. Buckets privados (acceso uniforme y sin acceso publico)"
for B in "$BUCKET_ENTRADA" "$BUCKET_RECHAZADOS"; do
  gcloud storage buckets create "gs://$B" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
done

echo ">> 3. Politicas de ciclo de vida"
gcloud storage buckets update "gs://$BUCKET_ENTRADA" --lifecycle-file=config/lifecycle-entrada.json
gcloud storage buckets update "gs://$BUCKET_RECHAZADOS" --lifecycle-file=config/lifecycle-rechazados.json

echo ">> 4. Permisos por bucket"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_ENTRADA" \
  --member="serviceAccount:$SA_WEBAPP" --role=roles/storage.objectCreator > /dev/null && echo "   OK webapp -> entrada (subir)"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_ENTRADA" \
  --member="serviceAccount:$SA_PROCESADOR" --role=roles/storage.objectAdmin > /dev/null && echo "   OK procesador -> entrada (leer/borrar)"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_RECHAZADOS" \
  --member="serviceAccount:$SA_PROCESADOR" --role=roles/storage.objectCreator > /dev/null && echo "   OK procesador -> rechazados (subir)"

echo "=== Script 02 terminado ==="
