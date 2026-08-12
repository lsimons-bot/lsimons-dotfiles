#!/usr/bin/env python3
"""Statistics on Claude Code auto-mode permission decisions.

Reads ~/.claude/projects/*/*.jsonl transcripts and reports:
  - tool-call volume per permission mode
  - denials by kind (auto mode classifier / static permission rule / user)
  - classifier reason categories, and which config the reason cited
    (central settings deny rules, per-project settings, CLAUDE.md)
  - what the model did after a denial: literal retry, variant attempt
    (a "work-around"), or stop-and-ask
  - the extra work each denial caused: assistant turns, output tokens, and
    whether the user had to step in with another prompt

Important limitation: transcripts record only *denials*. Auto-mode approvals
are silent -- there is no per-call record saying "classifier approved", and
no way to tell a classifier approval apart from a static allow-rule match or
a call that needed no permission at all. "Approved" below therefore means
"tool call in auto mode that was not denied", i.e. an upper bound.

Usage:
  python3 claude/permission_stats.py [--since YYYY-MM-DD] [--details N]
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import fnmatch
import glob
import json
import os
import re
import shlex

PROJECTS = os.path.expanduser("~/.claude/projects")

DENY_KIND_LABEL = {
    "automode-blocked": "auto mode classifier denied",
    "permission-rule": "static permission rule denied",
    "user-rejected": "user rejected (interactive)",
    "automode-unavailable": "auto mode classifier unavailable",
}

CLASSIFIER_MARKER = "denied by the Claude Code auto mode classifier"
# The reason runs from "Reason:" up to the boilerplate that follows it. Do not
# stop at the first "..", since reasons quote commands containing dots.
REASON_RE = re.compile(
    r"Reason:\s*(?:\[(?P<cat>[^\]]+)\]\s*)?(?P<reason>.*?)"
    r"(?:If you have other tasks that don't depend|IMPORTANT: You \*may\*|$)", re.DOTALL)

# What the classifier reason cited as the basis for the denial.
CITATION_PATTERNS = {
    "explicit deny rule in settings": re.compile(
        r"deny rule|deny list|denyRule|explicitly (?:configured|denied)|standing permission deny", re.IGNORECASE),
    "user permission settings (generic)": re.compile(
        r"permission (?:rule|settings|config)|settings\.json|\.claude/settings", re.IGNORECASE),
    "CLAUDE.md / user instructions": re.compile(
        r"CLAUDE\.md|user's (?:global |private )?instructions|stated preference", re.IGNORECASE),
    "project-local config": re.compile(r"project(?:-| )(?:local|level|specific) (?:settings|rule|config)", re.IGNORECASE),
}

# User prompts that are actually machine-injected, not the human typing.
SYNTHETIC_PROMPT_RE = re.compile(
    r"^\s*(<(?:system-reminder|command-name|command-message|local-command|teammate-message|user-prompt-submit)|"
    r"Another Claude session|Caveat: The messages below|\[Request interrupted)", re.DOTALL)

PERMISSION_HELP_RE = re.compile(
    r"permission|denied|deny|classifier|auto mode|allow(?:list)?|settings\.json|bypass|approve", re.IGNORECASE)


RULE_RE = re.compile(r"`([A-Za-z]+\([^`]*\))`")  # e.g. `Bash(git commit --amend*)`


def load_deny_rules() -> tuple[set[str], dict[str, set[str]]]:
    """Deny rules from central settings and from every per-project settings file."""
    central: set[str] = set()
    per_project: dict[str, set[str]] = {}

    def deny_of(path):
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return set()
        perms = data.get("permissions") or {}
        return set(perms.get("deny") or []) | set(perms.get("ask") or [])

    for name in ("settings.json", "settings.local.json"):
        central |= deny_of(os.path.expanduser(f"~/.claude/{name}"))
    for path in glob.glob(os.path.expanduser("~/git/**/.claude/settings*.json"), recursive=True):
        project = os.path.dirname(os.path.dirname(path))
        rules = deny_of(path)
        if rules:
            per_project.setdefault(project, set()).update(rules)
    return central, per_project


def attribute_rule(reason: str, central: set[str], per_project: dict[str, set[str]]) -> set[str]:
    """Which config a classifier reason's quoted rules come from."""
    quoted = set(RULE_RE.findall(reason))
    if not quoted:
        return set()
    where = set()
    project_only = set().union(*per_project.values()) if per_project else set()
    for rule in quoted:
        if rule in central:
            where.add("central ~/.claude/settings.json deny rule")
        elif rule in project_only:
            where.add("per-project .claude/settings.json deny rule")
        else:
            where.add("rule quoted but not found in any settings file")
    return where


READONLY_SIGS = {
    "git status", "git log", "git diff", "git show", "git rev-parse", "git reflog",
    "git remote", "git fetch", "git ls-files", "git cat-file", "git describe",
    "ls", "cat", "head", "tail", "wc", "echo", "printf", "pwd", "find", "grep",
    "which", "du", "sort", "awk", "sed", "date", "sleep", "true", "test",
}
READONLY_PREFIXES = ("gh pr view", "gh issue view", "gh repo view", "gh run view", "gh api")
WRITE_FLAG_RE = re.compile(r"(?:^|\s)-{1,2}(?:f|D|d|m|M|force|delete|prune|hard)\b")


def segments_of(cmd: str) -> list[str]:
    return [s.strip() for s in re.split(r"&&|\|\||;|\n", cmd) if s.strip()]


def is_readonly(segment: str) -> bool:
    seg = segment.split("|")[0].strip()
    sigs = bash_signatures(seg)
    if any(seg.startswith(p) for p in READONLY_PREFIXES):
        return True
    if WRITE_FLAG_RE.search(seg):
        return False
    return bool(sigs) and sigs <= READONLY_SIGS


def effective_writes(cmd: str) -> set[str]:
    """Signatures of the state-changing parts of a command line."""
    out = set()
    for seg in segments_of(cmd):
        if not is_readonly(seg):
            out |= bash_signatures(seg)
    return out


def match_static_rule(tool: str, cmd: str, central: set[str], per_project: dict[str, set[str]],
                      cwd: str) -> tuple[str, str]:
    """Best-effort: which configured rule blocked this call, and from where.

    Claude Code matches rules per command segment, so test each segment of a
    compound shell line separately.
    """
    segments = [s.strip() for s in re.split(r"&&|\|\||;|\n|\|", cmd) if s.strip()] or [cmd]
    candidates: list[tuple[str, str]] = [(r, "central") for r in central]
    for project, rules in per_project.items():
        if cwd and cwd.startswith(project):
            candidates += [(r, "project") for r in rules]
    for rule, where in candidates:
        m = re.fullmatch(r"([A-Za-z]+)\((.*)\)", rule)
        if not m or m.group(1) != tool:
            continue
        pattern = m.group(2)
        for seg in segments:
            if fnmatch.fnmatch(seg, pattern) or fnmatch.fnmatch(seg, pattern + "*"):
                return rule, where
    return "", "no configured rule matched (built-in or hook)"


def parse_ts(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def blocks(rec: dict) -> list[dict]:
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def text_of(rec: dict) -> str:
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in blocks(rec) if b.get("type") == "text")


def result_text(block: dict) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") for b in c if isinstance(b, dict))
    return ""


def command_of(tool: str, tool_input: dict) -> str:
    if not isinstance(tool_input, dict):
        return ""
    if tool == "Bash":
        return tool_input.get("command", "") or ""
    for key in ("file_path", "path", "pattern", "url", "prompt"):
        if key in tool_input:
            return str(tool_input[key])
    return json.dumps(tool_input, sort_keys=True)[:200]


def bash_verbs(command: str) -> set[str]:
    """Rough set of program+subcommand tokens in a shell command line."""
    return {sig.split()[0] for sig in bash_signatures(command)}


def bash_signatures(command: str) -> set[str]:
    """`program subcommand` pairs, e.g. {'git commit', 'gh pr'}.

    Used to decide whether a later command is another attempt at the *same*
    blocked action rather than merely another invocation of the same program.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    sigs: set[str] = set()
    expect_program = True
    for i, tok in enumerate(tokens):
        if tok in ("&&", "||", "|", ";", "(", ")", "{", "}"):
            expect_program = True
            continue
        if expect_program:
            prog = os.path.basename(tok)
            sub = ""
            for nxt in tokens[i + 1:i + 2]:
                if not nxt.startswith("-") and nxt not in ("&&", "||", "|", ";"):
                    sub = os.path.basename(nxt)
            sigs.add(f"{prog} {sub}".strip())
            expect_program = False
    return sigs


def similarity(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class Session:
    """One transcript file, flattened into an ordered list of records."""

    def __init__(self, path: str):
        self.path = path
        self.project = os.path.basename(os.path.dirname(path))
        self.records: list[dict] = []
        with open(path, errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue


def analyse(paths: list[str], since: dt.datetime | None):
    central_deny, project_deny = load_deny_rules()
    stats = {
        "central_deny_rules": len(central_deny),
        "project_deny_files": len(project_deny),
        "sessions": set(),
        "tool_calls_by_mode": collections.Counter(),
        "tool_calls_by_tool": collections.Counter(),
        "denials_by_kind": collections.Counter(),
        "denials_by_tool": collections.Counter(),
        "denials_by_day": collections.Counter(),
        "denials_by_project": collections.Counter(),
        "classifier_categories": collections.Counter(),
        "classifier_citations": collections.Counter(),
        "rule_sources": collections.Counter(),
        "static_rule_source": collections.Counter(),
        "static_rule_hits": collections.Counter(),
        "classifier_no_citation": 0,
        "denied_bash_verbs": collections.Counter(),
        "followup": collections.Counter(),
        "user_prompts": 0,
        "assistant_turns": 0,
        "output_tokens": 0,
        "post_denial_turns": 0,
        "post_denial_output_tokens": 0,
        "user_help_prompts": 0,
    }
    events: list[dict] = []
    # A resumed session replays the earlier session's records into a new
    # transcript file, so the same record uuid can appear in several files.
    # Count each uuid once (first file wins); still keep every record in the
    # file for look-ahead context.
    counted: set[str] = set()
    stats["duplicate_records_skipped"] = 0

    for path in paths:
        sess = Session(path)
        recs = sess.records

        # index: tool_use_id -> (record index, tool name, input)
        tool_use: dict[str, tuple[int, str, dict]] = {}
        mode = "unknown"
        for i, rec in enumerate(recs):
            if rec.get("type") == "permission-mode":
                mode = rec.get("permissionMode", mode)
            if rec.get("type") == "assistant":
                for b in blocks(rec):
                    if b.get("type") == "tool_use":
                        tool_use[b.get("id", "")] = (i, b.get("name", "?"), b.get("input") or {})

        # result index: tool_use_id -> (record index, is_error, text)
        results: dict[str, tuple[int, bool, str]] = {}
        for i, rec in enumerate(recs):
            if rec.get("type") == "user":
                for b in blocks(rec):
                    if b.get("type") == "tool_result":
                        results[b.get("tool_use_id", "")] = (i, bool(b.get("is_error")), result_text(b))

        mode = "unknown"
        for i, rec in enumerate(recs):
            ts = parse_ts(rec.get("timestamp"))
            if rec.get("type") == "permission-mode":
                mode = rec.get("permissionMode", mode)
                continue
            if since and ts and ts < since:
                continue
            uuid = rec.get("uuid")
            if uuid:
                if uuid in counted:
                    stats["duplicate_records_skipped"] += 1
                    continue
                counted.add(uuid)
            rtype = rec.get("type")
            if ts:
                stats["sessions"].add(sess.path)

            if rtype == "assistant":
                usage = (rec.get("message") or {}).get("usage") or {}
                if blocks(rec):
                    stats["assistant_turns"] += 1
                    stats["output_tokens"] += usage.get("output_tokens", 0) or 0
                for b in blocks(rec):
                    if b.get("type") == "tool_use":
                        stats["tool_calls_by_mode"][mode] += 1
                        stats["tool_calls_by_tool"][b.get("name", "?")] += 1

            if rtype == "user":
                txt = text_of(rec)
                is_tool_result = any(b.get("type") == "tool_result" for b in blocks(rec))
                if not is_tool_result and txt and not rec.get("isMeta") and not SYNTHETIC_PROMPT_RE.match(txt):
                    stats["user_prompts"] += 1

                kind = rec.get("toolDenialKind")
                if not kind:
                    continue
                stats["denials_by_kind"][kind] += 1
                stats["denials_by_project"][sess.project] += 1
                if ts:
                    stats["denials_by_day"][ts.date().isoformat()] += 1

                block = next((b for b in blocks(rec) if b.get("type") == "tool_result"), {})
                rtxt = result_text(block)
                tid = block.get("tool_use_id", "")
                _, tool, tinput = tool_use.get(tid, (None, "?", {}))
                cmd = command_of(tool, tinput)
                stats["denials_by_tool"][tool] += 1
                if tool == "Bash":
                    for v in sorted(bash_verbs(cmd))[:2]:
                        stats["denied_bash_verbs"][v] += 1

                if kind == "permission-rule":
                    rule, where = match_static_rule(tool, cmd, central_deny, project_deny,
                                                    rec.get("cwd") or "")
                    stats["static_rule_source"][where] += 1
                    if rule:
                        stats["static_rule_hits"][rule] += 1

                category = None
                reason = ""
                if CLASSIFIER_MARKER in rtxt:
                    m = REASON_RE.search(rtxt)
                    if m:
                        category = (m.group("cat") or "uncategorised").strip()
                        reason = " ".join(m.group("reason").split())
                    stats["classifier_categories"][category or "uncategorised"] += 1
                    cited = [name for name, pat in CITATION_PATTERNS.items() if pat.search(reason)]
                    for name in cited:
                        stats["classifier_citations"][name] += 1
                    if not cited:
                        stats["classifier_no_citation"] += 1
                    for src in attribute_rule(rtxt, central_deny, project_deny):
                        stats["rule_sources"][src] += 1

                ev = follow_up(recs, i, tid, tool, cmd, tool_use, results, stats)
                ev.update({
                    "project": sess.project, "session": os.path.basename(sess.path),
                    "when": rec.get("timestamp"), "kind": kind, "tool": tool,
                    "command": cmd, "category": category, "reason": reason,
                    "mode": mode,
                })
                stats["followup"][ev["outcome"]] += 1
                events.append(ev)

    return stats, events


WINDOW_TURNS = 8  # assistant turns after a denial that we attribute to it


def follow_up(recs, idx, tool_id, tool, cmd, tool_use, results, stats):
    """Classify what happened after the denial at record `idx`.

    Only the next WINDOW_TURNS assistant turns within the same user prompt are
    considered; work further out is ordinary progress, not denial fallout.
    """
    prompt_id = recs[idx].get("promptId")
    literal_retries = 0
    variant_attempts = 0
    variant_succeeded = False
    denied_again = 0
    turns = 0
    tokens = 0
    user_stepped_in = False
    user_helped = False
    asked_user = False
    asked_permission = False  # used AskUserQuestion to get the go-ahead
    turns_before_user = None
    attempts: list[dict] = []

    for rec in recs[idx + 1:]:
        rtype = rec.get("type")
        if rtype == "user":
            txt = text_of(rec)
            is_tool_result = any(b.get("type") == "tool_result" for b in blocks(rec))
            if not is_tool_result and txt and not rec.get("isMeta") and not SYNTHETIC_PROMPT_RE.match(txt):
                turns_before_user = turns
                user_helped = bool(PERMISSION_HELP_RE.search(txt))
                # "stepped in" only counts if the model stalled right after the
                # denial; a prompt many turns later is just the next request.
                user_stepped_in = turns <= 3
                if user_helped:
                    stats["user_help_prompts"] += 1
                break
            continue
        if rtype != "assistant":
            continue
        if prompt_id and rec.get("promptId") not in (None, prompt_id):
            break
        if turns >= WINDOW_TURNS:
            break
        usage = (rec.get("message") or {}).get("usage") or {}
        if blocks(rec):
            turns += 1
            tokens += usage.get("output_tokens", 0) or 0
            stats["post_denial_turns"] += 1
            stats["post_denial_output_tokens"] += usage.get("output_tokens", 0) or 0
        for b in blocks(rec):
            if b.get("type") == "text" and re.search(
                    r"permission|denied|deny rule|classifier|can't (?:run|do)|blocked", b.get("text", ""), re.IGNORECASE):
                asked_user = True
            if b.get("type") != "tool_use":
                continue
            if b.get("name") == "AskUserQuestion":
                asked_permission = True
            ncmd = command_of(b.get("name", "?"), b.get("input") or {})
            same_goal = b.get("name") == tool and (
                ncmd == cmd
                or similarity(ncmd, cmd) >= 0.5
                or (tool == "Bash" and bool(bash_signatures(ncmd) & bash_signatures(cmd))
                    and similarity(ncmd, cmd) >= 0.25))
            if not same_goal:
                continue
            res = results.get(b.get("id", ""))
            failed = bool(res and res[1])
            if ncmd == cmd:
                literal_retries += 1
            else:
                variant_attempts += 1
            if failed:
                denied_again += 1
            elif ncmd != cmd:
                variant_succeeded = True
            # If the variant introduces no state-changing step that the blocked
            # command didn't already have, it is the same command with the
            # blocked part dropped (or read-only probing) -- explicitly allowed
            # by the denial message. A *new* write step means the goal was
            # reached by a different mechanism, which deserves a human look.
            dropped_part = not (effective_writes(ncmd) - effective_writes(cmd))
            attempts.append({
                "kind": "literal" if ncmd == cmd else "variant",
                "ok": not failed,
                "after_user_ok": asked_permission,
                "dropped_blocked_part": dropped_part,
                "command": " ".join(ncmd.split())[:200],
            })

    if variant_succeeded and asked_permission:
        outcome = "escalated, then proceeded with user's go-ahead"
    elif variant_succeeded:
        outcome = "worked around (variant succeeded, no user check)"
    elif variant_attempts or literal_retries:
        outcome = "retried, still blocked"
    elif asked_user:
        outcome = "stopped and explained to user"
    else:
        outcome = "moved on / no retry detected"

    return {
        "outcome": outcome,
        "literal_retries": literal_retries,
        "variant_attempts": variant_attempts,
        "denied_again": denied_again,
        "post_turns": turns,
        "post_tokens": tokens,
        "user_stepped_in": user_stepped_in,
        "user_helped": user_helped,
        "turns_before_user": turns_before_user,
        "asked_permission": asked_permission,
        "attempts": attempts,
    }


def bar(n, total, width=28):
    if not total:
        return ""
    return "#" * max(1, round(width * n / total)) if n else ""


def report(stats, events, since, details):
    def head(t):
        print(f"\n{t}\n" + "-" * len(t))

    total_calls = sum(stats["tool_calls_by_mode"].values())
    total_denials = sum(stats["denials_by_kind"].values())
    auto_calls = stats["tool_calls_by_mode"].get("auto", 0)
    classifier_denials = stats["denials_by_kind"].get("automode-blocked", 0)

    print("=" * 72)
    print("Claude Code permission / auto-mode classifier statistics")
    print(f"window: {'since ' + since.date().isoformat() if since else 'all transcripts'}")
    print(f"sessions: {len(stats['sessions'])}   human prompts: {stats['user_prompts']}   "
          f"assistant turns: {stats['assistant_turns']}   output tokens: {stats['output_tokens']:,}")
    print("=" * 72)

    head("Tool calls by permission mode")
    for mode, n in stats["tool_calls_by_mode"].most_common():
        print(f"  {mode:<12} {n:>7}  {100*n/total_calls:5.1f}%  {bar(n, total_calls)}")
    print(f"  {'TOTAL':<12} {total_calls:>7}")

    head("Permission decisions")
    print(f"  tool calls in auto mode                      {auto_calls:>7}")
    print(f"  ... denied by the classifier                 {classifier_denials:>7}"
          f"  ({100*classifier_denials/auto_calls:.2f}% of auto-mode calls)" if auto_calls else "")
    print(f"  ... not denied (upper bound on 'approved')   {auto_calls - classifier_denials:>7}")
    print("  NOTE: approvals are not logged; the figure above also includes calls")
    print("        matched by static allow rules or needing no permission at all.")

    head("Denials by kind")
    for kind, n in stats["denials_by_kind"].most_common():
        print(f"  {DENY_KIND_LABEL.get(kind, kind):<36} {n:>5}  {bar(n, total_denials)}")
    print(f"  {'TOTAL':<36} {total_denials:>5}")

    if stats["classifier_categories"]:
        head("Classifier denial categories")
        for cat, n in stats["classifier_categories"].most_common():
            print(f"  {cat:<36} {n:>5}  {bar(n, classifier_denials)}")

        head("What the classifier reason cited")
        for name, n in stats["classifier_citations"].most_common():
            print(f"  {name:<36} {n:>5}  ({100*n/classifier_denials:.0f}% of classifier denials)")
        print(f"  {'no config cited (general policy)':<36} {stats['classifier_no_citation']:>5}"
              f"  ({100*stats['classifier_no_citation']/classifier_denials:.0f}%)")

        head("Where a quoted rule actually lives")
        print(f"  ({stats['central_deny_rules']} central deny/ask rules; "
              f"{stats['project_deny_files']} projects with their own settings)")
        for src, n in stats["rule_sources"].most_common() or [("(no rule quoted verbatim)", 0)]:
            print(f"  {src:<48} {n:>5}")

    if stats["static_rule_source"]:
        head("Static-rule denials: which config blocked them")
        for src, n in stats["static_rule_source"].most_common():
            print(f"  {src:<48} {n:>5}")
        for rule, n in stats["static_rule_hits"].most_common(10):
            print(f"    {rule:<46} {n:>5}")
        print("  (best-effort re-match of the command against your rules; when")
        print("   several patterns match a command, the first one wins)")

    head("Denials by tool")
    for tool, n in stats["denials_by_tool"].most_common(10):
        print(f"  {tool:<36} {n:>5}")

    if stats["denied_bash_verbs"]:
        head("Most-denied shell commands")
        for verb, n in stats["denied_bash_verbs"].most_common(12):
            print(f"  {verb:<36} {n:>5}")

    head("Denials by project")
    for proj, n in stats["denials_by_project"].most_common(10):
        print(f"  {proj:<52} {n:>5}")

    head("Denials by day")
    for day in sorted(stats["denials_by_day"]):
        n = stats["denials_by_day"][day]
        print(f"  {day}  {n:>4}  {bar(n, max(stats['denials_by_day'].values()))}")

    head("What happened after a denial")
    for outcome, n in stats["followup"].most_common():
        print(f"  {outcome:<44} {n:>5}  ({100*n/total_denials:.0f}%)")

    retried = sum(1 for e in events if e["literal_retries"] or e["variant_attempts"])
    variants = sum(e["variant_attempts"] for e in events)
    literals = sum(e["literal_retries"] for e in events)
    worked_around = [e for e in events if e["outcome"].startswith("worked around")]
    escalated = sum(1 for e in events if e["outcome"].startswith("escalated"))
    head("Retry / work-around attempts")
    print(f"  denials followed by another attempt at the same goal   {retried:>5}"
          f"  ({100*retried/total_denials:.0f}% of denials)")
    print(f"  total variant attempts (different command, same goal)  {variants:>5}")
    print(f"  total literal re-runs of the blocked command           {literals:>5}")
    print(f"  succeeded only after asking the user (legitimate)      {escalated:>5}")
    print(f"  succeeded via a variant with no user check             {len(worked_around):>5}")

    def by_other_means(e):
        return [a for a in e["attempts"]
                if a["kind"] == "variant" and a["ok"] and not a["dropped_blocked_part"]]

    dropped_only = [e for e in worked_around if not by_other_means(e)]
    other_means = [e for e in worked_around if by_other_means(e)]
    print(f"  ... of which: re-ran the command without the blocked part {len(dropped_only):>5}")
    print(f"  ... of which: reached the goal by a different mechanism    {len(other_means):>5}")

    if other_means:
        head("Work-arounds by a different mechanism (audit these by hand)")
        for e in other_means:
            print(f"\n  {e['when']}  {e['project']}  [{e['kind']}]  {e.get('category') or ''}")
            print(f"    BLOCKED: {' '.join(e['command'].split())[:180]}")
            for a in e["attempts"]:
                print(f"    {a['kind']:<8} {'ok ' if a['ok'] else 'err'}  {a['command'][:160]}")

    head(f"Extra work caused by denials (<={WINDOW_TURNS}-turn window per denial)")
    print(f"  assistant turns in the windows                {stats['post_denial_turns']:>7}"
          f"  ({100*stats['post_denial_turns']/max(1,stats['assistant_turns']):.1f}% of all turns)")
    print(f"  output tokens in those turns                  {stats['post_denial_output_tokens']:>7,}"
          f"  ({100*stats['post_denial_output_tokens']/max(1,stats['output_tokens']):.1f}% of all output)")
    per = sorted(e["post_turns"] for e in events)
    if per:
        print(f"  turns per denial: median {per[len(per)//2]}, max {per[-1]}")
    stepped = sum(1 for e in events if e["user_stepped_in"])
    helped = sum(1 for e in events if e["user_helped"])
    both = sum(1 for e in events if e["user_stepped_in"] and e["user_helped"])
    print("  denials where the model stalled (<=3 turns) and the")
    print(f"    user then had to prompt again                {stepped:>5}"
          f"  ({100*stepped/total_denials:.0f}% of denials)")
    print(f"  ... where that prompt was about permissions     {both:>5}")
    print(f"  next human prompt mentioned permissions at all  {helped:>5}"
          f"  ({100*helped/total_denials:.0f}%)")

    if details:
        head(f"Sample denials (most recent {details})")
        for e in sorted(events, key=lambda e: e["when"] or "")[-details:]:
            print(f"\n  {e['when']}  {e['project']}  [{e['kind']}]")
            print(f"    tool: {e['tool']}  cmd: {e['command'][:120]}")
            if e["category"]:
                print(f"    category: {e['category']}")
            if e["reason"]:
                print(f"    reason: {e['reason'][:300]}")
            print(f"    outcome: {e['outcome']}  (+{e['post_turns']} turns, "
                  f"{e['variant_attempts']} variants, user stepped in: {e['user_stepped_in']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="ISO date; only count records at/after this date")
    ap.add_argument("--details", type=int, default=0, help="print N most recent denials verbatim")
    ap.add_argument("--json", action="store_true", help="dump denial events as JSON instead of a report")
    args = ap.parse_args()

    since = None
    if args.since:
        since = dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc)

    paths = sorted(glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")))
    stats, events = analyse(paths, since)
    if args.json:
        print(json.dumps(events, indent=2))
    else:
        report(stats, events, since, args.details)


if __name__ == "__main__":
    main()
