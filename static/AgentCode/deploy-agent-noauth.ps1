# =============================================================================
# Deploy the Good Neighbor Strands agent to Amazon Bedrock AgentCore Runtime
# WITHOUT Cognito (no bootstrap-stack). Inbound auth is AWS IAM (SigV4): callers
# invoke the runtime with their AWS credentials, so no user pool is needed.
#
# Prerequisites (already set up in this project):
#   * bedrock-agentcore-starter-toolkit installed (agentcore CLI)
#   * Execution role: good-neighbor-agent-exec-role
#   * Bedrock model access for Claude in the target region
#
# Usage (from static/AgentCode):
#   powershell -ExecutionPolicy Bypass -File .\deploy-agent-noauth.ps1
#
# MIT License - Copyright (c) 2026 Dineshraj Dhanapathy@DD
# =============================================================================

$ErrorActionPreference = "Stop"

# --- Settings ----------------------------------------------------------------
$AgentName   = "good_neighbor_agent"
$EntryPoint  = "agent.py"
$Requirements = "requirements.txt"
$Region      = "us-east-1"
$RoleArn     = "arn:aws:iam::466742534146:role/good-neighbor-agent-exec-role"

# agentcore CLI location (installed by pip --user; not always on PATH).
$AgentCore = Join-Path $env:APPDATA "Python\Python313\Scripts\agentcore.exe"
if (-not (Test-Path $AgentCore)) {
    # Fall back to PATH if the user installed it globally.
    $AgentCore = "agentcore"
}

# Silence the deprecated-toolkit banner, and force UTF-8 so the CLI's Rich
# output doesn't crash on Windows cp1252 (it prints Unicode check marks etc.).
$env:AGENTCORE_SUPPRESS_RECOMMENDATION = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Push-Location $PSScriptRoot
try {
    Write-Host "=== Configuring AgentCore runtime (IAM / SigV4 inbound auth) ===" -ForegroundColor Cyan
    # No --authorizer-config => the runtime defaults to AWS IAM inbound auth
    # (no Cognito). Container deployment builds the ARM64 image remotely with
    # CodeBuild — no local Docker or zip utility required.
    & $AgentCore configure `
        --entrypoint $EntryPoint `
        --name $AgentName `
        --region $Region `
        --execution-role $RoleArn `
        --requirements-file $Requirements `
        --disable-otel `
        --disable-memory `
        --non-interactive

    Write-Host "=== Deploying AgentCore runtime (CodeBuild — several minutes) ===" -ForegroundColor Cyan
    # --auto-update-on-conflict updates the runtime if it already exists.
    # NOTE: let this run to completion; interrupting it leaves the local config
    # out of sync with the deployed runtime.
    & $AgentCore deploy --auto-update-on-conflict

    Write-Host "=== Runtime status ===" -ForegroundColor Cyan
    & $AgentCore status
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Done. Verify by invoking the runtime directly (avoids CLI arg-quoting issues):" -ForegroundColor Green
Write-Host '  ''{"prompt": "hello"}'' | Out-File -Encoding ascii payload.json'
Write-Host '  aws bedrock-agentcore invoke-agent-runtime --region us-east-1 \'
Write-Host '    --agent-runtime-arn <RUNTIME_ARN> --payload fileb://payload.json \'
Write-Host '    --content-type application/json --accept application/json out.json'
Write-Host ""
Write-Host "NOTE: Bedrock model access requires a valid payment instrument on the AWS" -ForegroundColor Yellow
Write-Host "account. If the response says INVALID_PAYMENT_INSTRUMENT, add a payment"    -ForegroundColor Yellow
Write-Host "method in the Billing console and enable the Claude model in Bedrock."       -ForegroundColor Yellow
