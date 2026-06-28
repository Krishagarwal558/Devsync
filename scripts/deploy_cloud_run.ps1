param(
    [string]$ProjectId,
    [string]$Region = "asia-south1",
    [string]$ServiceName = "devsync-backend",
    [string]$ImageName = "devsync-backend",
    [string]$EnvVarsFile = "server\.env.beta.yaml"
)

$ErrorActionPreference = "Stop"

if (-not $ProjectId) {
    throw "ProjectId is required."
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud CLI is not installed or not on PATH."
}

if (-not (Test-Path $EnvVarsFile)) {
    throw "Cloud Run env YAML not found: $EnvVarsFile"
}

$image = "gcr.io/$ProjectId/$ImageName"

gcloud config set project $ProjectId
gcloud builds submit --tag $image --file Dockerfile.backend .
gcloud run deploy $ServiceName `
    --image $image `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --port 8000 `
    --env-vars-file $EnvVarsFile
