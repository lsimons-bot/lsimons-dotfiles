[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# Locate the powerlevel10k theme. Homebrew and Arch install it to
# different prefixes, Debian/Ubuntu have no package so install.py clones
# it under XDG_DATA_HOME, and none of these is on a search path zsh knows
# about, so try each in turn and source the first one found.
() {
  local theme candidate
  local -a candidates

  if (( $+commands[brew] )); then
    candidates+=("$(brew --prefix powerlevel10k 2>/dev/null)/share/powerlevel10k/powerlevel10k.zsh-theme")
  fi
  candidates+=(
    /usr/share/zsh-theme-powerlevel10k/powerlevel10k.zsh-theme
    /usr/local/share/powerlevel10k/powerlevel10k.zsh-theme
    "${XDG_DATA_HOME:-$HOME/.local/share}/powerlevel10k/powerlevel10k.zsh-theme"
  )

  for candidate in $candidates; do
    if [[ -r $candidate ]]; then
      theme=$candidate
      break
    fi
  done

  [[ -n $theme ]] && source $theme
}
