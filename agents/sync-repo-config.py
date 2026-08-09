#!/usr/bin/env python3
"""Generate per-repository coding-agent config from mise tasks and overrides.

For each directory given on the command line (or, if none, every sibling of
the repositories root that has a .mise.toml or Claude override), write:

* .claude/settings.json permissions for each mise task plus Claude overrides
* .codex/rules/mise.rules prefix rules for each mise task
* .opencode/opencode.json permissions for each mise task

Claude overrides live in overrides/claude/<repo-name>.json. Their
allow/deny/ask lists are merged with generated permissions and deduplicated.

The goal is to whitelist the specific task-runner invocations that exist in
each repo today, instead of blanket-approving `mise run` / `mise tasks run`.

Ownership of each generated path is "regenerate always, never destroy
without a backup": there is no ownership marker and no merge with
hand-edited content. Before writing or removing a generated path, anything
already there (a file or a symlink) is backed up via this repo's existing
`helpers.backup_file` convention. See `write_generated` for details.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import backup_file, is_dry_run, set_dry_run


def parse_tasks(mise_toml: Path) -> list[str]:
    """Return the list of task names declared in a .mise.toml file."""
    with open(mise_toml, "rb") as f:
        config = tomllib.load(f)
    return list(config.get("tasks", {}))


def dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_claude_settings(tasks: list[str], override: dict | None) -> dict:
    allow = [f"Bash(mise run {t})" for t in tasks] + [
        f"Bash(mise run {t} *)" for t in tasks
    ]
    deny: list[str] = []
    ask: list[str] = []
    if override:
        perms = override.get("permissions", {})
        allow += list(perms.get("allow", []))
        deny += list(perms.get("deny", []))
        ask += list(perms.get("ask", []))

    perms_out: dict[str, list[str]] = {}
    if allow:
        perms_out["allow"] = dedupe(allow)
    if deny:
        perms_out["deny"] = dedupe(deny)
    if ask:
        perms_out["ask"] = dedupe(ask)
    return {"permissions": perms_out}


def build_codex_rules(tasks: list[str]) -> str:
    """Return Codex prefix rules for the given mise task names."""
    lines = [
        'prefix_rule(pattern = ["mise", "run", '
        f'{json.dumps(task)}], decision = "allow")'
        for task in tasks
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def build_opencode_config(tasks: list[str]) -> dict:
    """Return OpenCode bash permissions for the given mise task names."""
    bash = {
        command: "allow"
        for task in tasks
        for command in (f"mise run {task}", f"mise run {task} *")
    }
    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": {"bash": bash},
    }


DOTFILES_REPO = Path(__file__).resolve().parents[1]


def write_generated(target: Path, rendered: str) -> None:
    """Write or remove one generated config file.

    This is "regenerate always, never destroy without a backup": there is no
    ownership marker and no attempt to merge unmanaged content. Instead,
    anything already at `target` — a hand-maintained file *or* a symlink —
    is backed up first, using this repo's existing backup convention
    (`helpers.backup_file`, which moves it under
    `~/.dotfiles-backup/<timestamp>/...`, preserving its relative location
    and never clobbering a previous run's backup).

    A symlink at `target` is always backed up and replaced with a plain
    file, even if the generated content happens to match what it currently
    resolves to — we never write through an existing symlink, since that
    could silently redirect the write outside this repo. A regular file is
    only backed up when its content actually differs from what would be
    generated.

    When there is nothing to generate, any existing file or symlink is
    backed up and then removed, rather than being deleted outright.

    Dry-run mode is read from `helpers.is_dry_run()` (set once, in `main`,
    via `helpers.set_dry_run`) rather than a separate parameter here, so
    there is a single source of truth: `backup_file` reports what it would
    back up and this function reports what it would write or remove,
    without touching the filesystem.
    """
    dry_run = is_dry_run()
    is_symlink = target.is_symlink()
    exists = is_symlink or target.exists()

    if not rendered:
        if exists:
            backup_file(target)
            print(f"{'would remove' if dry_run else 'removed'}:   {target}")
        return

    if exists and not is_symlink:
        existing = target.read_text()
        if existing == rendered:
            print(f"unchanged: {target}")
            return

    if exists:
        backup_file(target)

    if dry_run:
        print(f"--- {target} ---")
        print(rendered, end="")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered)
    print(f"wrote:     {target}")


def sync_repo(repo: Path, claude_overrides_dir: Path) -> bool:
    # This repository maintains its native agent config by hand.
    if repo.resolve() == DOTFILES_REPO:
        return False

    mise_toml = repo / ".mise.toml"
    override_file = claude_overrides_dir / f"{repo.name}.json"

    if not mise_toml.exists() and not override_file.exists():
        return False

    tasks = parse_tasks(mise_toml) if mise_toml.exists() else []
    override = json.loads(override_file.read_text()) if override_file.exists() else None

    claude_settings = build_claude_settings(tasks, override)
    claude_rendered = (
        json.dumps(claude_settings, indent=2) + "\n"
        if claude_settings["permissions"]
        else ""
    )
    write_generated(repo / ".claude" / "settings.json", claude_rendered)
    write_generated(
        repo / ".codex" / "rules" / "mise.rules",
        build_codex_rules(tasks),
    )
    opencode_rendered = (
        json.dumps(build_opencode_config(tasks), indent=2) + "\n" if tasks else ""
    )
    write_generated(
        repo / ".opencode" / "opencode.json",
        opencode_rendered,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repos-dir",
        type=Path,
        default=Path.home() / "git" / "lsimons",
        help="Directory containing sibling repos (default: ~/git/lsimons)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without changing any files",
    )
    parser.add_argument(
        "repos",
        nargs="*",
        type=Path,
        help=(
            "Specific repo paths to sync; default is every sibling with a "
            ".mise.toml or override"
        ),
    )
    args = parser.parse_args()
    set_dry_run(args.dry_run)

    claude_overrides_dir = Path(__file__).resolve().parent / "overrides" / "claude"

    if args.repos:
        candidates = [p.resolve() for p in args.repos]
    else:
        if not args.repos_dir.is_dir():
            print(f"No such directory: {args.repos_dir}", file=sys.stderr)
            return 1
        candidates = sorted(p for p in args.repos_dir.iterdir() if p.is_dir())

    touched = 0
    for repo in candidates:
        if sync_repo(repo, claude_overrides_dir):
            touched += 1

    if touched == 0:
        print("No repositories had a .mise.toml or matching override.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
