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
For the Windows 11 ARM64 sandbox variant, see [AGENT_WINDOWS_SETUP.md](./docs/AGENT_WINDOWS_SETUP.md) and [windows/README.md](./windows/README.md).

On an existing macOS system with Homebrew:

```bash
mkdir -p ~/git/lsimons && cd ~/git/lsimons
git clone https://github.com/lsimons/lsimons-dotfiles.git
cd lsimons-dotfiles
./script/install.py              # preview first: ./script/install.py --dry-run
source ~/.zshrc
```

Once mise is installed you can also use `mise run install` (add
`-- --dry-run` to preview) and `mise run check` for subsequent runs.

Run `mise run check` (or `python3 script/check.py`) to validate the
repo without touching your system — this is what CI runs on every push.
Prefer `mise run check`: it bootstraps ruff via `.mise.toml`'s
`[tools]` section so linting is always covered. The bare `check.py`
entry point skips ruff with a warning when it's not on PATH.

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
| `ansible/` | Ansible and related tools |
| `aws/` | AWS CLI (`awscli`) + default `~/.aws/config` |
| `azure/` | Azure CLI (`az`) |
| `bash/` | Bash configuration and directories |
| `bash-it/` | Bash-it framework (prompt, plugins) |
| `claude/` | Claude Code CLI and configuration |
| `colors/` | `pastel` color CLI + docs for theme/palette files across tools |
| `copilot/` | GitHub Copilot CLI |
| `docker/` | Docker |
| `gemini/` | Gemini CLI |
| `fnox/` | fnox (1Password secret injection, via mise) |
| `fonts/` | Fonts (Cascadia Code, Iosevka, JetBrains Mono, Lilex, Lilex Nerd Font) |
| `gh/` | GitHub CLI |
| `go/` | Go (via mise) |
| `ghostty/` | Ghostty terminal |
| `git/` | Git (via Homebrew) |
| `jdk/` | OpenJDK (via mise) |
| `lsimons-agent/` | LLM agent environment configuration |
| `mise/` | mise (polyglot tool version manager) |
| `node/` | Node.js (via mise) + pnpm (via corepack) |
| `oh-my-zsh/` | Oh My Zsh |
| `opencode/` | OpenCode CLI |
| `openspec/` | openspec |
| `pi-coding-agent/` | pi-coding-agent |
| `python/` | Python (via mise) + XDG config |
| `ruby/` | Ruby (via mise) |
| `rust/` | Rust (via mise) + CARGO_HOME |
| `sh/` | Shared shell configuration (PATH, XDG, settings) |
| `ssh/` | SSH configuration (post-quantum warning, 1Password agent) |
| `terminal/` | macOS Terminal.app "LSD Warm Light" profile (mirrors Ghostty) |
| `terraform/` | tfenv and Terraform |
| `tmux/` | tmux |
| `topgrade/` | topgrade (automated updates) |
| `uv/` | uv (Python package manager) |
| `vivaldi/` | Vivaldi Browser |
| `wordpress/` | WordPress shell environment |
| `zed/` | Zed editor |
| `zsh/` | ZSH directories |

## For AI Agents

If you're an AI coding agent (GitHub Copilot, Claude Code, etc.) working on this repository, please read [AGENTS.md](AGENTS.md) for detailed instructions and guidelines.

## Structure

```
.
├── script/           # Installation scripts and helpers
│   ├── install.py    # Main installer (supports --dry-run)
│   ├── check.py      # Validation checks (py_compile, ruff, JSON, install dry-run)
│   └── helpers.py    # Shared functions for topic installers
├── machines/         # Machine-specific configuration
│   ├── default.json  # Default config (used when no hostname match)
│   └── <hostname>.json # Per-machine overrides
└── <topic>/          # One directory per topic (see table above)
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
- mise installs/shims: `~/.local/share/mise/`

## Machine-Specific Configuration

The `machines/` directory contains per-machine configuration in JSON format. During installation, `get_machine_config()` in `helpers.py` loads `machines/<short-hostname>.json`, merging with `machines/default.json`.

To add a new machine, create `machines/<hostname>.json` (use `hostname -s` to get the short hostname).

## 1Password Integration

Secrets are loaded from 1Password, not stored in git. See the [1Password topic](./1password).

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
