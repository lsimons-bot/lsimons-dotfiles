# PowerShell profile for the Windows 11 ARM64 AI-agent VM.
# Symlinked to $PROFILE.CurrentUserAllHosts by bootstrap-phase1.ps1.
# See ../docs/AGENT_WINDOWS_SETUP.md for rationale.

# --- XDG-on-Windows ---
# Many tools respect XDG env vars even on Windows. Point them at LocalAppData
# subfolders so the home directory stays clean.
if (-not $env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME = Join-Path $env:APPDATA      'xdg\config' }
if (-not $env:XDG_DATA_HOME)   { $env:XDG_DATA_HOME   = Join-Path $env:LOCALAPPDATA 'xdg\data'   }
if (-not $env:XDG_CACHE_HOME)  { $env:XDG_CACHE_HOME  = Join-Path $env:LOCALAPPDATA 'xdg\cache'  }
if (-not $env:XDG_STATE_HOME)  { $env:XDG_STATE_HOME  = Join-Path $env:LOCALAPPDATA 'xdg\state'  }
foreach ($d in $env:XDG_CONFIG_HOME, $env:XDG_DATA_HOME, $env:XDG_CACHE_HOME, $env:XDG_STATE_HOME) {
  if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

# --- PSReadLine ---
if (Get-Module -ListAvailable -Name PSReadLine) {
  Import-Module PSReadLine
  Set-PSReadLineOption -HistorySavePath (Join-Path $env:XDG_STATE_HOME 'pwsh\history.txt')
  Set-PSReadLineOption -HistoryNoDuplicates
  # Prediction options need PSReadLine 2.2+ (ships with pwsh 7). Windows
  # PowerShell 5.1 carries 2.0.0, which lacks these parameters -- skip them
  # there so this shared profile doesn't error on 5.1.
  if ((Get-Module PSReadLine).Version -ge [version]'2.2.0') {
    Set-PSReadLineOption -PredictionSource HistoryAndPlugin
    Set-PSReadLineOption -PredictionViewStyle ListView
  }
  Set-PSReadLineOption -EditMode Emacs
  Set-PSReadLineKeyHandler -Key Tab -Function MenuComplete
  Set-PSReadLineKeyHandler -Key UpArrow -Function HistorySearchBackward
  Set-PSReadLineKeyHandler -Key DownArrow -Function HistorySearchForward
}

# --- 1Password SSH agent (named pipe) ---
# Tools that honour SSH_AUTH_SOCK on Windows need the pipe path.
# OpenSSH's own ssh.exe reads it via the OpenSSH Authentication Agent service,
# which 1Password replaces when developer mode is on.
if (-not $env:SSH_AUTH_SOCK) {
  $env:SSH_AUTH_SOCK = '\\.\pipe\openssh-ssh-agent'
}

# --- mise (polyglot tool version manager) ---
# mise's pwsh chpwd hook requires PowerShell 7+; activating under Windows
# PowerShell 5.1 only emits a warning, so gate it on the major version.
if (($PSVersionTable.PSVersion.Major -ge 6) -and
    (Get-Command mise -ErrorAction SilentlyContinue)) {
  mise activate pwsh | Out-String | Invoke-Expression
}

# --- zoxide (smarter cd) ---
if (Get-Command zoxide -ErrorAction SilentlyContinue) {
  Invoke-Expression (& { (zoxide init powershell | Out-String) })
}

# --- starship prompt ---
if (Get-Command starship -ErrorAction SilentlyContinue) {
  Invoke-Expression (&starship init powershell)
}

# --- fzf keybindings ---
if ((Get-Command fzf -ErrorAction SilentlyContinue) -and
    (Get-Module -ListAvailable -Name PSFzf)) {
  Import-Module PSFzf
  Set-PsFzfOption -PSReadlineChordProvider 'Ctrl+t' -PSReadlineChordReverseHistory 'Ctrl+r'
}

# --- Aliases mirroring macOS zsh setup where reasonable ---
Set-Alias -Name ll  -Value Get-ChildItem
if (Get-Command eza -ErrorAction SilentlyContinue) {
  function ls { eza --icons --group-directories-first @args }
  function la { eza --icons --group-directories-first -la @args }
  function lt { eza --icons --tree --level=2 @args }
}
if (Get-Command bat -ErrorAction SilentlyContinue) {
  Set-Alias -Name cat -Value bat -Option AllScope
}
Set-Alias -Name g -Value git

# --- Git worktree helper ---
function gst { git status $args }
function gco { git checkout $args }
function gp  { git pull --rebase; git push }

# --- Convenience: quick jump to repo root ---
function cdr {
  $root = git rev-parse --show-toplevel 2>$null
  if ($root) { Set-Location $root } else { Write-Warning "not in a git repo" }
}

# --- op helpers (1Password CLI) ---
function op-env {
  param([Parameter(Mandatory)][string]$EnvFile)
  op run --env-file=$EnvFile -- pwsh
}
