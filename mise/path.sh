# mise shims fallback for non-interactive shells.
# `mise activate` (in mise/rc.zsh / mise/rc.bash) handles interactive sessions;
# this ensures shims are discoverable in scripts and sh-invoked subprocesses.
if [ -d "$XDG_DATA_HOME/mise/shims" ]; then
  export PATH="$XDG_DATA_HOME/mise/shims:$PATH"
fi
