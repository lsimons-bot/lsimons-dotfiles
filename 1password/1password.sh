# 1Password CLI integration
# Cache-first secret loading with 24-hour TTL

_op_cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/1password"
_op_cache_file="$_op_cache_dir/secrets.sh"
_op_env_file="${XDG_CONFIG_HOME:-$HOME/.config}/1password/env"

# Load cached secrets if cache exists and is less than 24 hours old
_op_cache_valid=0
if [ -f "$_op_cache_file" ]; then
  _op_cache_mtime=$(stat -f %m "$_op_cache_file" 2>/dev/null)
  _op_now=$(date +%s)
  if [ -n "$_op_cache_mtime" ] && [ $((_op_now - _op_cache_mtime)) -lt 86400 ]; then
    _op_cache_valid=1
  fi
fi

if [ "$_op_cache_valid" -eq 1 ]; then
  . "$_op_cache_file"
elif command -v op > /dev/null 2>&1 && [ -f "$_op_env_file" ]; then
  # Resolve secrets via op run, capture export statements, write to cache
  _op_vars=$(grep -v '^#' "$_op_env_file" | grep -v '^$' | grep 'op://' | cut -d= -f1 | tr '\n' ' ')
  if [ -n "$_op_vars" ]; then
    _op_resolved=$(op run --no-masking --env-file="$_op_env_file" -- sh -c '
      for v in '"$_op_vars"'; do
        val=$(printenv "$v" 2>/dev/null)
        [ -n "$val" ] && printf "export %s=%q\n" "$v" "$val"
      done
    ' 2>/dev/null) || true
    if [ -n "$_op_resolved" ]; then
      mkdir -p "$_op_cache_dir"
      printf '%s\n' "$_op_resolved" > "$_op_cache_file"
      chmod 600 "$_op_cache_file"
      . "$_op_cache_file"
    fi
    unset _op_resolved
  fi
  unset _op_vars
fi

unset _op_cache_dir _op_cache_file _op_env_file _op_cache_valid _op_cache_mtime _op_now

# Helper functions for ad-hoc terminal use
if command -v op > /dev/null 2>&1; then
  # Load a single secret from 1Password
  # Usage: op_load_secret "op://vault/item/field"
  op_load_secret() {
    if [ -z "$1" ]; then
      echo "Usage: op_load_secret <secret-reference>" >&2
      return 1
    fi
    op read "$1" 2>/dev/null
  }

  # Set environment variable from 1Password
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
fi
