# WSL2 + Ubuntu setup

How these dotfiles install inside **WSL2 Ubuntu 24.04** on a Windows 11 host
that was itself set up with [`windows/`](../windows/README.md). Ubuntu rather
than Arch because it is the most common WSL distro among colleagues at work.
Two uses drive it:

1. Run Claude Code with `/sandbox` (bubblewrap). Windows-native `claude.exe`
   cannot sandbox. Both `/sandbox` and
   [claude-docker](https://github.com/schubergphilis/claude-docker) are
   endorsed at work; teams pick either.
2. Carry the macOS/Linux dotfiles config over to WSL, so the WSL shell feels
   like the Mac.

Arch/Omarchy stays the first-class Linux desktop target. WSL means Ubuntu on
WSL only; there is no Omarchy-on-WSL variant.

## Windows side

Do the [`windows/`](../windows/README.md) phases first (as yourself, not the
bot: see "Personal machine variant" there). Beyond those, the Linux side
needs two things from Windows:

- **`npiperelay`**, from the scoop extras bucket. It is in `scoopfile.json`;
  on an existing machine `scoop install npiperelay` is enough.
- **The 1Password app's SSH agent and CLI integration enabled**: Settings →
  Developer → "Use the SSH agent" and "Integrate with 1Password CLI".

Then `wsl --install -d Ubuntu-24.04`. Ubuntu 24.04 runs systemd inside WSL
by default (`/etc/wsl.conf`, `[boot] systemd=true`); the agent bridge below
depends on that.

## Linux side

```bash
mkdir -p ~/git/lsimons && cd ~/git/lsimons        # on the Linux filesystem, not /mnt/c
git clone https://github.com/lsimons/lsimons-dotfiles.git
cd lsimons-dotfiles
hostname -s                                        # enroll: create machines/<this>.json
./script/install.py --dry-run
./script/install.py
```

Ubuntu 24.04's `python3` (3.12) clears the installer's version guard, so no
newer interpreter is needed. `sudo` asks for your password once for apt.

The installer detects Ubuntu through `ID`/`ID_LIKE` in `/etc/os-release`
(`IS_DEBIAN`) and WSL through `WSL_DISTRO_NAME` or the Microsoft kernel in
`/proc/version` (`IS_WSL`), and then differs from a Linux desktop in these
ways:

- **Bootstrap** installs `build-essential git curl ca-certificates gnupg
  python3` and adds the vendor apt repositories for **mise**, **GitHub CLI**
  and **1Password** (keyrings under `/etc/apt/keyrings`, 1Password's debsig
  policy included), because Ubuntu's archive has no mise or 1Password CLI
  and a stale gh. A mise repo already enabled through `extrepo enable mise`
  is recognised and left alone.
- **Packages**: `apt` for what Ubuntu packages well (git, git-lfs,
  git-filter-repo, zsh, tmux, jq, python3, ansible, docker.io and its
  compose/buildx plugins, a few fonts); **mise** (`mise use -g`) for the
  other developer CLIs (herdr, glab, pastel, uv, aws-cli, saml2aws,
  azure-cli, codex, copilot, opencode, topgrade, tfenv, memex via
  `github:nicosuave/memex`). powerlevel10k has no Ubuntu package and is
  cloned from upstream into `$XDG_DATA_HOME/powerlevel10k`.
- **Desktop topics are skipped**: `fonts`, `ghostty`, `omarchy`, `vivaldi`,
  `zed` declare `linux-desktop` in `platforms.txt`, which a WSL host does
  not satisfy. The Windows host owns the desktop.
- **1Password**: no Linux app and no `agent.toml`. Instead the `1password`
  topic installs
  - a systemd user service, `1password-agent-bridge`, running socat and
    `npiperelay.exe` to expose the Windows app's SSH agent (named pipe
    `\\.\pipe\openssh-ssh-agent`) at `~/.1password/agent.sock`, the same
    path the Linux app would use, so `~/.ssh/config.agent` is unchanged;
  - `~/.local/bin/op`, a wrapper around the Windows `op.exe`, the only CLI
    that can use the Windows app's biometric unlock. Without `op.exe` the
    Linux CLI is installed from the 1Password repo instead.
- **Git signing**: `op-ssh-sign` only ships with the desktop app, so
  `gpg.ssh.program` is `~/.config/dotfiles/ssh-sign-1password-bridge.sh`,
  which runs `ssh-keygen` against the bridged agent. `user.signingkey` is
  the public key, which is what makes ssh-keygen ask the agent.
- **Git credentials**: `credential.helper` is `!gh auth git-credential`
  everywhere, with `!glab auth git-credential` scoped to the GitLab hosts
  in machine config. HTTPS fetches and pushes use the tokens from `gh auth
  login` and `glab auth login`. Ubuntu has no Git Credential Manager
  package, so Azure DevOps remotes fall through to git's own prompt.
- **Docker**: `docker.io` from Ubuntu runs the daemon natively under WSL2
  with systemd. Docker Engine, the CLI, compose and buildx are Apache 2.0;
  only Docker Desktop is licensed, and it is not needed. Podman
  (`apt install podman`) is the alternative if a team standardises on it.

### Verify

```bash
systemctl --user status 1password-agent-bridge --no-pager
SSH_AUTH_SOCK=~/.1password/agent.sock ssh-add -l      # lists the 1Password keys
op whoami                                             # via op.exe, with a Windows Hello prompt
ssh -T git@github.com
git commit --allow-empty -m "test: signing" && git log -1 --show-signature && git reset --hard HEAD~1
```

Each `op` and signing call raises a 1Password prompt on the Windows side;
that is the biometric unlock working.

## Claude Code

Install with the native installer (`~/.local/bin/claude`) and log in.
`/sandbox` needs `bwrap` and `socat` (`apt install bubblewrap socat`); the
dotfiles install socat anyway for the agent bridge. Inside the sandbox,
`systemctl --user` cannot reach the user bus and Windows executables cannot
be run (no interop socket), so check the bridge from a normal shell.

## Troubleshooting

- **`Failed to configure the mise apt repository: HTTP Error 403`**:
  mise.jdx.dev rejects Python's default `Python-urllib` user agent. The
  bootstrap sends its own; if you see this, the repo is older than that fix.
- **`fatal: cannot exec '/opt/1Password/op-ssh-sign'`** on commit: the `git`
  topic ran before the `ssh` topic wrote the signing helper, or the machine
  was not detected as WSL. Re-run `python3 git/install.py`.
- **`git: 'credential-manager' is not a git command`** on push, or a
  username prompt for github.com or gitlab.com: the config predates the
  CLI helpers, or the CLI is not logged in. Re-run `python3 git/install.py`,
  then `gh auth login` or `glab auth login`.
- **`ssh-add -l` says `Error connecting to agent`**: the bridge is down.
  `systemctl --user status 1password-agent-bridge`; check that
  `npiperelay.exe` exists (`scoop install npiperelay`) and that the SSH
  agent is enabled in the Windows 1Password app. `journalctl --user -u
  1password-agent-bridge` has socat's messages.
- **A WSL session started without the Windows PATH** (cron, sudo): the
  bridge and the `op` wrapper use absolute `/mnt/c/...` paths recorded at
  install time, so they do not depend on it.

## CI

`.github/workflows/ci.yml` runs `mise run check` (dry-run of every topic)
and an `install-smoke` job that runs the Debian bootstrap and the `jq`,
`tmux`, `zsh` and `mise` topics for real on the Ubuntu runner, then checks
the bootstrap is idempotent.
