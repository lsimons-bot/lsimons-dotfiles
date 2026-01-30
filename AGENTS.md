# Agent Instructions for lsimons-dotfiles

This document provides guidance for AI coding agents (GitHub Copilot, Claude Code, etc.) working on this repository.

## Repository Overview

This is a personal dotfiles repository for managing shell configuration, environment setup, and system configuration for macOS. The repository follows a modular, topic-based structure inspired by [holman/dotfiles](https://github.com/holman/dotfiles).

**Key Features:**
- Modular topic-based structure
- XDG Base Directory specification compliance
- 1Password CLI integration for secrets
- Python-based installation system
- Safe, idempotent installation scripts

## Architecture & Design Principles

### Topic-Based Organization

Each configuration topic lives in its own directory:
- `zsh/` - ZSH shell configuration
- `python/` - Python environment configuration
- `git/` - Git configuration
- `1password/` - Secret management with 1Password CLI
- `script/` - Installation and bootstrap scripts

### File Naming Conventions

- `*.symlink` - Files to be symlinked to home directory or XDG directories
- `*.zsh` - ZSH configuration files, automatically sourced
- `path.zsh` - Loaded first, for PATH configuration
- `completion.zsh` - Loaded last, for shell completion
- `install.py` - Python-based topic installation script
- `install.sh` - Bash-based topic installation script (deprecated, prefer Python)

### XDG Base Directory Compliance

All configuration must respect XDG Base Directory specification:
- `XDG_CONFIG_HOME` (default: `~/.config`) - Configuration files
- `XDG_DATA_HOME` (default: `~/.local/share`) - Data files
- `XDG_CACHE_HOME` (default: `~/.cache`) - Cache files
- `XDG_STATE_HOME` (default: `~/.local/state`) - State files (logs, history)

**Never** create dot-files directly in `$HOME` unless absolutely necessary for compatibility. Always prefer XDG paths.

### Installation Flow

1. User runs `./script/install.py` (Python-based installer)
2. Script installs Homebrew (if not present)
3. Script installs Python via Homebrew (if not present)
4. Script runs topic-specific `install.py` scripts using Homebrew Python
5. User runs `./script/bootstrap` to symlink dotfiles
6. User sources `~/.zshrc` to load configuration

## Development Guidelines

### Adding New Configuration Topics

When adding a new topic (e.g., `vim/`, `tmux/`, `rust/`):

1. Create a new directory: `mkdir <topic>/`
2. Add configuration files following naming conventions
3. (Optional) Create `<topic>/install.py` for topic-specific installation
4. Update `.gitignore` if topic generates temporary/cache files
5. Update `README.md` to document the new topic

Example structure:
```
newtopic/
├── newtopic.zsh          # Shell configuration (auto-loaded)
├── newtopicrc.symlink    # Config file to symlink
└── install.py            # Optional: installation script
```

### Writing Installation Scripts

Topic-specific `install.py` scripts should:
- Be idempotent (safe to run multiple times)
- Use Homebrew for macOS package management
- Follow XDG Base Directory specification
- Print clear status messages
- Handle errors gracefully
- Never require user input (fully automated)

Example template:
```python
#!/usr/bin/env python3
"""Installation script for <topic>"""

import subprocess
import sys
from pathlib import Path

def main():
    print("[INFO] Installing <topic>...")
    
    # Check if already installed
    result = subprocess.run(['which', 'command'], capture_output=True)
    if result.returncode == 0:
        print("[SUCCESS] <topic> already installed")
        return 0
    
    # Install via Homebrew
    try:
        subprocess.run(['brew', 'install', 'package'], check=True)
        print("[SUCCESS] <topic> installed")
        return 0
    except subprocess.CalledProcessError:
        print("[ERROR] Failed to install <topic>", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

### ZSH Configuration

ZSH files are loaded in this order:
1. `*/path.zsh` - PATH modifications first
2. `*/*.zsh` - All other .zsh files (except path and completion)
3. `*/completion.zsh` - Completion configuration last

Keep ZSH files:
- Modular and focused on one topic
- Free of side effects
- Fast to load (avoid expensive operations)

### Secret Management

**Never commit secrets to the repository!**

Use 1Password CLI for secret management:
- Store secrets in 1Password
- Reference secrets using `op://vault/item/field` format
- Load secrets at runtime using helper functions
- Add `.env.1password` to `.gitignore`

Example usage in ZSH:
```bash
# In 1password/.env.1password (gitignored)
GITHUB_TOKEN=op://Development/GitHub/personal_token

# Loaded automatically by 1password/1password.zsh
echo $GITHUB_TOKEN  # Contains actual secret value
```

### Testing Changes

Before committing:

1. **Test bootstrap script:**
   ```bash
   ./script/bootstrap
   ```
   Verify symlinks are created correctly.

2. **Test installation script:**
   ```bash
   ./script/install.py
   ```
   Verify Homebrew and Python setup works.

3. **Test ZSH configuration:**
   ```bash
   zsh -c 'source ~/.zshrc && echo "Success"'
   ```
   Verify no errors loading configuration.

4. **Verify XDG compliance:**
   Check that no new dot-files are created in `$HOME` unnecessarily.

5. **Check for secrets:**
   ```bash
   git diff
   ```
   Ensure no secrets are being committed.

## Common Tasks

### Adding a Homebrew Package

1. Add to appropriate topic's `install.py`:
   ```python
   subprocess.run(['brew', 'install', 'package-name'], check=True)
   ```

2. If it needs configuration, create corresponding `.zsh` file:
   ```bash
   # topic/package.zsh
   export PACKAGE_CONFIG="$XDG_CONFIG_HOME/package"
   ```

### Adding Environment Variables

Add to the appropriate topic's `.zsh` file:
```bash
# topic/topic.zsh
export MY_VAR="value"
export XDG_COMPLIANT_VAR="$XDG_CONFIG_HOME/topic"
```

### Adding Shell Aliases

Add to topic's `.zsh` file:
```bash
# topic/aliases.zsh
alias myalias='command'
```

### Adding to PATH

Add to topic's `path.zsh`:
```bash
# topic/path.zsh
if [ -d "/path/to/bin" ]; then
  export PATH="/path/to/bin:$PATH"
fi
```

## Troubleshooting Common Issues

### Symlink Already Exists

The bootstrap script backs up existing files to `~/.dotfiles-backup/` before creating new symlinks.

### Homebrew Not Found

Ensure Homebrew is installed and in PATH. The install script handles this automatically.

### Python Not Found

The install script installs Python via Homebrew. If issues persist, run:
```bash
brew install python@3
```

### ZSH Configuration Not Loading

Check that `~/.zshrc` is properly symlinked:
```bash
ls -la ~/.zshrc
# Should show: ~/.zshrc -> /path/to/dotfiles/zsh/zshrc.symlink
```

## Important Notes

### Platform Support

This repository is designed for **macOS only**. While the structure could work on Linux, installation scripts specifically target macOS with Homebrew.

### Minimal Changes Philosophy

When making changes:
- Keep modifications minimal and surgical
- Don't refactor working code without good reason
- Maintain backward compatibility when possible
- Test thoroughly before committing

### Dependencies

Core dependencies:
- macOS (Darwin)
- Homebrew (installed by install.py)
- Python 3 (installed via Homebrew)
- ZSH (default on modern macOS)

Optional dependencies:
- 1Password CLI (for secret management)
- Git (for version control)

## References

- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/)
- [holman/dotfiles](https://github.com/holman/dotfiles)
- [1Password CLI Documentation](https://developer.1password.com/docs/cli/)
- [Homebrew Documentation](https://docs.brew.sh/)

## Questions or Issues?

When uncertain about a change:
1. Check existing patterns in the repository
2. Follow XDG Base Directory specification
3. Keep changes minimal and focused
4. Test thoroughly before committing
5. Document significant changes in commit messages

---

*This document should be kept up to date as the repository evolves.*
