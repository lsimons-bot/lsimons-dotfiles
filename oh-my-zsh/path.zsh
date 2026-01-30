# Oh My Zsh configuration
# Loaded early via path.zsh to ensure oh-my-zsh is available for other topics

# Path to oh-my-zsh installation
export ZSH="$HOME/.oh-my-zsh"

# Only proceed if oh-my-zsh is installed
if [ -d "$ZSH" ]; then
    # Use XDG-compliant path for completion dump
    export ZSH_COMPDUMP="$XDG_CACHE_HOME/zsh/zcompdump-$ZSH_VERSION"
    # Theme configuration
    ZSH_THEME="robbyrussell"

    # Plugin configuration
    plugins=(
        git
        brew
        macos
    )

    # Disable auto-update prompts (use topgrade instead)
    zstyle ':omz:update' mode disabled

    # Source oh-my-zsh
    source "$ZSH/oh-my-zsh.sh"
fi
