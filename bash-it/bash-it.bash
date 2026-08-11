# Bash-it configuration
# Loaded early to set up prompt, aliases, and completions

BASH_IT="${XDG_DATA_HOME:-$HOME/.local/share}/bash-it"

if [ -d "$BASH_IT" ]; then
    export BASH_IT
    export BASH_IT_THEME='robbyrussell'

    # Enable git plugin and completion.
    # shellcheck disable=SC2034  # read by bash_it.sh, sourced just below
    SCM_CHECK=true

    # shellcheck disable=SC1091  # bash-it is installed at runtime, outside this repo
    source "${BASH_IT}/bash_it.sh"
fi
