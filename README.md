# lsimons-dotfiles

Homedir setup for @lsimons (and @lsimons-bot)

A modular dotfiles configuration for macOS, Arch-based Linux ([Omarchy](https://omarchy.org/)) and Ubuntu (including under WSL2), featuring ZSH and Bash support, XDG Base Directory compliance, and 1Password CLI integration for secure secret management.

## Features

- **Modular topic-based structure** - Inspired by [holman/dotfiles](https://github.com/holman/dotfiles)
- **XDG Base Directory compliant** - Follows the [freedesktop.org specification](https://specifications.freedesktop.org/basedir-spec/latest/)
- **1Password integration** - Load secrets securely without storing them in git
- **ZSH configuration** - Clean, modular ZSH setup with Oh My Zsh
- **Bash configuration** - Modular Bash setup with the same topic-based loading
- **Python-based installation** - Idempotent installation automation
- **Cross-platform packaging** - One package name per platform: Homebrew
  on macOS, pacman/yay on Arch, apt on Ubuntu with mise filling the gaps
  in its archive. Topics that only make sense on one platform declare it
  in a `platforms.txt` and are skipped elsewhere
- **Development tools** - Includes editors, terminals, CLI tools, and coding agents

## Quick Start

These dotfiles install natively on **macOS**, **Arch-based Linux**
([Omarchy](https://omarchy.org/)) and **Ubuntu**, including Ubuntu under
**WSL2**. Native Windows is not a target of `install.py`; the `windows/`
directory bootstraps a Windows host with PowerShell instead. Pick your
platform:

| You are on | Do this |
|------------|---------|
| macOS | [Prepare](#macos), then run the [common steps](#common-steps) |
| Arch-based Linux (Omarchy) | Run the [common steps](#common-steps) |
| Ubuntu (desktop or server) | Run the [common steps](#common-steps) |
| Windows 11 | Bootstrap Windows with [windows/README.md](./windows/README.md), then optionally add [WSL2](#windows-11--wsl2) |
| Ubuntu under WSL2 | [Prepare Windows](#windows-11--wsl2), then run the common steps inside WSL |

For a fresh AI-agent VM (UTM, Little Snitch, accounts), read
[AGENT_SETUP.md](./docs/AGENT_SETUP.md) first; the Windows 11 ARM64
variant is [AGENT_WINDOWS_SETUP.md](./docs/AGENT_WINDOWS_SETUP.md).

### Common steps

Every machine must be enrolled before installing: the installer refuses
to run for a hostname without a `machines/<hostname>.json` (see
[Machine-Specific Configuration](#machine-specific-configuration)).

```bash
mkdir -p ~/git/lsimons && cd ~/git/lsimons
git clone https://github.com/lsimons/lsimons-dotfiles.git
cd lsimons-dotfiles
hostname -s                      # enroll: create machines/<this>.json if missing
./script/install.py --dry-run    # preview
./script/install.py
source ~/.zshrc                  # or open a new terminal
```

The installer needs **Python 3.11 or newer** and stops with a message if
the interpreter is too old. It bootstraps the platform's package manager
itself (Homebrew, yay, or the vendor apt repositories) and then runs
every topic that supports the platform. Installing packages needs root
on Linux, so `sudo` may ask for your password once — the same way a
Homebrew cask does on macOS.

Once mise is installed you can also use `mise run install` (add
`-- --dry-run` to preview) for subsequent runs.

### macOS

macOS only ships Python 3.9 in the Command Line Tools, so install
Homebrew and a current Python first:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python
```

Then run the common steps. Desktop apps (Ghostty, Zed, Vivaldi, fonts,
the 1Password app) install as Homebrew casks; the `dock/`, `terminal/`,
`swiftdialog/` and `timeout/` topics are macOS-only.

### Arch-based Linux (Omarchy)

Nothing to prepare: Arch is a rolling release, so its `python` is always
new enough, and the installer adds `base-devel`, `git` and `yay` itself.
Run the common steps. Omarchy is the first-class Linux desktop; the
`omarchy/` topic adds LSD Warm themes and an extra Hyprland keybinding
layer on top of Omarchy's own config, and other Arch derivatives are
recognised through `ID_LIKE` in `/etc/os-release`.

### Ubuntu

Nothing to prepare on Ubuntu 24.04 or newer, whose `python3` (3.12) is
new enough. On an older release, install a 3.11+ `python3` first (Ubuntu 22.04
ships 3.10, which is too old). Run the common steps. The bootstrap adds the
vendor apt repositories for mise, GitHub CLI and 1Password, which
Ubuntu's archive lacks or ships stale; the remaining developer CLIs come
from mise. Desktop topics (fonts, Ghostty, Zed, Vivaldi) install on a
desktop session and are skipped on a server or under WSL.

### Windows 11 + WSL2

Windows itself is set up with PowerShell, not `install.py`: follow the
phases in [windows/README.md](./windows/README.md) (winget, Scoop,
profiles, Claude Code, SSH and git signing, mise runtimes). That is a
complete Windows-native setup on its own.

To also get the Linux dotfiles, add WSL2 with Ubuntu on top:

1. On Windows, make sure `npiperelay` is installed (`scoop install
   npiperelay`; it is in `windows/scoopfile.json`) and enable
   **Settings → Developer → Use the SSH agent** and **Integrate with
   1Password CLI** in the 1Password app.
2. Run `wsl --install -d Ubuntu-24.04` and open the distro.
3. Inside WSL, run the common steps **on the Linux filesystem** (your WSL
   home, not `/mnt/c`).

Under WSL the installer skips the desktop topics, since the Windows host
owns the editor, browser, fonts and 1Password app, and instead bridges
the Windows 1Password SSH agent and `op.exe` into WSL. Details and
troubleshooting: [docs/WSL_UBUNTU_SETUP.md](./docs/WSL_UBUNTU_SETUP.md).

### Validating the repo

Run `mise run check` (or `python3 script/check.py`) to validate the
repo without touching your system — this is what CI runs on every push.
Prefer `mise run check`: it provisions ruff, shellcheck and actionlint
from `.mise.toml`'s `[tools]` section at exactly the versions CI uses.
The bare `check.py` entry point fails, rather than skipping, when those
tools are not on PATH.

`mise run ci` runs everything CI runs — `check` plus the zizmor
workflow audit — and `mise run ci-watch` follows the real run on GitHub.

## What Gets Installed

The installation script (`./script/install.py`) will:

1. **Bootstrap the package manager** — Homebrew plus `python@3` on macOS;
   the `base-devel`/`git`/`python` prerequisites plus `yay` on Arch; on
   Ubuntu the build prerequisites plus the vendor apt repositories for
   mise, GitHub CLI and 1Password, which Ubuntu's own archive lacks or
   ships stale
2. **Create `~/.dotfiles` symlink** pointing to this repository
3. **Set up XDG directories** (`~/.config`, `~/.local/share`, `~/.cache`, `~/.local/state`)
4. **Symlink dotfiles** to appropriate locations
5. **Run topic installers** for development tools, skipping any whose
   `platforms.txt` excludes the current platform:

| Topic | Installs |
|-------|----------|
| `1password/` | 1Password app and CLI (`op`). Under WSL: no app, but a systemd user service bridging the Windows app's SSH agent into `~/.1password/agent.sock`, and `op` running the Windows `op.exe` |
| `agents/` | Shared coding-agent instructions, links to the [lsimons-skills](https://github.com/lsimons/lsimons-skills) collection, and repository config sync |
| `ansible/` | Ansible and related tools |
| `aws/` | AWS CLI (`awscli`) + default `~/.aws/config`; `saml2aws` configured with the Browser provider for Okta OIE |
| `azure/` | Azure CLI (`az`) |
| `bash/` | Bash configuration and directories |
| `bash-it/` | Bash-it framework (prompt, plugins) |
| `claude/` | Claude Code CLI and configuration |
| `colors/` | `pastel` color CLI + docs for theme/palette files across tools |
| `codex/` | OpenAI Codex CLI and configuration |
| `copilot/` | GitHub Copilot CLI (git-config-ai routing) |
| `docker/` | Rancher Desktop on macOS; the docker engine, compose and buildx on Linux |
| `dock/` | Pins apps to the macOS Dock via dockutil (runs last). **macOS only** |
| `gemini/` | Gemini CLI |
| `fnox/` | fnox (1Password secret injection, via mise) |
| `fonts/` | Fonts (Cascadia Code, Iosevka, JetBrains Mono, Lilex, Lilex Nerd Font). **Desktop only** |
| `gh/` | GitHub CLI + extensions (`gh stack`) |
| `glab/` | GitLab CLI (`glab`) |
| `go/` | Go (via mise) |
| `ghostty/` | Ghostty terminal (no aarch64 Linux build — config only there) |
| `git/` | Git + credential helper (Git Credential Manager where packaged, else `gh auth git-credential`), git-filter-repo, Git LFS (installed and initialized) |
| `herdr/` | herdr terminal agent multiplexer + LSD Warm Light theme |
| `jdk/` | OpenJDK (via mise) |
| `jq/` | jq JSON processor (used by the Claude statusline) |
| `lsimons-agent/` | LLM agent environment configuration |
| `memex/` | memex agent-transcript search + its herdr plugin |
| `mise/` | mise (polyglot tool version manager) |
| `node/` | Node.js (via mise) + pnpm (via corepack) |
| `oh-my-zsh/` | Oh My Zsh + powerlevel10k |
| `omarchy/` | LSD Warm Dark/Light Omarchy themes, an extra Hyprland keybinding layer, Omarchy's default-app selection, and a per-machine foot font size. **Linux only** |
| `opencode/` | OpenCode CLI (permissions, model variants, LSD Warm theme, git-config-ai routing) |
| `openspec/` | openspec |
| `pi-coding-agent/` | pi-coding-agent (settings, LSD Warm themes, git-config-ai routing) |
| `python/` | Python (via mise) + XDG config |
| `quarto/` | Quarto (Homebrew cask; `quarto-cli-bin` from the AUR) |
| `ruby/` | Ruby (via mise) |
| `rust/` | Rust (via mise) + CARGO_HOME |
| `sh/` | Shared shell configuration (PATH, XDG, settings) |
| `ssh/` | SSH configuration (post-quantum warning, 1Password agent), and on Linux an `ssh-agent` systemd user unit holding the AI signing key |
| `sshd/` | OpenSSH server: `authorized_keys` from the machine config, keys-only login, port 22 in ufw. **Opt-in per machine** via `remoteAccess.sshd`; Linux only |
| `swiftdialog/` | swiftDialog (via Homebrew cask; skipped if already present, e.g. via MDM). **macOS only** |
| `tailscale/` | Tailscale (Homebrew cask on macOS, `tailscale` + `tailscaled` on Arch). Joining the tailnet stays manual |
| `terminal/` | macOS Terminal.app "LSD Warm Light" profile (mirrors Ghostty). **macOS only** |
| `terraform/` | tfenv and Terraform |
| `timeout/` | `timeout` command for macOS (via the `aisk/tap` Homebrew tap). **macOS only** — Linux coreutils already has it |
| `tmux/` | tmux |
| `topgrade/` | topgrade (automated updates) |
| `uv/` | uv (Python package manager) |
| `vivaldi/` | Vivaldi Browser (no aarch64 Linux build) |
| `wayvnc/` | wayvnc remote desktop for a Hyprland session, bound to the machine's Tailscale address, as a systemd user unit plus a tailnet-only ufw rule. **Opt-in per machine** via `remoteAccess.wayvnc`; Linux desktop only |
| `wordpress/` | WordPress shell environment |
| `zed/` | Zed editor (`zeditor` on Linux; no aarch64 build — config only there) |
| `zsh/` | ZSH itself (Arch has no zsh by default) and its directories |

## For AI Agents

If you're an AI coding agent (GitHub Copilot, Claude Code, etc.) working on this repository, please read [AGENTS.md](AGENTS.md) for detailed instructions and guidelines.

## Structure

```
.
├── script/           # Installation scripts and helpers
│   ├── install.py    # Main installer (supports --dry-run)
│   ├── check.py      # Validation checks (py_compile, ruff, shellcheck, actionlint, JSON, tests, install dry-run)
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
- `dependencies.txt` - Other topics that must install first, one per line
- `platforms.txt` - Platforms this topic supports, one per line: `macos`,
  `linux`, or `linux-desktop` for a Linux with a graphical session of its
  own (everything but WSL). Absent means every platform, which is the
  usual case

Loading order: shared and shell-specific `path.*` files first, ordinary shared
and shell-specific files second, then shared and shell-specific `completion.*`
files.

## Platform Support

| Platform | Installer | Packages from | Desktop topics | Notes |
|----------|-----------|---------------|----------------|-------|
| macOS | `install.py` | Homebrew (formulae and casks) | yes | Needs `brew install python` first; see [Quick Start](#macos) |
| Arch-based Linux | `install.py` | pacman, yay for the AUR | yes | [Omarchy](https://omarchy.org/) in practice; its config tree is what the `omarchy/` topic detects. Derivatives are recognised through `ID_LIKE` in `/etc/os-release`, so Arch Linux ARM counts too |
| Ubuntu / Debian | `install.py` | apt, mise for the rest | on a desktop session | Ubuntu's archive has no mise or 1Password CLI and a stale gh; the bootstrap adds the vendors' apt repositories for those |
| Ubuntu under WSL2 | `install.py` | apt, mise for the rest | no | The Windows host owns editor, browser, fonts and the 1Password app; the `1password/` topic bridges the Windows app's SSH agent and CLI into WSL. See [docs/WSL_UBUNTU_SETUP.md](./docs/WSL_UBUNTU_SETUP.md) |
| Windows 11 (native) | `windows/*.ps1` | winget, Scoop, mise | yes | Not handled by `install.py`. PowerShell bootstrap for the Windows host, x64 or ARM64; see [windows/README.md](./windows/README.md). Pair with WSL2 above for the Linux shell |

Topic installers should not branch on the platform themselves. Call
`ensure_package()` from `script/helpers.py` with a package name per
platform, and let it pick the manager:

```python
ensure_package("GitHub CLI", brew="gh", pacman="github-cli", apt="gh", command="gh")
ensure_package("topgrade", brew="topgrade", aur="topgrade", mise="topgrade",
               command="topgrade")
ensure_package("Ghostty", brew="ghostty", cask=True, pacman="ghostty",
               command="ghostty", optional=True)
```

`command=` (or `macos_app=`) is the presence probe. `apt=` is for what
Debian and Ubuntu package well; `mise=` names a tool in the mise
registry (or a `github:owner/repo` release) and is the fallback wherever
no native name is given, which on Ubuntu is most developer CLIs.
`optional=True` turns "no package for this platform" and "the install
failed" into warnings, which is how the topics for software with no
aarch64 Linux build — Ghostty, Zed, Vivaldi, Quarto — avoid failing the
whole run.

Work that is genuinely platform-shaped, rather than just a different
package name, is the exception and does test `IS_MACOS` / `IS_LINUX` /
`IS_WSL`: the mise GUI PATH hook (a LaunchAgent vs. a systemd
`environment.d` drop-in), the 1Password SSH agent socket and its WSL
bridge, and the docker engine.

A whole topic that only belongs on one platform says so in a
`platforms.txt` instead; a desktop topic lists `linux-desktop` rather
than `linux` so it stays off WSL. `script/install.py` skips the others
and drops any dependency on a skipped topic.

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

**Every machine must be enrolled before installing.** `machines/default.json` intentionally has no SSH keys and no git signing key, so `get_machine_config()` refuses to fall back to it for a hostname with no dedicated file — the installer exits with an error instead of silently generating a git config with commit signing enabled but no signing key, or a 1Password SSH agent config with no exposed keys. To enroll a new machine, create `machines/<hostname>.json` (use `hostname -s` to get the short hostname) before running the installer.

### Provider credentials (`providers`)

Some tools (currently the Codex and OpenCode shell wrappers, see
`codex/codex.sh` and `opencode/opencode.sh`) need an LLM provider API key
that lives in 1Password under a different account on different machines
— e.g. the SBP work account on a work laptop, a personal account
elsewhere. This is configured per machine under `providers`, mirroring
the shape of the existing `ssh.keys[].op_account`/`op_vault` fields:

```json
{
  "providers": {
    "litellm": {
      "op_account": "schubergphilis",
      "op_ref": "op://Employee/litellm-pat/token"
    }
  }
}
```

- `op_account` is passed to `op read --account`.
- `op_ref` is a full `op://vault/item/field` reference.
- Only a reference is stored here, never the secret itself.

Resolution happens at **call time**: `codex()`/`opencode()` invoke
`script/provider_credential.py <provider>`, which reads the CURRENT
machine's config (via `get_machine_config()`/`get_provider_credential()`
in `helpers.py`) and prints the account/reference for `op read` to
consume. A machine with no `providers.<provider>` entry configured fails
closed — the wrapper returns a non-zero exit and an explicit error
instead of falling back to another machine's account or reference.

### Remote access (`remoteAccess`)

Hosting SSH or a VNC desktop is opt-in per machine, since either opens a
port on whatever network the machine sits on:

```json
{
  "remoteAccess": {
    "allowFrom": "192.168.2.0/24",
    "sshd": true,
    "wayvnc": true
  }
}
```

- `sshd` runs the `sshd/` topic: OpenSSH server enabled, `authorized_keys`
  generated from this machine's `ssh.keys` entries with `auth: true`,
  and password/root login disabled once at least one key is present.
- `wayvnc` runs the `wayvnc/` topic: wayvnc as a systemd user unit that
  starts with the Hyprland session and listens on this machine's
  Tailscale IPv4 address only, plus 5900/tcp in ufw for the tailnet range
  (`100.64.0.0/10`). VNC auth is off; the tailnet is the access control,
  so connect from another tailnet device with a VNC viewer (TigerVNC or
  RealVNC on macOS — Apple's Screen Sharing does not get along with
  wayvnc). wayvnc encodes on the CPU and never touches GPU buffers, which
  is why it replaced Sunshine here.
- `allowFrom` scopes the `sshd` ufw rule to one CIDR, normally the home
  LAN. Omit it to allow from anywhere the firewall already permits. The
  `wayvnc` rule is always tailnet-only and ignores it.

Both hosts depend on the `tailscale/` topic, which installs Tailscale on
every machine but leaves `tailscale up` to the user.

### Omarchy desktop (`omarchy`)

Per-machine tweaks to Omarchy's stock desktop, applied by the `omarchy/`
topic:

```json
{
  "omarchy": {
    "terminalFontSize": 14
  }
}
```

- `terminalFontSize` sets the size on the `font=` line of Omarchy's own
  `~/.config/foot/foot.ini` (foot is Omarchy's default terminal). Only
  the size attribute changes; the family stays whatever Omarchy set. Note
  that `omarchy-font-set` rewrites that line back to size 9, so re-run
  the installer after changing the system font. Omit the key to leave
  foot's config untouched.

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

## Troubleshooting

### `ModuleNotFoundError: No module named 'tomllib'`

The installer needs Python 3.11 or newer, and macOS ships 3.9 in the
Command Line Tools. Install a newer Python and re-run:

```bash
brew install python              # macOS
sudo pacman -S python            # Arch
sudo apt-get install -y python3  # Debian/Ubuntu
./script/install.py
```

On a Mac with no Homebrew either, install Homebrew first (see
https://brew.sh). The installer does that itself normally, but it cannot
get that far on Python 3.9.

### A topic was skipped on Linux

Expected for `dock`, `terminal`, `swiftdialog` and `timeout`, and under
WSL also for `fonts`, `ghostty`, `omarchy`, `vivaldi` and `zed` — see
Platform Support above. The installer names every topic it skips and
why.

### Commit signing fails on Linux

Git signs through 1Password's `op-ssh-sign`, which needs the desktop app
running with the SSH agent enabled (Settings → Developer → Use the SSH
agent). `~/.ssh/config.agent`, generated by `ssh/install.py`, points ssh
at `~/.1password/agent.sock`.

Under WSL there is no `op-ssh-sign`; git signs with `ssh-keygen` through
the same socket, which the `1password-agent-bridge` systemd user service
provides from the Windows app. Check it with
`systemctl --user status 1password-agent-bridge` and
`SSH_AUTH_SOCK=~/.1password/agent.sock ssh-add -l`. It needs `npiperelay`
on the Windows side (`scoop install npiperelay`) and the SSH agent enabled
in the Windows 1Password app.

### AI commits fail to sign over SSH on Linux

The AI signing key is a passphrase-protected file, `~/.ssh/ai_ed25519`,
not a 1Password agent key, so it needs an ssh-agent. `ssh/install.py`
enables the `ssh-agent.socket` systemd user unit (or writes an equivalent
service where the distro ships none), and `ssh/ssh.sh` exports its
socket as `SSH_AUTH_SOCK` when nothing else has set one. Interactive
shells then load the key with the passphrase from 1Password. Over SSH
there is no desktop app to approve that read, so the shell prints a hint
and you load it by hand once per boot:

```bash
ssh-add ~/.ssh/ai_ed25519
```

Check with `ssh-add -l` and `systemctl --user status ssh-agent.socket`.

### XDG directories not created

Re-run installer:
```bash
~/.dotfiles/script/install.py
```

## Security

This is a personal project. Do not depend on it, and in particular do
not depend on its security. There is no support.

To report a vulnerability, use the "Report a vulnerability" button under
this repository's Security tab on GitHub.

## License

Apache License 2.0. See the [LICENSE](./LICENSE) file.

## Inspiration

- [holman/dotfiles](https://github.com/holman/dotfiles)
- [iheitlager/dotfiles](https://github.com/iheitlager/dotfiles)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/)
