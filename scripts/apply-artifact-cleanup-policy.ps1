# Apply Artifact Registry cleanup policies (automatic ongoing pruning).
# Policies take effect within ~24h; use prune-gae-images.ps1 for immediate cleanup.
#
# Usage:
#   .\scripts\apply-artifact-cleanup-policy.ps1           # dry run
#   .\scripts\apply-artifact-cleanup-policy.ps1 -Apply

param(
    [string]$Project = "cloudtasks-app-473120",
    [string]$Location = "us-central1",
    [string]$Repository = "gae-standard",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$policyFile = Join-Path $PSScriptRoot "..\config\artifact-registry-cleanup-policy.json"
$policyFile = (Resolve-Path $policyFile).Path

$args = @(
    "artifacts", "repositories", "set-cleanup-policies", $Repository,
    "--location=$Location",
    "--project=$Project",
    "--policy=$policyFile"
)
if (-not $Apply) {
    $args += "--dry-run"
}

Write-Host "Policy file: $policyFile"
Write-Host "gcloud $($args -join ' ')"
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& gcloud.cmd @args 2>$null
$ErrorActionPreference = $prevEap

if (-not $Apply) {
    Write-Host ""
    Write-Host "Dry run complete. Re-run with -Apply to enable automatic cleanup."
}
