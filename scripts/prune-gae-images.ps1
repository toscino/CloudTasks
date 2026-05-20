# One-time prune of old App Engine images in Artifact Registry (gae-standard).
# Keeps the N most recent app/default images; deletes older digests.
#
# Usage:
#   .\scripts\prune-gae-images.ps1              # dry run (default)
#   .\scripts\prune-gae-images.ps1 -Keep 5 -Apply
#
param(
    [string]$Project = "cloudtasks-app-473120",
    [string]$Location = "us-central1",
    [string]$Repository = "gae-standard",
    [string]$Package = "app/default",
    [int]$Keep = 5,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$imagePath = "$Location-docker.pkg.dev/$Project/$Repository/$Package"

Write-Host "Repository: $Repository ($Location)"
Write-Host "Package:    $Package"
Write-Host "Keeping:    $Keep newest image(s)"
Write-Host ""

# Use gcloud.cmd and tolerate stderr progress lines (gcloud.ps1 treats them as errors).
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$json = & gcloud.cmd artifacts docker images list $imagePath `
    --format=json `
    --sort-by=~UPDATE_TIME `
    2>$null | Out-String
$ErrorActionPreference = $prevEap
if (-not $json) {
    Write-Error "No images found (check gcloud auth and project)."
}
$images = $json | ConvertFrom-Json
if ($images -isnot [array]) {
    $images = @($images)
}

Write-Host "Found $($images.Count) version(s)."
if ($images.Count -le $Keep) {
    Write-Host "Nothing to prune."
    exit 0
}

$toKeep = $images | Select-Object -First $Keep
$toDelete = $images | Select-Object -Skip $Keep

Write-Host ""
Write-Host "=== KEEP ==="
foreach ($img in $toKeep) {
    Write-Host "  $($img.update_time)  $($img.version)"
}

Write-Host ""
Write-Host "=== DELETE ($($toDelete.Count)) ==="
foreach ($img in $toDelete) {
    Write-Host "  $($img.update_time)  $($img.version)"
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry run only. Re-run with -Apply to delete the images above."
    exit 0
}

Write-Host ""
$confirm = Read-Host "Type 'yes' to delete $($toDelete.Count) image version(s)"
if ($confirm -ne "yes") {
    Write-Host "Aborted."
    exit 1
}

foreach ($img in $toDelete) {
    $ref = "$imagePath@$($img.version)"
    Write-Host "Deleting $ref ..."
    & gcloud.cmd artifacts docker images delete $ref --quiet --delete-tags 2>$null
}

Write-Host "Done. Repository size may take a few minutes to update in the console."
