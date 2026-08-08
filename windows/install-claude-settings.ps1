#Requires -Version 7.0
<#
.SYNOPSIS
    Install Claude Code settings from the claude/ dotfiles topic.

.DESCRIPTION
    Copies the shared agent instructions and skills, then builds Claude Code
    settings.json from the claude/ topic with dynamic commit attribution
    derived from the configured git user email. Idempotent.

.PARAMETER DryRun
    Print what would happen without making changes.
#>

[CmdletBinding()]
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$dotfilesRoot = Split-Path -Parent $scriptDir
$topicDir     = Join-Path $dotfilesRoot 'claude'
$agentsDir    = Join-Path $dotfilesRoot 'agents'
$claudeDir    = Join-Path $env:USERPROFILE '.claude'

# Skills live in the lsimons-skills checkout next to this repository, not in
# agents/. See agents/README.md.
$skillsDir    = Join-Path (Split-Path -Parent $dotfilesRoot) 'lsimons-skills' 'skills'

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

function Copy-IfChanged {
  param([string]$Source, [string]$Dest)
  $destDir = Split-Path -Parent $Dest
  if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null
  }
  if ((Test-Path $Dest) -and
      ((Get-FileHash $Source).Hash -eq (Get-FileHash $Dest).Hash)) {
    Write-Ok "unchanged: $Dest"
    return
  }
  Copy-Item -Path $Source -Destination $Dest -Force
  Write-Ok "wrote $Dest"
}

Write-Info "Installing Claude Code settings from claude/ topic"
if ($DryRun) { Write-Dry "dry-run mode -- no changes will be made" }

Invoke-Step "Ensure $claudeDir exists" {
  if (-not (Test-Path $claudeDir)) {
    New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null
    Write-Ok "created $claudeDir"
  } else {
    Write-Ok "$claudeDir exists"
  }
}

Invoke-Step "Install CLAUDE.md" {
  Copy-IfChanged `
    -Source (Join-Path $agentsDir 'AGENTS.md') `
    -Dest   (Join-Path $claudeDir 'CLAUDE.md')
}

Invoke-Step "Install statusline-command.ps1" {
  Copy-IfChanged `
    -Source (Join-Path $topicDir 'statusline-command.ps1') `
    -Dest   (Join-Path $claudeDir 'statusline-command.ps1')
}

Invoke-Step "Install skills/" {
  $src  = $skillsDir
  $dest = Join-Path $claudeDir 'skills'
  if (-not (Test-Path $src)) {
    Write-WarnMsg "no skills collection at $src -- clone lsimons-skills next to this repository"
    return
  }
  if (-not (Test-Path $dest)) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
  }
  Get-ChildItem -Path $src -Recurse -File | ForEach-Object {
    $rel      = $_.FullName.Substring($src.Length).TrimStart('\','/')
    $destFile = Join-Path $dest $rel
    Copy-IfChanged -Source $_.FullName -Dest $destFile
  }
}

Invoke-Step "Install themes/" {
  # Claude Code picks up custom themes from ~/.claude/themes/*.json; the
  # settings.json below selects one via "theme": "custom:lsd-warm-light".
  $src  = Join-Path $topicDir 'themes'
  $dest = Join-Path $claudeDir 'themes'
  if (-not (Test-Path $dest)) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
  }
  Get-ChildItem -Path $src -Recurse -File | ForEach-Object {
    $rel      = $_.FullName.Substring($src.Length).TrimStart('\','/')
    $destFile = Join-Path $dest $rel
    Copy-IfChanged -Source $_.FullName -Dest $destFile
  }
}

Invoke-Step "Write settings.json" {
  $basePath     = Join-Path $topicDir 'settings.json.base'
  $settingsPath = Join-Path $claudeDir 'settings.json'

  $settings = Get-Content $basePath -Raw | ConvertFrom-Json -AsHashtable

  # Replace the .sh statusLine with the PowerShell equivalent
  $psScript = Join-Path $claudeDir 'statusline-command.ps1'
  $settings['statusLine'] = [ordered]@{
    type    = 'command'
    command = "pwsh -NoProfile -NonInteractive -File `"$psScript`""
  }

  # Attribution based on git email (mirrors claude/install.py logic)
  $email = git config --get user.email 2>$null
  if ($email) {
    Write-Info "git email: $email"
    $attr = if ($email -eq 'bot@leosimons.com') {
      'Co-Authored-By: Leo Simons <mail@leosimons.com>'
    } else {
      'Co-Authored-By: lsimons-bot <bot@leosimons.com>'
    }
    $settings['attribution'] = [ordered]@{ commit = $attr; pr = $attr }
  } else {
    Write-WarnMsg "no git email configured -- skipping attribution"
  }

  $settings | ConvertTo-Json -Depth 10 | Set-Content -Path $settingsPath -Encoding utf8
  Write-Ok "wrote $settingsPath"
}

Write-Host ""
Write-Ok "Claude settings installed."
