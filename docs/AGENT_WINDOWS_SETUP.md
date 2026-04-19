# Setting Up a Sandboxed Windows VM for Agentic Coding

A Windows 11 ARM64 companion to [AGENT_SETUP.md](./AGENT_SETUP.md). Same goals (network control, isolation, scoped credentials, damage limitation); different OS.

Read [AGENT_SETUP.md](./AGENT_SETUP.md) first — this doc only covers what's different on Windows.

![](./ai-win-vm-green-goodness.png)

## Why a Windows sandbox?

Testing dotfiles, the AI harness, and developer-environment tooling against a clean, Windows-native setup. Useful for:

- Validating that Claude Code, Zed, and other tools actually work on Windows (without a WSL2 crutch)
- Exercising the winget + Scoop + PowerShell path rather than Homebrew + zsh
- Catching Windows-only path/line-ending/case-sensitivity bugs before users hit them

## Hard constraint: no WSL2, no containers

On Apple Silicon **M1 and M2**, macOS's Hypervisor.framework does not expose nested virtualization at all. On **M3+**, nested virt is exposed *only for Linux guests via the Apple Virtualization backend* — Windows guests still don't get it.

Practical consequences inside a UTM-hosted Windows 11 ARM VM:

| Thing | Status |
|---|---|
| WSL2 | **Broken** (`WslRegisterDistribution 0x80370102`). WSL1 only. |
| Docker Desktop | **Broken** (needs WSL2 backend) |
| Podman / Rancher Desktop | **Broken** (same reason) |
| Hyper-V / Windows Sandbox | **Broken** |
| Native Windows ARM64 dev tools | **Fine** |
| x64 Windows apps via Prism emulation | **Fine**, ~10-15% overhead |

So this VM is native-Windows-only by force, not by choice. If you need containers, run a separate Linux UTM VM alongside.

## Stack

Picked for: native ARM64 availability, declarative scripting, mirrors macOS dotfiles philosophy where possible.

| Layer | Choice | Why not X |
|---|---|---|
| Package mgr (GUI/MSI) | **winget** + `winget configure` YAML | Best ARM64 support; Microsoft-invested; declarative like a Brewfile |
| Package mgr (CLI) | **Scoop** | Closest to Homebrew philosophy — user-space, no UAC, shims, buckets ≈ taps |
| Shell | **PowerShell 7 (`pwsh`)** | Native ARM64, object pipeline, the realistic default. Git Bash is legacy. |
| Terminal | **Windows Terminal** | Ghostty has no official Windows build in 2026. WT is actively maintained and GPU-accelerated. |
| Editor | **Zed** | Official stable Windows builds ship in 2026. Keeps parity with macOS. |
| Browser | **Vivaldi** | Same as macOS. |
| Firewall | **Simplewall** (alert mode) | Little Snitch has no Windows build. Simplewall is the closest interactive filter. |
| Security audit | **Pareto Security** | Cross-platform; same as macOS. |
| Agent | **Claude Code** (native Windows, via `irm` installer) | No WSL2 required as of 2026; Git for Windows is the only prereq. |
| Secrets | **1Password + op CLI** | Same as macOS. SSH agent works via named pipe on Windows. |

Explicitly rejected:

- **Chocolatey**: declining share; no ARM64 architecture awareness.
- **Boxstarter**: its killer feature (reboot-resume across SQL Server / full Visual Studio installs) doesn't apply to this stack. `winget configure` covers the declarative need.
- **chezmoi**: worth learning eventually, but another substrate on top of an already-new (for the user) platform.
- **Ghostty**: no official Windows build in 2026.
- **WSL2 / Docker / Podman**: physically unavailable (see constraint above).

## Prerequisites

- An Apple Silicon Mac with enough resources (8GB+ RAM for the VM)
- UTM 4.7+
- A Windows 11 ARM64 installation ISO and a valid licence
- A separate bot GitHub and 1Password account (see [AGENT_SETUP.md § Setting up an agent profile](./AGENT_SETUP.md#setting-up-an-agent-profile))

## Setting up the VM

### 1. Create the UTM Virtual Machine

1. Create a new **Windows ARM64** VM in UTM (generous CPU/RAM)
2. Attach the Windows 11 ARM installation ISO
3. Install Windows 11 Home (or Pro)
4. During OOBE: **use a local account**, not a Microsoft account
5. Apply all pending Windows Updates before running the bootstrap

### 2. Basic Windows tuning (before bootstrap)

Done manually, once, so the bootstrap has a clean substrate:

- Install Vivaldi (or any browser) to bootstrap from
- Verify `winget` works: `winget --version`
- Verify `pwsh` is installable: the bootstrap installs PowerShell 7, but the first run uses Windows PowerShell 5.1

### 3. Run bootstrap-phase1 (unattended)

See [windows/README.md](../windows/README.md) for the one-liner.

Phase 1 does, in order:

1. Enables `winget configure`
2. Runs `winget configure --file packages.winget.yaml` — installs Git for Windows, GitHub CLI, 1Password + CLI, PowerShell 7, Windows Terminal, Zed, Pareto Security, Simplewall, and Vivaldi
3. Installs Scoop (user-space, non-elevated)
4. Runs `scoop import scoopfile.json` — installs the CLI toolchain (ripgrep, fzf, fd, bat, jq, yq, eza, zoxide, just, lazygit, delta, starship, mise)
5. Applies registry tweaks: dark mode, show hidden files, show file extensions, disable animations, distinct accent color (so you always know you're in the sandbox)
6. Sets the wallpaper to a sandbox-distinct image
7. Symlinks the PowerShell profile and Windows Terminal settings into the right places
8. Installs Claude Code via `irm https://claude.ai/install.ps1 | iex`

Phase 1 is fully unattended. No signed-in accounts required yet.

### 4. Manual interactive steps (between phases)

Can't be automated by design:

- **1Password**: sign in (Secret Key + passkey/biometric), connect the browser extension, enable the desktop app, enable the SSH agent
- **GitHub**: `gh auth login` (OAuth browser flow)
- **Vivaldi**: sign in to the bot account, enable sync
- **Claude Code**: run `claude` and use `/login` for the browser OAuth flow
- **Pareto Security**: run checks, remediate until green
- **Simplewall**: enable filtering, start in alert mode

### 5. Run bootstrap-phase2 (needs 1Password signed in)

Phase 2 pulls secrets via `op read`:

1. Writes bot SSH public key from 1Password
2. Configures Git to sign commits using the 1Password SSH agent (`ssh.exe` over the Windows named pipe)
3. Sets git user identity (name / email / signingkey) from `machines/<hostname>.json` if present
4. Clones bot repos into `~/git/`

### 6. Switch Simplewall to alert mode

The key security control. Every new outbound connection prompts for approve/deny. Same discipline as Little Snitch on macOS.

## Key differences from macOS setup

| Concern | macOS | Windows |
|---|---|---|
| Package install | `brew install` | `winget` for GUI, `scoop` for CLI |
| Declarative manifest | shell loops in `install.py` | `packages.winget.yaml` + `scoopfile.json` |
| Network firewall | Little Snitch | Simplewall (rougher UX, similar model) |
| SSH agent | 1Password socket | 1Password named pipe, `SSH_AUTH_SOCK` env or `ssh.exe` config |
| Shell | zsh | pwsh 7 |
| XDG dirs | real | emulated via env vars pointing at `$env:LOCALAPPDATA` subfolders |
| Symlinks | `ln -s` works | `New-Item -ItemType SymbolicLink` — needs Developer Mode or admin |

## References

- [AGENT_SETUP.md](./AGENT_SETUP.md) — macOS companion
- [UTM - Virtual machines for Mac](https://mac.getutm.app/)
- [Simplewall](https://www.henrypp.org/product/simplewall)
- [Pareto Security](https://paretosecurity.com/mac) (Windows build on the same page)
- [WinGet Configuration](https://learn.microsoft.com/en-us/windows/package-manager/configuration/)
- [Scoop](https://scoop.sh)
- [Claude Code on Windows](https://code.claude.com/docs/en/quickstart)
- [Windows on ARM app compatibility](https://learn.microsoft.com/en-us/windows/arm/)
