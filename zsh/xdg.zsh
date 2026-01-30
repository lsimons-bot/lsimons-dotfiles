# XDG Base Directory configuration
# Follow https://specifications.freedesktop.org/basedir-spec/latest/

# Ensure XDG directories exist
mkdir -p "$XDG_CONFIG_HOME"
mkdir -p "$XDG_DATA_HOME"
mkdir -p "$XDG_CACHE_HOME"
mkdir -p "$XDG_STATE_HOME"
mkdir -p "$XDG_CACHE_HOME/zsh"

# Configure ZSH to use XDG paths
export ZDOTDIR="${ZDOTDIR:-$XDG_CONFIG_HOME/zsh}"
export HISTFILE="$XDG_STATE_HOME/zsh/history"
export HISTSIZE=10000
export SAVEHIST=10000

# Ensure ZSH state directory exists
mkdir -p "$(dirname "$HISTFILE")"
