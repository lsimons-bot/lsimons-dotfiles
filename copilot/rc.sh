# Route git inside Copilot CLI sessions to the AI-specific git config so
# commits are signed with an on-disk SSH key (ssh-keygen) instead of
# op-ssh-sign -- no 1Password prompt mid-session. Mirrors the git-config-ai
# routing in the claude, codex, and pi-coding-agent topics. Copilot CLI has
# no config env block, so we scope GIT_CONFIG_GLOBAL to the launched process
# (like opencode/rc.sh / codex/rc.sh). Requires the git topic's config.ai.
copilot() {
  GIT_CONFIG_GLOBAL="${XDG_CONFIG_HOME:-$HOME/.config}/git/config.ai" command copilot "$@"
}
