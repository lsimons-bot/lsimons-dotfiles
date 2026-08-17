# Coding agents

This directory is the shared source of truth for coding-agent configuration:

- `AGENTS.md` contains global instructions.
- `shared.py` owns shared paths, attribution policy, and instruction rendering.
  Every agent — Claude Code included — gets the same rendered instructions with
  the literal `Co-Authored-By` line, rather than a harness-native attribution
  setting, so there is one place that decides what a trailer looks like. Claude
  Code's own `attribution` setting is explicitly set to empty strings to switch
  its built-in trailer off; omitting the key restores the default trailer
  instead of removing it.
- `install.py` links the skills collection into the shared skill locations.
- `overrides/<agent>/` contains agent-specific per-repository additions.
- `sync-repo-config.py` generates native per-repository configuration from
  tasks declared in `.mise.toml`.

## Skills

Skills are **not** maintained here. The single source of truth is the
[`lsimons-skills`](https://github.com/lsimons/lsimons-skills) repository,
which vendors the full collection in its `skills/` directory. It is expected
to be checked out next to this repository, at `../lsimons-skills`.

Everything in this repository only links to that directory. The `claude`,
`codex`, `copilot`, `gemini` and `opencode` topics link it to their
agent-specific global skills directory, `pi-coding-agent` points its config at
it, and `install.py` links it to `~/.agents/skills` and
`$XDG_CONFIG_HOME/agents/skills` so agents without a dedicated topic (Zed,
Cursor, Cline, Warp, Amp, ...) pick up the same set.

Add, update or remove skills in `lsimons-skills`; nothing here needs to
change. `install.py` warns and exits non-zero if the checkout is missing.

The one exception is `sbp-brandbook`, which is not open source and so isn't
part of `lsimons-skills`. It lives in the private
[`sbp-skills`](https://github.com/lsimons/sbp-skills) checkout instead,
expected at `../sbp-skills`, and `install.py` symlinks it into
`lsimons-skills/skills/sbp-brandbook` so it still reaches every agent through
the same shared mechanism.

The `vercel-agent-browser` skill is only a discovery stub, so the installer
also installs the `agent-browser` CLI and its Chrome build (~180 MB,
downloaded once).

## Sandbox trust model

The generated Claude/Codex configs grant sandboxed agent processes
broad host access: read of the private SSH signing key and unrestricted
Unix-domain socket access. This is deliberate, not a gap — see
[`docs/AGENT_SANDBOX_TRUST_MODEL.md`](../docs/AGENT_SANDBOX_TRUST_MODEL.md)
for the reasoning and accepted risk on each.

Preview configuration for every repository under `~/git/lsimons`:

```sh
python3 agents/sync-repo-config.py --dry-run
```

Pass repository paths to sync only those repositories. The generated files are
`.claude/settings.json`, `.codex/rules/mise.rules`, and
`.opencode/opencode.json`.

These paths are fully generated: there is no ownership marker and no merge
with hand-edited content, so every run regenerates them from scratch. To
avoid destroying anything irrecoverably, whatever already exists at a
generated path — a hand-edited file *or* a symlink — is backed up first,
using this repo's usual backup convention (`helpers.backup_file`, under
`~/.dotfiles-backup/<timestamp>/...`). A symlink is always backed up and
replaced with a plain file, since writing through it could otherwise land
outside the target repo. When there's nothing to generate for a path, the
existing file/symlink is backed up and then removed rather than deleted
outright. `--dry-run` reports what would be backed up and written/removed
without changing anything.
