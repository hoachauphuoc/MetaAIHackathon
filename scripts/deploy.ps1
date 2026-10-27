# Deploy to Cloud Run. The project owner runs this; Claude never does.
# Needs: gcloud logged in, a project with Cloud Run, Cloud Build and Secret Manager enabled,
# and two secrets: meta-api-key (the Meta key) and workflow-secret (any long random string).
param([Parameter(Mandatory)][string]$Project, [string]$Region = "us-central1", [string]$Service = "role-assistants")
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
# min = max = 1: the demo database lives in memory, so every request must reach the same instance.
# Session affinity keeps a visitor on it. Lower min-instances to 0 after 9/11 to stop paying for idle.
gcloud run deploy $Service --project $Project --region $Region --source . `
    --min-instances 1 --max-instances 1 --memory 1Gi --cpu 1 --session-affinity `
    --allow-unauthenticated --timeout 120 `
    --set-secrets "META_API_KEY=meta-api-key:latest,WORKFLOW_SECRET=workflow-secret:latest" `
    --set-env-vars "DAILY_CEILING_USD=10"
