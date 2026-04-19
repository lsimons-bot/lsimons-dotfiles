#Requires -Version 7.0
<#
.SYNOPSIS
    Phase 2 bootstrap: account-coupled setup for the Windows 11 ARM64 AI-agent VM.

.DESCRIPTION
    Run AFTER phase 1 AND after signing into 1Password, GitHub, and Claude.

    Does the things that need credentials:
      - Pull bot SSH public key from 1Password
      - Configure git identity + commit signing via the 1Password SSH agent
      - Optionally clone a list of repos

    Idempotent.

    See ../docs/AGENT_WINDOWS_SETUP.md for rationale.

.PARAMETER DryRun
    Print what would happen without making changes.

.PARAMETER SshKeyItem
    1Password item reference for the bot SSH public key. The item must have
    a 'public key' field. Defaults to the bot's convention.

.PARAMETER GitName
    Overrides the git user.name. Default: "Leo-Bot Simons".

.PARAMETER GitEmail
    Overrides the git user.email. Default: "bot@leosimons.com".

.PARAMETER Repos
    List of GitHub repos (owner/name) to clone into ~/git. Optional.

.EXAMPLE
    PS> .\bootstrap-phase2.ps1
    PS> .\bootstrap-phase2.ps1 -Repos @('lsimons/lsimons-dotfiles','lsimons/lsimons-arch')
#>

[CmdletBinding()]
param(
  [switch]$DryRun,
  [string]$SshKeyItem = 'op://AI/lsimons-bot ssh key/public key',
  [string]$GitName    = 'Leo-Bot Simons',
  [string]$GitEmail   = 'bot@leosimons.com',
  [string]$GitDir     = 'C:\git',
  [string[]]$Repos    = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Info    { param($m) Write-Host "[INFO]    $m" -ForegroundColor Blue }
function Write-Step    { param($m) Write-Host "[STEP]    $m" -ForegroundColor Cyan }
function Write-Ok      { param($m) Write-Host "[OK]      $m" -ForegroundColor Green }
function Write-WarnMsg { param($m) Write-Host "[WARN]    $m" -ForegroundColor Yellow }
function Write-ErrMsg  { param($m) Write-Host "[ERR]     $m" -ForegroundColor Red }
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

Write-Info "lsimons-dotfiles Windows bootstrap-phase2"
if ($DryRun) { Write-Dry "dry-run mode --no changes will be made" }

foreach ($cmd in 'op','git','ssh') {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $cmd --run bootstrap-phase1.ps1 first"
  }
}

# Verify op session is active
if (-not $DryRun) {
  try {
    $null = op whoami 2>$null
    if ($LASTEXITCODE -ne 0) { throw }
  } catch {
    throw "1Password CLI is not signed in. Run 'op signin' (or sign into the desktop app with CLI integration enabled) and retry."
  }
  Write-Ok "op signed in"
}

# ---------------------------------------------------------------------------
# SSH public key from 1Password
# ---------------------------------------------------------------------------

$sshDir = Join-Path $env:USERPROFILE '.ssh'
$pubkeyPath = Join-Path $sshDir 'id_lsimons_bot_ed25519.pub'

Invoke-Step "Write bot SSH public key from 1Password to $pubkeyPath" {
  if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
  }
  $pubkey = op read $SshKeyItem 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $pubkey) {
    throw "Could not read $SshKeyItem from 1Password. Adjust -SshKeyItem or fix the vault item."
  }
  Set-Content -Path $pubkeyPath -Value $pubkey -Encoding ascii -NoNewline
  Write-Ok "wrote $pubkeyPath"
}

# ---------------------------------------------------------------------------
# Git config
# ---------------------------------------------------------------------------

function Find-OpSshSign {
  $candidates = @(
    "$env:LOCALAPPDATA\1Password\app\8\op-ssh-sign.exe",
    "$env:ProgramFiles\1Password\app\8\op-ssh-sign.exe"
  )
  foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
  # Fallback: look anywhere under 1Password install
  Get-ChildItem -Path $env:LOCALAPPDATA,$env:ProgramFiles -Filter 'op-ssh-sign.exe' `
                -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
}

Invoke-Step "Configure git identity and SSH commit signing" {
  $opSshSign = Find-OpSshSign
  if (-not $opSshSign) {
    throw "op-ssh-sign.exe not found. Install 1Password desktop and enable 'Use the SSH agent' in Developer settings."
  }
  Write-Info "op-ssh-sign: $opSshSign"

  git config --global user.name       $GitName
  git config --global user.email      $GitEmail
  git config --global user.signingkey $pubkeyPath
  git config --global gpg.format      ssh
  git config --global gpg.ssh.program $opSshSign
  git config --global commit.gpgsign  true
  git config --global tag.gpgsign     true
  git config --global init.defaultBranch main
  git config --global push.default    simple
  git config --global push.followTags true
  git config --global core.autocrlf   input
  git config --global pull.rebase     false

  Write-Ok "git identity: $GitName <$GitEmail>"
  Write-Ok "git will sign commits via 1Password SSH agent"
}

# ---------------------------------------------------------------------------
# Optional repo clones
# ---------------------------------------------------------------------------

if ($Repos.Count -gt 0) {
  Invoke-Step "Clone repos into $GitDir" {
    if (-not (Test-Path $GitDir)) { New-Item -ItemType Directory -Force -Path $GitDir | Out-Null }
    Push-Location $GitDir
    try {
      foreach ($repo in $Repos) {
        $name = ($repo -split '/')[-1]
        if (Test-Path (Join-Path $GitDir $name)) {
          Write-Ok "already cloned: $name"
          continue
        }
        Write-Info "cloning $repo"
        gh repo clone $repo
        if ($LASTEXITCODE -ne 0) { Write-WarnMsg "gh repo clone failed for $repo" }
      }
    } finally {
      Pop-Location
    }
  }
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

Write-Host ""
Write-Ok "Phase 2 complete."
Write-Info ""
Write-Info "Verify commit signing with:"
Write-Info "  cd <a repo>"
Write-Info "  git commit --allow-empty -m 'test: signing'"
Write-Info "  git log --show-signature -1"
Write-Info ""
Write-Info "You can now switch Simplewall to alert mode."
