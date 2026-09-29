# Agent Instructions for lsimons-dotfiles

> This file (`AGENTS.md`) is the canonical agent configuration. `CLAUDE.md` is a symlink to this file.

Personal dotfiles repository for macOS, Arch-based Linux ([Omarchy](https://omarchy.org/)) and Ubuntu (including WSL2). Topic-based structure inspired by [holman/dotfiles](https://github.com/holman/dotfiles).

## Quick Reference

- **Install**: `mise run install` (or `./script/install.py`) — needs Python 3.11+
- **Preview install**: `mise run install -- --dry-run`
- **Quality checks**: `mise run check` (or `python3 script/check.py`)
- **Workflow audit**: `mise run audit` (zizmor)
- **Everything CI runs locally**: `mise run ci` (= `check` + `audit`).
  CI additionally does a real Ubuntu smoke install (Debian bootstrap plus
  the `jq`, `tmux`, `zsh`, `mise` topics), which has no local equivalent
- **Watch CI**: `mise run ci-watch`
- **Test ZSH**: `zsh -c 'source ~/.zshrc && echo "Success"'`

`mise run install` installs the dotfiles onto **this machine**. It is not
a "fetch the project's dependencies" task, and must never run in CI.

### Git remote

Use GitHub with `gh`.

### Issue tracker

Use GitHub issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Use needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix.
See `docs/agents/issue-tracker.md`.

## Structure

Topics live in their own directories (`sh/`, `zsh/`, `bash/`, `python/`, `git/`, `1password/`, `script/`).

Machine-specific config lives in `machines/` as JSON files. Use `get_machine_config()` from `helpers.py` to load it.

**File naming:**
- `*.symlink` - Symlinked to home or XDG directories
- `*.sh` - Shared shell config (sourced by both bash and zsh)
- `*.zsh` - ZSH-specific config (sourced only by zsh)
- `*.bash` - Bash-specific config (sourced only by bash)
- `path.sh` / `path.zsh` / `path.bash` - Loaded first (PATH config)
- `completion.sh` / `completion.zsh` / `completion.bash` - Loaded last
- `install.py` - Topic installation script
- `dependencies.txt` - Topics that must install first, one per line
- `platforms.txt` - Platforms this topic supports: `macos`, `linux`, or
  `linux-desktop` for a Linux with its own graphical session (excludes
  WSL, where the Windows host owns the desktop). Absent means every
  platform

## Platforms

macOS, Arch-based Linux (Omarchy) and Debian-based Linux (Ubuntu, also
under WSL2). **Do not branch on the platform inside a topic installer.**
Use `ensure_package()` from `script/helpers.py`, which takes a package
name per platform:

```python
ensure_package("GitHub CLI", brew="gh", pacman="github-cli", apt="gh", command="gh")
ensure_package("topgrade", brew="topgrade", aur="topgrade", mise="topgrade", command="topgrade")
```

- `command=` / `macos_app=` are presence probes, checked before any
  package manager runs.
- `aur=` goes through yay; `pacman=` prefers a configured repo and falls
  back to yay. Omarchy ships an `[aur]` binary repo, so many nominally
  AUR packages resolve without a build.
- `apt=` is for what Debian/Ubuntu package well: git, zsh, tmux, jq,
  docker, ansible, fonts. Ubuntu's archive has no mise or 1Password CLI
  and a stale gh, so those three come from the vendors' apt repositories,
  which `script/install.py`'s bootstrap configures.
- `mise=` is the fallback for a platform with no native name; in practice
  that is Debian/Ubuntu for every other developer CLI (herdr, glab, uv,
  aws-cli, codex, ...). A `github:owner/repo` spec works for tools not in
  the mise registry. A topic that uses it lists `mise` in its
  `dependencies.txt`.
- `optional=True` downgrades "no package for this platform" and "install
  failed" to warnings. Use it for software with no aarch64 Linux build
  (Ghostty, Zed, Vivaldi, Quarto), not to paper over a real failure.

`IS_MACOS` / `IS_LINUX` / `IS_ARCH` / `IS_DEBIAN` / `IS_WSL` exist for
work that is genuinely platform-shaped rather than a renamed package —
LaunchAgents vs. systemd units, the 1Password agent socket, the Dock. A
topic that belongs on one platform entirely gets a `platforms.txt`
instead; a desktop topic (editor, browser, fonts, Omarchy theming) lists
`linux-desktop` rather than `linux` so it stays off WSL.

symlinks.txt lines may carry a `macos:` / `linux:` prefix when a config
file's destination differs per platform.

When touching `~/.config/hypr` or `~/.config/omarchy` on a Linux machine,
use the `omarchy` skill. The `omarchy/` topic only adds to Omarchy's own
config; it never replaces a stock file or writes to `/usr/share/omarchy`.

## Guidelines

**XDG compliance required.** Never create dotfiles in `$HOME` unless necessary for compatibility:
- `XDG_CONFIG_HOME` (~/.config) - Configuration
- `XDG_DATA_HOME` (~/.local/share) - Data
- `XDG_CACHE_HOME` (~/.cache) - Cache
- `XDG_STATE_HOME` (~/.local/state) - State/history

**Keep changes minimal.** Don't refactor working code. Focus on the specific task.

**Never commit secrets.** Use 1Password CLI with `op://vault/item/field` references.

**Installation scripts must be:**
- Idempotent
- Non-interactive
- Use `ensure_package()` for packages that aren't language runtimes
  (Homebrew on macOS, pacman/yay on Arch, apt or mise on Debian/Ubuntu)
- Use `mise use -g <tool>@<version>` for language runtimes and for tools
  that benefit from per-project version pinning (node, python, rust, go,
  ruby, jdk, fnox, etc.)
- For pnpm specifically: use `corepack enable pnpm` (mise's aqua backend
  for pnpm is broken — looks for `pnpm-macos-*` instead of `pnpm-darwin-*`)

## Adding a New Topic

Use the file naming conventions above. Update README.md to document it.

## Commit Message Convention

Follow [Conventional Commits](https://conventionalcommits.org/):

**Format:** `type(scope): description`

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `perf`, `revert`, `improvement`, `chore`

## Session Completion

Work is NOT complete until every change is committed, pushed, and CI passes.

1. **Quality gates** (if code changed):
   ```bash
   python3 script/check.py   # or: mise run check
   git diff                   # check for secrets
   ```

   `check.py` runs `py_compile`, `ruff`, `shellcheck`, `actionlint`,
   JSON validation, the unit tests, and `script/install.py --dry-run`
   (which exercises every topic installer without touching the system).
   It's what CI runs.

   ruff, shellcheck and actionlint are exact-pinned in `.mise.toml`'s
   `[tools]` section, so `mise run check` provisions them at the same
   versions CI uses. Running `python3 script/check.py` without them on
   PATH **fails** — it does not skip them.

   shellcheck covers `.sh`, `.bash` and `*.sh.symlink`. `.zsh` is out of
   scope because shellcheck has no zsh dialect. Most other `*.symlink`
   files are out of scope because they are not shell at all — they are
   JSON, TOML and ghostty config. The exceptions are `bashrc.symlink`
   and `bash_profile.symlink`, which source topic files through a
   computed path and so are SC1090/SC1091 by construction.

2. **Commit**: stage and commit every change from this session. Do not leave the working tree dirty.
   ```bash
   git status              # review untracked and unstaged files
   git add <files>
   git commit -m "<type>(<scope>): <description>"
   ```

3. **Push**:
   ```bash
   git pull --rebase && git push
   git status  # must show "up to date with origin"
   ```

4. **Verify CI**:
   ```bash
   mise run ci-watch
   ```
   On failure, inspect with `gh run view --log-failed`, fix, commit, push, and re-watch.

Never stop before CI is green. If anything fails, resolve and retry.
