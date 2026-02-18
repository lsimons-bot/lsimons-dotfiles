# lsimons-dotfiles

Homedir setup for @lsimons (and @lsimons-bot)

A modular dotfiles configuration for macOS, featuring ZSH and Bash support, XDG Base Directory compliance, and 1Password CLI integration for secure secret management.

## Features

- **Modular topic-based structure** - Inspired by [holman/dotfiles](https://github.com/holman/dotfiles)
- **XDG Base Directory compliant** - Follows the [freedesktop.org specification](https://specifications.freedesktop.org/basedir-spec/latest/)
- **1Password integration** - Load secrets securely without storing them in git
- **ZSH configuration** - Clean, modular ZSH setup with Oh My Zsh
- **Bash configuration** - Modular Bash setup with the same topic-based loading
- **Python-based installation** - Idempotent installation automation
- **Homebrew integration** - Automatically installs packages via Homebrew
- **Development tools** - Includes editors, terminals, CLI tools, and coding agents

## Quick Start

For a fresh VM setup (UTM, Little Snitch, accounts), see [AGENT_SETUP.md](./docs/AGENT_SETUP.md) first.

On an existing macOS system with Homebrew:

```bash
mkdir -p ~/git/lsimons && cd ~/git/lsimons
git clone https://github.com/lsimons/lsimons-dotfiles.git
cd lsimons-dotfiles
./script/install.py
source ~/.zshrc
```

## What Gets Installed

The installation script (`./script/install.py`) will:

1. **Install Homebrew** (if not present)
2. **Install Python** via Homebrew (if not present)
3. **Create `~/.dotfiles` symlink** pointing to this repository
4. **Set up XDG directories** (`~/.config`, `~/.local/share`, `~/.cache`, `~/.local/state`)
5. **Symlink dotfiles** to appropriate locations
6. **Run topic installers** for development tools:

| Topic | Installs |
|-------|----------|
| `1password/` | 1Password CLI (`op`) |
| `aws/` | AWS CLI (`awscli`) + default `~/.aws/config` |
| `bash/` | Bash configuration and directories |
| `bash-it/` | Bash-it framework (prompt, plugins) |
| `brave/` | Brave Browser |
| `gemini/` | Gemini CLI |
| `gh/` | GitHub CLI |
| `ghostty/` | Ghostty terminal |
| `git/` | Git (via Homebrew) |
| `jdk/` | JDK configuration |
| `node/` | nvm and Node.js LTS |
| `oh-my-zsh/` | Oh My Zsh |
| `pi-coding-agent/` | pi-coding-agent |
| `python/` | Python configuration |
| `ssh/` | SSH configuration (post-quantum warning, 1Password agent) |
| `terraform/` | tfenv and Terraform |
| `tmux/` | tmux |
| `topgrade/` | topgrade (automated updates) |
| `uv/` | uv (Python package manager) |
| `zed/` | Zed editor |
| `zsh/` | ZSH directories |

## For AI Agents

If you're an AI coding agent (GitHub Copilot, Claude Code, etc.) working on this repository, please read [AGENTS.md](AGENTS.md) for detailed instructions and guidelines.

## Structure

```
.
├── script/           # Installation scripts and helpers
│   ├── install.py    # Main installer
│   └── helpers.py    # Shared functions for topic installers
├── machines/         # Machine-specific configuration
│   ├── default.json  # Default config (used when no hostname match)
│   └── <hostname>.json # Per-machine overrides
├── aws/              # AWS CLI and configuration
├── sh/               # Shared shell configuration (sourced by both bash and zsh)
├── bash/             # Bash-specific configuration
├── 1password/        # 1Password CLI integration
├── brave/            # Brave browser installer
├── gemini/           # Gemini CLI installer
├── gh/               # GitHub CLI installer
├── ghostty/          # Ghostty terminal installer
├── git/              # Git configuration and installer
├── jdk/              # JDK configuration
├── node/             # nvm and Node.js
├── oh-my-zsh/        # Oh My Zsh installer
├── pi-coding-agent/  # Coding agent installer
├── python/           # Python configuration
├── ssh/              # SSH configuration
├── terraform/        # tfenv and Terraform
├── tmux/             # tmux installer
├── topgrade/         # topgrade installer
├── uv/               # uv Python package manager
├── zed/              # Zed editor installer
└── zsh/              # ZSH-specific configuration
```

### File Naming Convention

- `*.symlink` - Files symlinked to home directory or XDG directories
- `*.sh` - Shared shell config, sourced by both bash and zsh
- `*.zsh` - ZSH-specific config, sourced only by zsh
- `*.bash` - Bash-specific config, sourced only by bash
- `path.sh` / `path.zsh` / `path.bash` - Loaded first, for PATH configuration
- `completion.sh` / `completion.zsh` / `completion.bash` - Loaded last
- `install.py` - Topic-specific installation script

Loading order: `*.sh` files first, then shell-specific files (`*.zsh` or `*.bash`), so shell-specific config can override shared defaults.

## XDG Base Directory Compliance

This setup follows the XDG Base Directory specification:

| Variable | Default | Purpose |
|----------|---------|---------|
| XDG_CONFIG_HOME | ~/.config | Configuration files |
| XDG_DATA_HOME | ~/.local/share | Data files |
| XDG_CACHE_HOME | ~/.cache | Cache files |
| XDG_STATE_HOME | ~/.local/state | State files (logs, history) |

All tools are configured to respect these directories:
- ZSH history: `~/.local/state/zsh/history`
- Bash history: `~/.local/state/bash/history`
- Python history: `~/.local/state/python/history`
- Git config: `~/.config/git/config`
- nvm: `~/.local/share/nvm`

## Machine-Specific Configuration

The `machines/` directory contains per-machine configuration in JSON format. During installation, `get_machine_config()` in `helpers.py` loads `machines/<short-hostname>.json`, falling back to `machines/default.json`.

Currently used for git user identity:
- **default.json**: Leo Simons / mail@leosimons.com (main laptops)
- **sbp-mac-ai.json**: Leo-Bot Simons / bot@leosimons.com (AI coding machine)

To add a new machine, create `machines/<hostname>.json` (use `hostname -s` to get the short hostname).

## 1Password Integration

Secrets are loaded from 1Password at shell startup, not stored in git.

### Setup

1. Authenticate with 1Password CLI:
   ```bash
   op signin
   ```

2. Add secret references (get these from 1Password app: right-click field, "Copy Secret Reference"):
   ```bash
   echo "GITHUB_TOKEN=op://AI/GitHub/personal_access_token/password" >> 1password/.env.1password
   ```

### Usage

Secrets are automatically loaded when you start a new shell. Helper functions:

```bash
# Load a single secret
op_load_secret "op://AI/GitHub/personal_access_token/password"

# Export a secret as an environment variable
op_export GITHUB_TOKEN "op://AI/GitHub/personal_access_token/password"
```

## Customization

### Adding a New Topic

1. Create a directory:
   ```bash
   mkdir ~/.dotfiles/mytopic
   ```

2. Add files:
   - `mytopic.sh` - Shared shell config (auto-loaded in both bash and zsh)
   - `mytopic.zsh` - ZSH-specific config (optional)
   - `mytopic.bash` - Bash-specific config (optional)
   - `mytopic.symlink` - File to symlink
   - `install.py` - Installation script (optional)

3. Re-run installer:
   ```bash
   ~/.dotfiles/script/install.py
   ```

## Troubleshooting

### ZSH not loading configuration

Check symlink:
```bash
ls -la ~/.zshrc
# Should show: ~/.zshrc -> ~/.dotfiles/zsh/zshrc.symlink
```

### Bash not loading configuration

Check symlinks:
```bash
ls -la ~/.bashrc ~/.bash_profile
# Should show: ~/.bashrc -> ~/.dotfiles/bash/bashrc.symlink
# Should show: ~/.bash_profile -> ~/.dotfiles/bash/bash_profile.symlink
```

### 1Password secrets not loading

1. Check CLI is installed: `which op`
2. Check authentication: `op account list`
3. Test manually: `op read "op://AI/Example Service/password"`

### XDG directories not created

Re-run installer:
```bash
~/.dotfiles/script/install.py
```

## License

See [LICENSE.md](./LICENSE.md) file.

## Inspiration

- [holman/dotfiles](https://github.com/holman/dotfiles)
- [iheitlager/dotfiles](https://github.com/iheitlager/dotfiles)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/)
