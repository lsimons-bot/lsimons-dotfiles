# Add custom bin directories to PATH
# Loaded first by zshrc

# Add dotfiles bin directory
if [ -d "$HOME/.dotfiles/bin" ]; then
  export PATH="$HOME/.dotfiles/bin:$PATH"
fi

# Add local bin directory
if [ -d "$HOME/.local/bin" ]; then
  export PATH="$HOME/.local/bin:$PATH"
fi

# Rancher Desktop
if [ -d "$HOME/.rd/bin" ]; then
  export PATH="$HOME/.rd/bin:$PATH"
fi

# LM Studio
if [ -d "$HOME/.lmstudio/bin" ]; then
  export PATH="$HOME/.lmstudio/bin:$PATH"
fi
