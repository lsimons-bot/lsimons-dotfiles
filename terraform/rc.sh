# The Arch tfenv package keeps Terraform versions in /var/lib/tfenv but
# leaves TFENV_CONFIG_DIR at the root-owned /opt/tfenv, which makes
# `tfenv install` prompt to fall back to ~/.tfenv. Use an XDG path instead.
# terraform/install.py uses the same path.
if [ -d /var/lib/tfenv ] && [ -z "${TFENV_CONFIG_DIR:-}" ]; then
  export TFENV_CONFIG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/tfenv"
fi
