# Wrap opencode so the LiteLLM API key is fetched from 1Password just
# before launch instead of sitting in a var or file. Requires `op`
# signed in (see the 1password topic). The 1Password account and
# reference come from the current machine's config (machines/*.json,
# "providers.litellm") — see provider_credential.py. There is no
# fallback: a machine with no such config fails closed.
opencode() {
  local cred_output
  cred_output=$(python3 "$HOME/.dotfiles/script/provider_credential.py" litellm) || return 1
  local PROVIDER_CREDENTIAL_OP_ACCOUNT PROVIDER_CREDENTIAL_OP_REF
  eval "$cred_output"
  local api_key
  api_key=$(OP_ACCOUNT="$PROVIDER_CREDENTIAL_OP_ACCOUNT" op read "$PROVIDER_CREDENTIAL_OP_REF") || return 1
  [ -n "$api_key" ] || return 1
  GIT_CONFIG_GLOBAL="${XDG_CONFIG_HOME:-$HOME/.config}/git/config.ai" \
    SBP_AI_API_KEY="$api_key" \
    command opencode "$@"
}
