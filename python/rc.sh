# Python configuration following XDG Base Directory specification

# Set Python user base to XDG_DATA_HOME
export PYTHONUSERBASE="$XDG_DATA_HOME/python"

# Python startup file (for interactive sessions)
export PYTHONSTARTUP="$XDG_CONFIG_HOME/python/pythonrc"

# IPython configuration
export IPYTHONDIR="$XDG_CONFIG_HOME/ipython"

# Jupyter configuration
export JUPYTER_CONFIG_DIR="$XDG_CONFIG_HOME/jupyter"

# pip configuration
export PIP_CONFIG_FILE="$XDG_CONFIG_HOME/pip/pip.conf"
export PIP_LOG="$XDG_CACHE_HOME/pip/log"

# Add Python user bin to PATH
if [ -d "$PYTHONUSERBASE/bin" ]; then
  export PATH="$PYTHONUSERBASE/bin:$PATH"
fi

# Ensure Python directories exist
mkdir -p "$XDG_CONFIG_HOME/python"
mkdir -p "$XDG_CONFIG_HOME/pip"
mkdir -p "$XDG_CACHE_HOME/pip"

# Alias python to python3 (Homebrew best practice)
if command -v python3 >/dev/null 2>&1; then
  alias python=python3
fi
