# Claude Code sources this before every Bash tool command (CLAUDE_ENV_FILE).
# It loads the mise.toml [env] and tool PATH for the current directory:
# the shims alone give the right tool versions but not the project's
# environment variables, and `mise activate` never runs in that shell.
#
# BASH_ENV would look like the obvious hook, but Claude Code's command
# shells do not read it (only the one-off shell it snapshots at startup does).
if command -v mise >/dev/null 2>&1; then
  eval "$(mise hook-env -s bash 2>/dev/null)" || true
fi
