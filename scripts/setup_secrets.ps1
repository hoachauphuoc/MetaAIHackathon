# Creates the three Secret Manager secrets that deploy.ps1 mounts. The project owner runs this once.
# Key values are read from their files and written to a temp file without a trailing newline (the
# app does not strip env-var keys); nothing is printed.
param([Parameter(Mandatory)][string]$Project,
      [string]$MetaKeyFile = "$HOME\.bjt\MetaAIHackathon.txt",
      [string]$PrivateKeyFile = "$HOME\.bjt\GlimmerPrivate.txt")

function New-Secret($name, $value) {
    $tmp = New-TemporaryFile
    try {
        [IO.File]::WriteAllText($tmp.FullName, $value)
        gcloud secrets create $name --project $Project --data-file $tmp.FullName
    } finally { Remove-Item $tmp -Force }
}

New-Secret "meta-api-key" ((Get-Content $MetaKeyFile -Raw).Trim())
New-Secret "private-api-key" ((Get-Content $PrivateKeyFile -Raw).Trim())
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
New-Secret "workflow-secret" ([Convert]::ToBase64String($bytes))

# Cloud Run runs as the default compute service account; it must be allowed to read the secrets.
$number = gcloud projects describe $Project --format "value(projectNumber)"
foreach ($name in "meta-api-key", "private-api-key", "workflow-secret") {
    gcloud secrets add-iam-policy-binding $name --project $Project `
        --member "serviceAccount:$number-compute@developer.gserviceaccount.com" `
        --role roles/secretmanager.secretAccessor | Out-Null
}
