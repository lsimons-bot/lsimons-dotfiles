# lsimons-dotfiles

Homedir setup for @lsimons (and @lsimons-bot)

A modular dotfiles configuration for macOS, featuring ZSH and Python support, XDG Base Directory compliance, and 1Password CLI integration for secure secret management.

## Features

- 🗂️ **Modular topic-based structure** - Inspired by [holman/dotfiles](https://github.com/holman/dotfiles)
- 📁 **XDG Base Directory compliant** - Follows the [freedesktop.org specification](https://specifications.freedesktop.org/basedir-spec/latest/)
- 🔐 **1Password integration** - Load secrets securely without storing them in git
- 🐚 **ZSH configuration** - Clean, modular ZSH setup
- 🐍 **Python-based installation** - Uses Python for installation automation
- 🍺 **Homebrew integration** - Automatically installs and uses Homebrew
- 🔄 **Idempotent installation** - Safe to run multiple times
- 💾 **Automatic backups** - Backs up existing files before making changes

## Prerequisites

Before installation, ensure you have:

1. **macOS** (tested on macOS)
2. **ZSH** as your shell (default on modern macOS)
3. **Git** installed
4. **Internet connection** (for downloading Homebrew and Python)

**Note:** The installation script will automatically install Homebrew and Python if not present. 1Password CLI is optional for secret management.

## For AI Agents

If you're an AI coding agent (GitHub Copilot, Claude Code, etc.) working on this repository, please read [AGENTS.md](AGENTS.md) for detailed instructions and guidelines.

## Installation

This installation follows after the manual setup steps described in the [agent-setup documentation](https://github.com/lsimons/lsimons-bot/blob/main/docs/agent-setup.md).

### Quick Start

```bash
# Clone the repository
git clone https://github.com/lsimons/lsimons-dotfiles.git ~/.dotfiles
cd ~/.dotfiles

# Run the installation script (installs Homebrew, Python, and dependencies)
./script/install.py

# Run the bootstrap script to symlink dotfiles
./script/bootstrap

# Reload your shell
source ~/.zshrc
```

### What Gets Installed

The installation process will:

1. **Install Homebrew** (if not already installed)
   - The macOS package manager

2. **Install Python via Homebrew** (if not already installed)
   - Python 3.x from Homebrew
   - Used for running installation scripts

3. **Run topic-specific installers** (if any exist)
   - Each topic can have its own `install.py` script

The bootstrap script will then:

1. Create XDG Base Directory structure:
   - `~/.config` (XDG_CONFIG_HOME)
   - `~/.local/share` (XDG_DATA_HOME)
   - `~/.cache` (XDG_CACHE_HOME)
   - `~/.local/state` (XDG_STATE_HOME)

2. Symlink configuration files:
   - `~/.zshrc` → ZSH configuration
   - `~/.config/git/config` → Git configuration
   - `~/.config/python/pythonrc` → Python startup

3. Backup any existing files to `~/.dotfiles-backup/`

## Structure

The repository is organized by topics:

```
.
├── 1password/         # 1Password CLI integration
├── git/              # Git configuration
├── python/           # Python configuration
├── zsh/              # ZSH configuration
├── script/           # Installation scripts
│   ├── bootstrap     # Symlink dotfiles
│   └── install       # Run topic installers
└── bin/              # Custom executables
```

### File Naming Convention

- `*.symlink` - Files that will be symlinked to your home directory or XDG directories
- `*.zsh` - ZSH configuration files, automatically sourced
- `path.zsh` - Loaded first, for PATH configuration
- `completion.zsh` - Loaded last, for completion configuration
- `install.py` - Topic-specific installation script (preferred)
- `install.sh` - Legacy bash installation script (deprecated, use install.py instead)

## XDG Base Directory Compliance

This setup follows the XDG Base Directory specification to keep your home directory organized:

| Variable | Default | Purpose |
|----------|---------|---------|
| XDG_CONFIG_HOME | ~/.config | Configuration files |
| XDG_DATA_HOME | ~/.local/share | Data files |
| XDG_CACHE_HOME | ~/.cache | Cache files |
| XDG_STATE_HOME | ~/.local/state | State files (logs, history) |

All tools are configured to respect these directories:
- ZSH history → `~/.local/state/zsh/history`
- Python history → `~/.local/state/python/history`
- Git config → `~/.config/git/config`
- Completion cache → `~/.cache/zsh/`

## 1Password Integration

Secrets are loaded from 1Password, not stored in git.

### Setup

1. Install 1Password CLI:
   ```bash
   brew install 1password-cli
   ```

2. Authenticate:
   ```bash
   op signin
   ```

3. Create a secrets configuration file:
   ```bash
   cp ~/.dotfiles/1password/.env.1password.example ~/.dotfiles/1password/.env.1password
   ```

4. Add your secret references:
   ```bash
   # Example content of .env.1password
   GITHUB_TOKEN=op://Development/GitHub/personal_access_token
   AWS_ACCESS_KEY_ID=op://Development/AWS/access_key_id
   ```

### Usage

Secrets are automatically loaded when you start a new shell session. You can also use the helper functions:

```bash
# Load a single secret
op_load_secret "op://Development/GitHub/token"

# Export a secret as an environment variable
op_export GITHUB_TOKEN "op://Development/GitHub/token"
```

### Getting Secret References

1. Open 1Password desktop app
2. Find your item
3. Right-click on a field → **Copy Secret Reference**
4. Paste into `.env.1password`

## Customization

### Adding a New Topic

1. Create a directory for your topic:
   ```bash
   mkdir ~/.dotfiles/mytopic
   ```

2. Add configuration files:
   - `mytopic.zsh` - Shell configuration (auto-loaded)
   - `mytopic.symlink` - File to symlink
   - `install.sh` - Installation script (optional)

3. (Optional) Run topic-specific installers:
   ```bash
   ~/.dotfiles/script/install.py
   ```

### Modifying Existing Configuration

Simply edit the files in the topic directories and reload your shell:

```bash
source ~/.zshrc
```

## Uninstallation

To uninstall:

1. Remove symlinks:
   ```bash
   rm ~/.zshrc
   rm -rf ~/.config/git/config
   rm -rf ~/.config/python/pythonrc
   ```

2. Restore from backup if needed:
   ```bash
   ls ~/.dotfiles-backup/
   ```

3. Remove the repository:
   ```bash
   rm -rf ~/.dotfiles
   ```

## Troubleshooting

### ZSH not loading configuration

Ensure `~/.zshrc` is properly symlinked:
```bash
ls -la ~/.zshrc
```

Should show: `~/.zshrc -> /Users/yourusername/.dotfiles/zsh/zshrc.symlink`

### 1Password secrets not loading

1. Check 1Password CLI is installed: `which op`
2. Check authentication: `op account list`
3. Verify secret reference format: `op://vault-name/item-name/field-name`
4. Test manually: `op read "op://vault/item/field"`

### XDG directories not created

Run bootstrap again:
```bash
~/.dotfiles/script/bootstrap
```

## Contributing

This is a personal dotfiles repository, but suggestions are welcome via issues.

## License

See [LICENSE](LICENSE) file.

## Inspiration

- [holman/dotfiles](https://github.com/holman/dotfiles)
- [iheitlager/dotfiles](https://github.com/iheitlager/dotfiles)
- [dotfiles.github.io](https://dotfiles.github.io/)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/)
