#Requires -Version 5.1
<#
.SYNOPSIS
    Phase 1 bootstrap for the Windows 11 ARM64 AI-agent VM.

.DESCRIPTION
    Unattended setup. No sign-ins required --account-coupled work lives in
    bootstrap-phase2.ps1. Runs as the regular user; winget may prompt for
    UAC when a package needs machine-wide install.

    Idempotent: re-running is safe. Each step checks before acting.

    See ../docs/AGENT_WINDOWS_SETUP.md for rationale.

.PARAMETER DryRun
    Print what would happen without making changes.

.PARAMETER SkipWinget
    Skip the winget configure step (useful when iterating on Scoop only).

.PARAMETER SkipScoop
    Skip the Scoop install + import step.

.PARAMETER SkipClaude
    Skip the Claude Code install step.

.EXAMPLE
    PS> .\bootstrap-phase1.ps1
    PS> .\bootstrap-phase1.ps1 -DryRun
#>

[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$SkipWinget,
  [switch]$SkipScoop,
  [switch]$SkipClaude,
  [switch]$AllowElevated,
  [string]$GitDir = 'C:\git'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dotfilesRoot = Split-Path -Parent $scriptDir

function Write-Info    { param($m) Write-Host "[INFO]    $m" -ForegroundColor Blue }
function Write-Step    { param($m) Write-Host "[STEP]    $m" -ForegroundColor Cyan }
function Write-Ok      { param($m) Write-Host "[OK]      $m" -ForegroundColor Green }
function Write-WarnMsg { param($m) Write-Host "[WARN]    $m" -ForegroundColor Yellow }
function Write-ErrMsg  { param($m) Write-Host "[ERR]     $m" -ForegroundColor Red }
function Write-Dry     { param($m) Write-Host "[DRY-RUN] $m" -ForegroundColor DarkGray }

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-Step {
  param([string]$Label, [scriptblock]$Body)
  Write-Step $Label
  if ($DryRun) { Write-Dry  $Label; return }
  & $Body
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

Write-Info "lsimons-dotfiles Windows bootstrap-phase1"
Write-Info "Dotfiles root: $dotfilesRoot"
if ($DryRun) { Write-Dry "dry-run mode --no changes will be made" }

$isElevated = Test-Admin
if ($isElevated) {
  Write-WarnMsg "This PowerShell session is elevated (token has Administrators group active)."
  Write-WarnMsg "Scoop refuses to install from an elevated session; winget will self-elevate anyway."
  if (-not $AllowElevated -and -not $DryRun) {
    Write-ErrMsg ""
    Write-ErrMsg "Refusing to continue elevated. Two options:"
    Write-ErrMsg "  (a) Open a non-admin PowerShell:"
    Write-ErrMsg "      Start menu -> type PowerShell -> left-click (NOT Run as admin)"
    Write-ErrMsg "      Verify elevation is off with:"
    Write-ErrMsg '        $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())'
    Write-ErrMsg '        $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)    # must print False'
    Write-ErrMsg "  (b) Re-run with -AllowElevated to continue without Scoop:"
    Write-ErrMsg "      .\bootstrap-phase1.ps1 -AllowElevated"
    throw "Elevated session detected. See guidance above."
  }
  if ($AllowElevated) {
    Write-WarnMsg "-AllowElevated set: will skip Scoop install/import, continue with the rest."
    $SkipScoop = $true
  }
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  throw "winget not found. Install 'App Installer' from the Microsoft Store and retry."
}

# UAC sanity check: some Windows 11 ARM ISOs ship with EnableLUA=0 baked in.
# When UAC is off, an admin account cannot spawn a filtered (standard-user)
# token -- every session runs elevated, which breaks Scoop.
$uacPath = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
$enableLua = (Get-ItemProperty -Path $uacPath -Name EnableLUA -ErrorAction SilentlyContinue).EnableLUA
if ($enableLua -eq 0) {
  Write-WarnMsg "UAC is disabled (EnableLUA=0). This is not Windows default."
  Write-WarnMsg "Every session for an admin account runs elevated -- Scoop will refuse to install."
  Write-WarnMsg "Re-enable UAC (requires admin + reboot):"
  Write-WarnMsg "  Set-ItemProperty -Path '$uacPath' -Name EnableLUA -Value 1"
  Write-WarnMsg "  Restart-Computer"
  if (-not $AllowElevated -and -not $DryRun) {
    throw "UAC disabled. Re-enable and reboot, or re-run with -AllowElevated."
  }
}

# ---------------------------------------------------------------------------
# User-scope registry tweaks (no admin needed)
# ---------------------------------------------------------------------------

function Set-RegistryValue {
  param($Path, $Name, $Value, $Type = 'DWord')
  if ($DryRun) {
    Write-Dry "set $Path\$Name = $Value ($Type)"
    return
  }
  if (-not (Test-Path $Path)) { New-Item -Path $Path -Force | Out-Null }
  New-ItemProperty -Path $Path -Name $Name -Value $Value -PropertyType $Type -Force | Out-Null
}

Invoke-Step "Apply UI tweaks (dark mode, file extensions, hidden files, accent color)" {
  # Dark mode: apps and system
  $personalize = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
  Set-RegistryValue -Path $personalize -Name 'AppsUseLightTheme'   -Value 0
  Set-RegistryValue -Path $personalize -Name 'SystemUsesLightTheme' -Value 0

  # Explorer: show hidden, show extensions, show full paths in title
  $advanced = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
  Set-RegistryValue -Path $advanced -Name 'Hidden'          -Value 1
  Set-RegistryValue -Path $advanced -Name 'HideFileExt'     -Value 0
  Set-RegistryValue -Path $advanced -Name 'ShowSuperHidden' -Value 0
  Set-RegistryValue -Path $advanced -Name 'LaunchTo'        -Value 1   # Open to: This PC

  # Distinct accent colour --bright green to signal "sandbox VM"
  # Format is ABGR 32-bit.
  $dwm = 'HKCU:\Software\Microsoft\Windows\DWM'
  Set-RegistryValue -Path $dwm -Name 'ColorPrevalence'    -Value 1
  Set-RegistryValue -Path $dwm -Name 'AccentColor'        -Value 0xFF26E676
  Set-RegistryValue -Path $dwm -Name 'ColorizationColor'  -Value 0xC426E676
  Set-RegistryValue -Path $dwm -Name 'EnableWindowColorization' -Value 1

  # Reduce animations (VM performance)
  $visualFx = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects'
  Set-RegistryValue -Path $visualFx -Name 'VisualFXSetting' -Value 2  # Adjust for best performance

  Write-Ok "UI tweaks applied (may require sign-out to fully take effect)"
}

# ---------------------------------------------------------------------------
# winget configure
# ---------------------------------------------------------------------------

if (-not $SkipWinget) {
  Invoke-Step "Enable winget configure (if not already)" {
    # winget configure is an 'experimental' feature that must be opted in
    # once per user. The --enable flag is idempotent.
    winget configure --enable 2>&1 | Out-Null
    # Exit code 0 means newly enabled; non-zero may mean already enabled.
    # Either way, proceed -- the real configure call below will surface
    # any genuine problem.
    Write-Ok "winget configure feature enabled"
  }

  Invoke-Step "winget configure (GUI / MSI packages)" {
    $manifest = Join-Path $scriptDir 'packages.winget.yaml'
    if (-not (Test-Path $manifest)) { throw "Manifest not found: $manifest" }
    winget configure --file $manifest `
                     --accept-configuration-agreements `
                     --disable-interactivity
    if ($LASTEXITCODE -ne 0) {
      throw "winget configure failed with exit code $LASTEXITCODE"
    }
    Write-Ok "winget configure complete"
  }
}

# ---------------------------------------------------------------------------
# Scoop (non-elevated)
# ---------------------------------------------------------------------------

if (-not $SkipScoop) {
  Invoke-Step "Install Scoop (if not present)" {
    if (Get-Command scoop -ErrorAction SilentlyContinue) {
      Write-Ok "scoop already installed"
    } else {
      Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
      Invoke-RestMethod -Uri 'https://get.scoop.sh' | Invoke-Expression
      # Refresh PATH in current session
      $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' +
                  [Environment]::GetEnvironmentVariable('Path', 'Machine')
      Write-Ok "scoop installed"
    }
  }

  Invoke-Step "scoop import scoopfile.json" {
    $manifest = Join-Path $scriptDir 'scoopfile.json'
    if (-not (Test-Path $manifest)) { throw "Manifest not found: $manifest" }

    # Ensure git is on PATH for bucket clones. If winget installed Git,
    # its bin is in Program Files --pick it up.
    $gitBin = 'C:\Program Files\Git\cmd'
    if ((Test-Path $gitBin) -and (-not ($env:Path -split ';' -contains $gitBin))) {
      $env:Path = "$gitBin;$env:Path"
    }

    scoop import $manifest
    if ($LASTEXITCODE -ne 0) {
      Write-WarnMsg "scoop import exited $LASTEXITCODE --continuing (import can partial-fail on already-present apps)"
    }
    Write-Ok "scoop import complete"
  }
}

# ---------------------------------------------------------------------------
# Symlink / copy config files
# ---------------------------------------------------------------------------

function Copy-IfChanged {
  param([string]$Source, [string]$Dest)
  if (-not (Test-Path $Source)) { throw "Source missing: $Source" }
  if ($DryRun) { Write-Dry "copy $Source -> $Dest"; return }
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

Invoke-Step "Install PowerShell profile" {
  $src = Join-Path $scriptDir 'Microsoft.PowerShell_profile.ps1'
  # Use CurrentUserAllHosts so both pwsh and powershell 5.1 pick it up
  $dest = Join-Path (Split-Path $PROFILE.CurrentUserAllHosts) 'profile.ps1'
  Copy-IfChanged -Source $src -Dest $dest
  # Also drop the profile file for pwsh 7 specifically
  $pwshDest = Join-Path $env:USERPROFILE 'Documents\PowerShell\profile.ps1'
  Copy-IfChanged -Source $src -Dest $pwshDest
}

Invoke-Step "Install Windows Terminal settings" {
  $src = Join-Path $scriptDir 'WindowsTerminal-settings.json'
  $wtDir = Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState'
  if (-not (Test-Path $wtDir)) {
    Write-WarnMsg "Windows Terminal LocalState not found --launch WT once, then re-run this script"
    return
  }
  Copy-IfChanged -Source $src -Dest (Join-Path $wtDir 'settings.json')
}

# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------

if (-not $SkipClaude) {
  Invoke-Step "Install Claude Code" {
    if (Get-Command claude -ErrorAction SilentlyContinue) {
      Write-Ok "claude already installed"
    } else {
      Invoke-RestMethod -Uri 'https://claude.ai/install.ps1' | Invoke-Expression
      Write-Ok "claude installed --run 'claude' and '/login' to authenticate"
    }
  }

  Invoke-Step "Ensure ~\.local\bin is on the user PATH" {
    # Claude Code's Windows installer drops the binary in %USERPROFILE%\.local\bin
    # but doesn't update PATH. Add it for the user scope (persistent) and the
    # current session (so subsequent steps can 'claude').
    $toAdd = Join-Path $env:USERPROFILE '.local\bin'
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $segments = @()
    if ($userPath) { $segments = $userPath -split ';' }
    if ($segments -notcontains $toAdd) {
      $newPath = ($toAdd + ';' + $userPath).TrimEnd(';')
      [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
      Write-Ok "added $toAdd to user PATH (open a new shell to pick it up)"
    } else {
      Write-Ok "$toAdd already on user PATH"
    }
    # Make it work in the current session too
    if (($env:Path -split ';') -notcontains $toAdd) {
      $env:Path = "$toAdd;$env:Path"
    }
  }
}

# ---------------------------------------------------------------------------
# Simplewall
# ---------------------------------------------------------------------------

Invoke-Step "Add Simplewall to user PATH and startup" {
  $simplewallDir = 'C:\Program Files\simplewall'
  $simplewallExe = Join-Path $simplewallDir 'simplewall.exe'

  if (-not (Test-Path $simplewallExe)) {
    Write-WarnMsg "simplewall.exe not found at $simplewallExe -- skipping (run after winget installs it)"
    return
  }

  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
  $segments = if ($userPath) { $userPath -split ';' } else { @() }
  if ($segments -notcontains $simplewallDir) {
    $newPath = ($simplewallDir + ';' + $userPath).TrimEnd(';')
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    Write-Ok "added $simplewallDir to user PATH"
  } else {
    Write-Ok "$simplewallDir already on user PATH"
  }
  if (($env:Path -split ';') -notcontains $simplewallDir) {
    $env:Path = "$simplewallDir;$env:Path"
  }

  $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
  Set-RegistryValue -Path $runKey -Name 'simplewall' -Value $simplewallExe -Type 'String'
  Write-Ok "simplewall added to startup (HKCU Run)"
}

# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

Invoke-Step "Create git workspace at $GitDir" {
  # Default is C:\git so paths don't contain a space (Windows homedirs
  # often do, e.g. 'C:\Users\Leo Simons\', which breaks some build tools).
  if (-not (Test-Path $GitDir)) {
    New-Item -ItemType Directory -Force -Path $GitDir | Out-Null
    Write-Ok "created $GitDir"
  } else {
    Write-Ok "$GitDir exists"
  }
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

Write-Host ""
Write-Ok "Phase 1 complete."
Write-Info ""
Write-Info "Next steps (manual, interactive):"
Write-Info "  1. Launch Windows Terminal once (so LocalState exists) --re-run this script if needed"
Write-Info "  2. Sign in to 1Password, enable the SSH agent (Settings > Developer > Use the SSH agent)"
Write-Info "  3. gh auth login    # OAuth in browser"
Write-Info "  4. claude           # then /login"
Write-Info "  5. Configure Simplewall rules, then switch to alert mode"
Write-Info "  6. Run Pareto Security, remediate until all checks are green"
Write-Info ""
Write-Info "When those are done, run:  .\bootstrap-phase2.ps1"
