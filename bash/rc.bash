# Bash prompt and color defaults.
#
# Ubuntu's stock ~/.bashrc provides a colored prompt and color-aware ls/grep
# aliases. bashrc.symlink replaces that file, so the same defaults live here.
# zsh gets all of this from oh-my-zsh and powerlevel10k instead.

case "$TERM" in
  xterm-color|*-256color|xterm-ghostty|alacritty|foot|wezterm) color_prompt=yes ;;
  *) color_prompt= ;;
esac
if [ -z "$color_prompt" ] && command -v tput >/dev/null && tput setaf 1 >/dev/null 2>&1; then
  color_prompt=yes
fi

if [ "$color_prompt" = yes ]; then
  PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
else
  PS1='\u@\h:\w\$ '
fi
unset color_prompt

# Set the terminal title on xterm-compatible terminals.
case "$TERM" in
  xterm*|rxvt*|*-256color|alacritty|foot|wezterm)
    PS1="\[\e]0;\u@\h: \w\a\]$PS1"
    ;;
esac

# GNU ls (Linux) takes --color; BSD ls (macOS) uses CLICOLOR.
if command -v dircolors >/dev/null; then
  if [ -r "${XDG_CONFIG_HOME:-$HOME/.config}/dircolors" ]; then
    eval "$(dircolors -b "${XDG_CONFIG_HOME:-$HOME/.config}/dircolors")"
  else
    eval "$(dircolors -b)"
  fi
  alias ls='ls --color=auto'
else
  export CLICOLOR=1
fi
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# Bash-specific XDG configuration

export HISTFILE="$XDG_STATE_HOME/bash/history"
export HISTSIZE=10000
export HISTFILESIZE=10000

# Ensure Bash state directory exists
mkdir -p "$(dirname "$HISTFILE")"
