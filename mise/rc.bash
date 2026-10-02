# mise (polyglot tool version manager) activation for bash
# https://mise.jdx.dev/
if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate bash)"
fi
