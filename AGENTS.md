# Agent Instructions for lsimons-dotfiles

Personal dotfiles repository for macOS. Topic-based structure inspired by [holman/dotfiles](https://github.com/holman/dotfiles).

## Quick Reference

- **Install**: `./script/install.py`
- **Test ZSH**: `zsh -c 'source ~/.zshrc && echo "Success"'`

## Structure

Topics live in their own directories (`zsh/`, `python/`, `git/`, `1password/`, `script/`).

Machine-specific config lives in `machines/` as JSON files. Use `get_machine_config()` from `helpers.py` to load it.

**File naming:**
- `*.symlink` - Symlinked to home or XDG directories
- `*.zsh` - Auto-sourced ZSH config
- `path.zsh` - Loaded first (PATH config)
- `completion.zsh` - Loaded last
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
- Use Homebrew for packages

## Adding a New Topic

```
newtopic/
├── newtopic.zsh          # Shell config (auto-loaded)
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
   ./script/install.py
   python3 -m py_compile script/install.py
   git diff  # check for secrets
   ```

2. **Push**:
   ```bash
   git pull --rebase && git push
   git status  # must show "up to date with origin"
   ```

Never stop before pushing. If push fails, resolve and retry.
