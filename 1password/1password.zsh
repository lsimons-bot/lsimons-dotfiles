# 1Password CLI integration
# Load secrets from 1Password instead of storing them in GitHub

# Check if 1Password CLI is available
if command -v op &> /dev/null; then
  # Function to load a secret from 1Password
  # Usage: op_load_secret "op://vault/item/field"
  op_load_secret() {
    if [ -z "$1" ]; then
      echo "Usage: op_load_secret <secret-reference>" >&2
      return 1
    fi
    op read "$1" 2>/dev/null
  }

  # Function to set environment variable from 1Password
  # Usage: op_export VAR_NAME "op://vault/item/field"
  op_export() {
    if [ -z "$1" ] || [ -z "$2" ]; then
      echo "Usage: op_export VAR_NAME <secret-reference>" >&2
      return 1
    fi
    local value
    if value=$(op read "$2" 2>/dev/null) && [ -n "$value" ]; then
      export "$1"="$value"
      return 0
    else
      echo "Failed to load secret for $1" >&2
      return 1
    fi
  }

  # Load secrets from .env.1password if it exists
  # Format: VAR_NAME=op://vault/item/field
  # Uses op run for efficient bulk loading (single op call with proper escaping)
  if [ -f "$HOME/.dotfiles/1password/.env.1password" ]; then
    local _op_vars
    _op_vars=$(grep -v '^#' "$HOME/.dotfiles/1password/.env.1password" | grep -v '^$' | grep 'op://' | cut -d= -f1 | tr '\n' ' ')
    if [ -n "$_op_vars" ]; then
      eval "$(op run --no-masking --env-file="$HOME/.dotfiles/1password/.env.1password" -- sh -c '
        for v in '"$_op_vars"'; do
          val=$(printenv "$v" 2>/dev/null)
          [ -n "$val" ] && printf "export %s=%q\n" "$v" "$val"
        done
      ' 2>/dev/null)" || true
    fi
  fi
fi
