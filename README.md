# lsimons-dotfiles

Homedir setup for @lsimons (and @lsimons-bot)

A modular dotfiles configuration for macOS, featuring ZSH and Python support, XDG Base Directory compliance, and 1Password CLI integration for secure secret management.

## Features

- **Modular topic-based structure** - Inspired by [holman/dotfiles](https://github.com/holman/dotfiles)
- **XDG Base Directory compliant** - Follows the [freedesktop.org specification](https://specifications.freedesktop.org/basedir-spec/latest/)
- **1Password integration** - Load secrets securely without storing them in git
- **ZSH configuration** - Clean, modular ZSH setup with Oh My Zsh
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
| `brave/` | Brave Browser |
| `gemini/` | Gemini CLI |
| `gh/` | GitHub CLI |
| `ghostty/` | Ghostty terminal |
| `git/` | Git (via Homebrew) |
| `node/` | nvm and Node.js LTS |
| `oh-my-zsh/` | Oh My Zsh |
| `pi-coding-agent/` | pi-coding-agent |
| `python/` | Python configuration |
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
├── 1password/        # 1Password CLI integration
├── brave/            # Brave browser installer
├── gemini/           # Gemini CLI installer
├── gh/               # GitHub CLI installer
├── ghostty/          # Ghostty terminal installer
├── git/              # Git configuration and installer
├── node/             # nvm and Node.js
├── oh-my-zsh/        # Oh My Zsh installer
├── pi-coding-agent/  # Coding agent installer
├── python/           # Python configuration
├── tmux/             # tmux installer
├── topgrade/         # topgrade installer
├── uv/               # uv Python package manager
├── zed/              # Zed editor installer
└── zsh/              # ZSH configuration
```

### File Naming Convention

- `*.symlink` - Files symlinked to home directory or XDG directories
- `*.zsh` - ZSH configuration files, automatically sourced
- `path.zsh` - Loaded first, for PATH configuration
- `completion.zsh` - Loaded last, for completion configuration
- `install.py` - Topic-specific installation script

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
- Python history: `~/.local/state/python/history`
- Git config: `~/.config/git/config`
- nvm: `~/.local/share/nvm`

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
   - `mytopic.zsh` - Shell configuration (auto-loaded)
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
