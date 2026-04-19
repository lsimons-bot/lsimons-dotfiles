#Requires -Version 7.0
# Claude Code status line script (Windows/PowerShell port of statusline-command.sh)
# Reads JSON from stdin, outputs a formatted ANSI-coloured status line.

$raw  = [Console]::In.ReadToEnd()
$json = $raw | ConvertFrom-Json

# Extract fields (all optional — degrade gracefully)
$model        = if ($json.model.display_name)  { $json.model.display_name }  else { 'Claude' }
$cwd          = $json.workspace.current_dir ?? $json.cwd ?? ''
$outputStyle  = $json.output_style.name
$reasoning    = $json.model.reasoning_effort ?? $json.reasoning_effort ?? $json.model.thinking.type
$usedPct      = $json.context_window.used_percentage
$remainingPct = $json.context_window.remaining_percentage
$inputTokens  = ($json.context_window.current_usage.input_tokens                    ?? 0) +
                ($json.context_window.current_usage.cache_creation_input_tokens     ?? 0) +
                ($json.context_window.current_usage.cache_read_input_tokens         ?? 0)
$contextSize  = $json.context_window.context_window_size ?? $json.context_window.total

# ANSI escape codes
$ESC     = [char]27
$RESET   = "$ESC[0m"
$DIM     = "$ESC[2m"
$CYAN    = "$ESC[36m"
$BLUE    = "$ESC[34m"
$GREEN   = "$ESC[32m"
$YELLOW  = "$ESC[33m"
$RED     = "$ESC[31m"
$MAGENTA = "$ESC[35m"

# Shorten home directory
$shortCwd = if ($cwd) { $cwd -replace [regex]::Escape($env:USERPROFILE), '~' } else { '~' }

# Git branch
$gitBranch = ''
if ($cwd -and (Get-Command git -ErrorAction SilentlyContinue)) {
  $gitBranch = git -C $cwd symbolic-ref --short HEAD 2>$null
  if (-not $gitBranch) {
    $gitBranch = git -C $cwd rev-parse --short HEAD 2>$null
  }
}

# Context bar coloured by usage
$contextStr = ''
if ($null -ne $usedPct -and $null -ne $remainingPct) {
  $usedInt = [int][Math]::Round($usedPct)
  $remInt  = [int][Math]::Round($remainingPct)

  $ctxColor = if     ($usedInt -ge 80) { $RED }
              elseif ($usedInt -ge 50) { $YELLOW }
              else                     { $GREEN }

  $filled = [int]($usedInt / 10)
  $bar    = ('█' * $filled) + ('░' * (10 - $filled))

  $usedK  = [int](($inputTokens + 500) / 1000)
  $totalK = [int](($contextSize  + 500) / 1000)
  $tokensStr = if ($totalK -gt 0) { "${usedK}k/${totalK}k" } else { "${usedInt}%/${remInt}% left" }

  $contextStr = " ${ctxColor}${bar}${RESET} ${DIM}${tokensStr}${RESET}"
}

# Assemble the line
$line = "${CYAN}${model}${RESET}"
if ($reasoning)                                      { $line += " ${DIM}[${reasoning}]${RESET}" }
if ($outputStyle -and $outputStyle -ne 'default')   { $line += " ${DIM}(${outputStyle})${RESET}" }
$line += " ${DIM}in${RESET} ${BLUE}${shortCwd}${RESET}"
if ($gitBranch)                                      { $line += " ${DIM}on${RESET} ${MAGENTA}${gitBranch}${RESET}" }
$line += $contextStr

Write-Host $line
