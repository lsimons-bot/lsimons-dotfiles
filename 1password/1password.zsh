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
    
    local var_name="$1"
    local secret_ref="$2"
    local value
    
    value=$(op read "$secret_ref" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$value" ]; then
      export "$var_name"="$value"
      return 0
    else
      echo "Failed to load secret for $var_name" >&2
      return 1
    fi
  }
  
  # Load secrets from .env.1password if it exists
  # This file should contain secret references, not actual secrets
  # Format: VAR_NAME=op://vault/item/field
  if [ -f "$HOME/.dotfiles/1password/.env.1password" ]; then
    while IFS='=' read -r key value; do
      # Skip comments and empty lines
      [[ "$key" =~ ^#.*$ ]] && continue
      [ -z "$key" ] && continue
      
      # Remove any quotes around the value
      value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
      
      # Check if value is a 1Password reference
      if [[ "$value" =~ ^op:// ]]; then
        op_export "$key" "$value" || true
      fi
    done < "$HOME/.dotfiles/1password/.env.1password"
  fi
else
  echo "1Password CLI not installed. Install from: https://developer.1password.com/docs/cli/get-started/" >&2
fi
