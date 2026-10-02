# mise (polyglot tool version manager) activation for zsh
# https://mise.jdx.dev/
if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate zsh)"
fi
