# Deploy to Cloud Run. The project owner runs this; Claude never does.
# Needs: gcloud logged in, a project with Cloud Run, Cloud Build and Secret Manager enabled,
# and three secrets: meta-api-key (the Meta key), workflow-secret (any long random string) and
# private-api-key (the bearer token of the Modal endpoint, see scripts/private_modal.py).
param([Parameter(Mandatory)][string]$Project, [string]$Region = "us-central1", [string]$Service = "role-assistants",
       [string]$PrivateUrl = "https://hoachauphuoc--muse-glimmer-private-serve.us-east.modal.run/v1")
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
# min = max = 1: the demo database lives in memory, so every request must reach the same instance.
# Session affinity keeps a visitor on it. Lower min-instances to 0 after 9/11 to stop paying for idle.
gcloud run deploy $Service --project $Project --region $Region --source . `
    --min-instances 1 --max-instances 1 --memory 1Gi --cpu 1 --session-affinity `
    --allow-unauthenticated --timeout 120 `
    --set-secrets "META_API_KEY=meta-api-key:latest,WORKFLOW_SECRET=workflow-secret:latest,/secrets/private-api-key=private-api-key:latest" `
    --set-env-vars "DAILY_CEILING_USD=10,PRIVATE_PROVIDER=modal,PRIVATE_MODEL=meta-models/Muse-Glimmer-30B,PRIVATE_BASE_URL=$PrivateUrl,PRIVATE_API_KEY_FILE=/secrets/private-api-key"
