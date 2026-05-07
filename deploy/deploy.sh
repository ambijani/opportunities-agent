#!/bin/bash
# Deploy to Google Cloud Run.
# Prerequisites: gcloud CLI installed and authenticated, Docker running.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
SERVICE="opportunities-agent"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE"

echo "==> Building and pushing image..."
gcloud builds submit --tag "$IMAGE" .

echo "==> Deploying to Cloud Run..."
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --min-instances 1 \
  --max-instances 1 \
  --no-cpu-throttling \
  --memory 1Gi \
  --timeout 3600 \
  --no-allow-unauthenticated \
  --set-env-vars "$(paste -sd, deploy/env-vars.txt)" \
  --update-secrets "DISCORD_BOT_TOKEN=DISCORD_BOT_TOKEN:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest"

echo ""
echo "Done. Service URL:"
gcloud run services describe "$SERVICE" --region "$REGION" --format "value(status.url)"
