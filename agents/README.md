# Coding agents

This directory is the shared source of truth for coding-agent configuration:

- `AGENTS.md` contains global instructions.
- `shared.py` owns shared paths, attribution policy, and instruction rendering.
- `skills/` contains skills linked into each supported agent's config directory.
- `skills.txt` declares the skills fetched from [skills.sh](https://www.skills.sh).
- `install.py` installs the skills.sh CLI and everything in `skills.txt`.
- `overrides/<agent>/` contains agent-specific per-repository additions.
- `sync-repo-config.py` generates native per-repository configuration from
  tasks declared in `.mise.toml`.

## Skills

`skills/` is the single source of truth for skills. The `claude`, `codex`,
`copilot`, `gemini` and `opencode` topics link it to their agent-specific
global skills directory, `pi-coding-agent` points its config at it, and
`install.py` links it to `~/.agents/skills` and `$XDG_CONFIG_HOME/agents/skills`
so agents without a dedicated topic (Zed, Cursor, Cline, Warp, Amp, ...) pick
up the same set.

`1password/` and `python-knowledge-patch/` are maintained here. Everything
listed in `skills.txt` is fetched with the skills.sh CLI instead of being
vendored, so those directories are gitignored — `install.py` regenerates
`skills/.gitignore` from the manifest.

Add a skill by appending `<repository-url> <skill-name>` to `skills.txt` and
running the installer:

```sh
python3 agents/install.py            # install anything missing
mise run skills-update               # re-fetch everything (also run by topgrade)
```

Browse and search the catalog with the CLI (`skills find`, `skills list`); the
`find-skills` skill lets agents do that on their own.

The `agent-browser` skill is only a discovery stub, so the installer also
installs the `agent-browser` CLI and its Chrome build (~180 MB, downloaded
once).

Preview configuration for every repository under `~/git/lsimons`:

```sh
python3 agents/sync-repo-config.py --dry-run
```

Pass repository paths to sync only those repositories. The generated files are
`.claude/settings.json`, `.codex/rules/mise.rules`, and
`.opencode/opencode.json`.
