# On a machine with claude.dockerByDefault, `claude` in an interactive
# shell runs Claude Code in claude-docker, and `claude-local` runs the host
# install. Functions rather than a ~/.local/bin/claude shim: the official
# installer owns that path, and scripts calling `claude` keep the host one.
# claude-docker/install.py writes the marker; see DEFAULT_MARKER there.
if [ -f "${XDG_CONFIG_HOME:-$HOME/.config}/claude-docker/default-claude" ]; then
  claude() {
    claude-docker --gh --glab "$@"
  }
  claude-local() {
    command claude "$@"
  }
fi
