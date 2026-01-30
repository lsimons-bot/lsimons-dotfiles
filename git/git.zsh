# Git configuration following XDG Base Directory specification

# Set Git config location
export GIT_CONFIG_GLOBAL="$XDG_CONFIG_HOME/git/config"

# Ensure Git config directory exists
mkdir -p "$XDG_CONFIG_HOME/git"
