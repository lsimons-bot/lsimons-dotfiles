# Agent Instructions for lsimons-dotfiles

> This file (`AGENTS.md`) is the canonical agent configuration. `CLAUDE.md` is a symlink to this file.

Personal dotfiles repository for macOS. Topic-based structure inspired by [holman/dotfiles](https://github.com/holman/dotfiles).

## Quick Reference

- **Install**: `./script/install.py`
- **Preview install**: `./script/install.py --dry-run`
- **Quality checks**: `python3 script/check.py` (or `mise run check`)
- **Test ZSH**: `zsh -c 'source ~/.zshrc && echo "Success"'`

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
- Use Homebrew for packages that aren't language runtimes
- Use `mise use -g <tool>@<version>` for language runtimes and for tools
  that benefit from per-project version pinning (node, python, rust, go,
  ruby, jdk, pnpm, fnox, etc.)

## Adding a New Topic

```
newtopic/
├── newtopic.sh           # Shared shell config (auto-loaded by bash and zsh)
├── newtopic.zsh          # ZSH-specific config (optional)
├── newtopic.bash         # Bash-specific config (optional)
├── newtopicrc.symlink    # Config to symlink
└── install.py            # Optional installer
```

Update README.md to document it.

## Commit Message Convention

Follow [Conventional Commits](https://conventionalcommits.org/):

**Format:** `type(scope): description`

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `perf`, `revert`, `improvement`, `chore`

## Session Completion

Work is NOT complete until `git push` succeeds.

1. **Quality gates** (if code changed):
   ```bash
   python3 script/check.py   # or: mise run check
   git diff                   # check for secrets
   ```

   `check.py` runs `py_compile`, `ruff`, JSON validation, and
   `script/install.py --dry-run` (which exercises every topic
   installer without touching the system). It's what CI runs.

   ruff is provisioned via `.mise.toml`'s `[tools]` section, so
   `mise run check` auto-installs it. Running `python3 script/check.py`
   directly without mise/ruff on PATH skips ruff with a warning.

2. **Push**:
   ```bash
   git pull --rebase && git push
   git status  # must show "up to date with origin"
   ```

Never stop before pushing. If push fails, resolve and retry.
