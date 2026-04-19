#Requires -Version 7.0
<#
.SYNOPSIS
    Phase 3 bootstrap: mise-managed runtimes and developer CLI tools.

.DESCRIPTION
    Run AFTER phase 1. Installs language runtimes and CLI tools globally
    via mise. Idempotent: re-running is safe.

    See ../docs/AGENT_WINDOWS_SETUP.md for rationale.

.PARAMETER DryRun
    Print what would happen without making changes.

.EXAMPLE
    PS> .\bootstrap-phase3.ps1
    PS> .\bootstrap-phase3.ps1 -DryRun
#>

[CmdletBinding()]
param(
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Info    { param($m) Write-Host "[INFO]    $m" -ForegroundColor Blue }
function Write-Step    { param($m) Write-Host "[STEP]    $m" -ForegroundColor Cyan }
function Write-Ok      { param($m) Write-Host "[OK]      $m" -ForegroundColor Green }
function Write-WarnMsg { param($m) Write-Host "[WARN]    $m" -ForegroundColor Yellow }
function Write-Dry     { param($m) Write-Host "[DRY-RUN] $m" -ForegroundColor DarkGray }

function Invoke-Step {
  param([string]$Label, [scriptblock]$Body)
  Write-Step $Label
  if ($DryRun) { Write-Dry $Label; return }
  & $Body
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

Write-Info "lsimons-dotfiles Windows bootstrap-phase3"
if ($DryRun) { Write-Dry "dry-run mode -- no changes will be made" }

if (-not (Get-Command mise -ErrorAction SilentlyContinue)) {
  throw "mise not found -- run bootstrap-phase1.ps1 first"
}

# ---------------------------------------------------------------------------
# mise tools
# ---------------------------------------------------------------------------

# Runtimes and CLI tools managed by mise.
# Tools that fail (e.g. not yet in the mise registry on Windows/ARM64) emit
# a warning and are skipped so the rest of the installs still proceed.
$tools = @(
  'fnox@latest',
  'node@lts',
  'python@latest',
  'go@latest',
  'rust@latest',
  'ruby@latest',
  'java@21',
  'uv@latest',
  'terraform@latest',
  'awscli@latest',
  'azure-cli@latest'
)

foreach ($tool in $tools) {
  Invoke-Step "mise use -g $tool" {
    mise use --global $tool
    if ($LASTEXITCODE -ne 0) {
      Write-WarnMsg "$tool: mise exited $LASTEXITCODE -- skipping"
    } else {
      Write-Ok "$tool installed"
    }
  }
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

Write-Host ""
Write-Ok "Phase 3 complete."
Write-Info ""
Write-Info "Verify installed tools with: mise ls"
