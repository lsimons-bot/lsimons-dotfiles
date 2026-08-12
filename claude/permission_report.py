#!/usr/bin/env python3
"""Render the auto-mode permission statistics as a self-contained HTML report.

Imports the analysis from permission_stats.py (same directory), runs it over two
windows (this week and all transcripts), and writes one HTML file with no
external assets -- no CDN, no JS libraries, CSS-only charts -- so it can be
mailed or opened offline.

Usage:
  python3 claude/permission_report.py [--since YYYY-MM-DD] [--out FILE]
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import importlib.util
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location("permission_stats", os.path.join(HERE, "permission_stats.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

# Classifier categories grouped into the root causes worth acting on.
CLUSTERS = {
    "Merge without human review": ["Merge Without Review"],
    "Unasked outward-facing writes": ["External System Writes", "Production Deploy", "Modify Shared Resources"],
    "Git history rewrite (amend / force-push)": ["Git Destructive", "User Deny Rules"],
    "Destruction beyond the task scope": ["Irreversible Local Destruction", "Irreversible Deletion general"],
    "Agent modifying its own guardrails": ["Self-Modification", "Self Modification", "Self-Approval", "Auto-Mode Bypass"],
    "Credential exposure": ["Credential Exploration", "Credential Materialization"],
    "Other / provenance / transient": ["Instruction Poisoning", "Blind Apply", "Sensitive-Source Provenance", "uncategorised"],
}

CLUSTER_FIX = {
    "Merge without human review": "AGENTS.md gives merge <em>strategy</em> but never says who decides; state the gate explicitly.",
    "Unasked outward-facing writes": "No rule on one-way doors, and terse acks (&ldquo;approved&rdquo;, &ldquo;continue&rdquo;) get over-read as broad authorization.",
    "Git history rewrite (amend / force-push)": "Trailer rules with no non-amend repair path, against an absolute deny rule.",
    "Destruction beyond the task scope": "No &ldquo;only delete what you created, and name it first&rdquo; rule.",
    "Agent modifying its own guardrails": "Widening its own allowlist / self-approving PRs is not prohibited anywhere.",
    "Credential exposure": "Enumerating credential stores and printing token fragments is not prohibited anywhere.",
    "Other / provenance / transient": "Includes transient stage-2 classifier errors, which no instruction can prevent.",
}

CSS = """
:root {
  --ink: #16181d; --muted: #6b7280; --line: #e5e7eb; --bg: #ffffff;
  --panel: #f9fafb; --accent: #b45309; --accent-soft: #fef3c7;
  --deny: #b91c1c; --ok: #15803d; --info: #1d4ed8;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 1.5rem 5rem; background: var(--bg); color: var(--ink);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
main { max-width: 62rem; margin: 0 auto; }
header.title { padding: 3rem 0 1.5rem; border-bottom: 2px solid var(--ink); margin-bottom: 2.5rem; }
h1 { font-size: 2.1rem; line-height: 1.2; margin: 0 0 .5rem; letter-spacing: -.02em; }
h2 {
  font-size: 1.35rem; margin: 3rem 0 .25rem; padding-top: 1.5rem;
  border-top: 1px solid var(--line); letter-spacing: -.01em;
}
h3 { font-size: 1rem; margin: 2rem 0 .5rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
p, li { max-width: 52rem; }
.sub { color: var(--muted); margin: 0; }
.lede { font-size: 1.1rem; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); gap: 1rem; margin: 1.5rem 0 0; }
.card { border: 1px solid var(--line); border-radius: .6rem; padding: 1rem 1.1rem; background: var(--panel); }
.card .n { font-size: 1.9rem; font-weight: 650; letter-spacing: -.03em; display: block; }
.card .k { font-size: .82rem; color: var(--muted); display: block; margin-top: .15rem; }
.card.hi { background: var(--accent-soft); border-color: #fcd34d; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: .95rem; }
th, td { text-align: left; padding: .5rem .6rem; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 600; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.bar { display: block; height: .55rem; border-radius: 3px; background: var(--accent); min-width: 2px; }
.bar.deny { background: var(--deny); }
.bar.ok { background: var(--ok); }
.bar.info { background: var(--info); }
td.barcell { width: 34%; padding-top: .85rem; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
code { font-size: .86em; background: var(--panel); padding: .1rem .3rem; border-radius: 3px; }
pre {
  background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--ink);
  padding: .7rem .9rem; overflow-x: auto; font-size: .82rem; margin: .4rem 0; line-height: 1.45;
}
pre.blocked { border-left-color: var(--deny); }
pre.variant { border-left-color: var(--ok); }
.note {
  background: var(--accent-soft); border: 1px solid #fcd34d; border-radius: .6rem;
  padding: .9rem 1.1rem; margin: 1.5rem 0; font-size: .95rem;
}
.note strong { color: #92400e; }
.case { border: 1px solid var(--line); border-radius: .6rem; padding: 1rem 1.1rem; margin: 1rem 0; }
.case h4 { margin: 0 0 .5rem; font-size: .95rem; }
.tag {
  display: inline-block; font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
  padding: .1rem .45rem; border-radius: 3px; background: var(--panel); border: 1px solid var(--line);
  color: var(--muted); margin-right: .35rem; white-space: nowrap;
}
.tag.deny { background: #fee2e2; border-color: #fecaca; color: #991b1b; }
.tag.ok { background: #dcfce7; border-color: #bbf7d0; color: #166534; }
.label { font-size: .74rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
footer { margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .87rem; }
ul.tight li { margin: .3rem 0; }
@media print {
  body { padding: 0; font-size: 11pt; }
  h2 { page-break-after: avoid; }
  .case, table { page-break-inside: avoid; }
}
"""


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def bar(n, total, cls="") -> str:
    pct = 0 if not total else 100 * n / total
    return f'<span class="bar {cls}" style="width:{max(pct, 0.8):.1f}%"></span>'


def rows(counter, total=None, cls="", limit=None, fmt=str):
    total = total or (max(counter.values()) if counter else 1)
    items = counter.most_common(limit) if limit else counter.most_common()
    out = []
    for key, n in items:
        out.append(f"<tr><td>{fmt(key)}</td><td class='n'>{n}</td>"
                   f"<td class='barcell'>{bar(n, total, cls)}</td></tr>")
    return "\n".join(out)


def pct(n, d, decimals=0) -> str:
    return "0%" if not d else f"{100 * n / d:.{decimals}f}%"


# New write steps that matter when judging a work-around; a variant that merely
# adds a mkdir or a copy is scaffolding, not a route around the boundary.
INTERESTING = ("git", "gh", "glab", "aws", "curl", "op", "rm")


def interest(event, new_attempts) -> int:
    sigs = set()
    for a in new_attempts:
        sigs |= S.effective_writes(a["command"])
    blocked = S.effective_writes(event["command"])
    novel = {s for s in sigs - blocked if s.split()[0] in INTERESTING}
    return len(novel)


def clean(cmd: str, limit=260) -> str:
    one = " ".join(str(cmd).split())
    return esc(one[:limit] + ("…" if len(one) > limit else ""))


def build(week, alltime, since, generated) -> str:
    ws, we = week
    as_, ae = alltime

    w_total = sum(ws["denials_by_kind"].values())
    a_total = sum(as_["denials_by_kind"].values())
    w_auto = ws["tool_calls_by_mode"].get("auto", 0)
    a_auto = as_["tool_calls_by_mode"].get("auto", 0)
    w_cls = ws["denials_by_kind"].get("automode-blocked", 0)
    a_cls = as_["denials_by_kind"].get("automode-blocked", 0)

    # Root-cause clusters over the all-time classifier denials (bigger sample).
    cluster_counts = {}
    for name, cats in CLUSTERS.items():
        cluster_counts[name] = sum(as_["classifier_categories"].get(c, 0) for c in cats)

    def by_other_means(e):
        return [a for a in e["attempts"] if a["kind"] == "variant" and a["ok"] and not a["dropped_blocked_part"]]

    w_workarounds = [e for e in we if e["outcome"].startswith("worked around")]
    a_workarounds = [e for e in ae if e["outcome"].startswith("worked around")]
    w_other = [e for e in w_workarounds if by_other_means(e)]
    a_other = [e for e in a_workarounds if by_other_means(e)]
    w_escalated = [e for e in we if e["outcome"].startswith("escalated")]

    cases = []
    ranked = sorted(a_other, key=lambda e: (interest(e, by_other_means(e)), e["when"] or ""), reverse=True)
    for e in ranked[:5]:
        variants = "".join(
            f'<div><span class="label">then, allowed:</span><pre class="variant">{clean(a["command"])}</pre></div>'
            for a in by_other_means(e)[:1])
        cases.append(f"""
        <div class="case">
          <h4><span class="tag deny">{esc(S.DENY_KIND_LABEL.get(e['kind'], e['kind']))}</span>
              {esc(e.get('category') or '')}
              <span class="tag">{esc((e['when'] or '')[:10])}</span>
              <span class="tag">{esc(e['project'].split('-git-')[-1])}</span></h4>
          <div><span class="label">blocked:</span><pre class="blocked">{clean(e['command'])}</pre></div>
          {variants}
        </div>""")

    top_reasons = "".join(
        f"<li><strong>{esc(e['category'])}</strong> — {esc(e['reason'][:260])}…</li>"
        for e in sorted([x for x in ae if x["kind"] == "automode-blocked" and x["reason"]],
                        key=lambda x: x["when"] or "", reverse=True)[:5])

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code auto mode — permission decision report</title>
<style>{CSS}</style>
</head><body><main>

<header class="title">
  <p class="sub">Transcript analysis · generated {esc(generated)}</p>
  <h1>What the auto-mode permission classifier actually blocked</h1>
  <p class="lede sub">{as_['sessions_n']} Claude Code sessions, {a_auto:,} tool calls in auto mode,
  {a_total} permission denials. Measured from local session transcripts
  (<code>~/.claude/projects/*/*.jsonl</code>), not from vendor telemetry.</p>
</header>

<div class="note">
  <strong>Read this first.</strong> Transcripts record <em>denials</em> only. An auto-mode
  approval leaves no trace, and an approved call is indistinguishable from one matched by a
  static allow rule or one that needed no permission at all. Every &ldquo;approved&rdquo;
  figure below is therefore an upper bound, not a classifier decision count.
</div>

<h2>Headline: this week</h2>
<p class="sub">Window: since {esc(since)} · {ws['sessions_n']} sessions ·
{ws['user_prompts']} human prompts · {ws['assistant_turns']:,} assistant turns ·
{ws['output_tokens']:,} output tokens.</p>
<div class="cards">
  <div class="card"><span class="n">{w_auto:,}</span><span class="k">tool calls in auto mode
    ({pct(w_auto, sum(ws['tool_calls_by_mode'].values()))} of all calls)</span></div>
  <div class="card hi"><span class="n">{w_cls}</span><span class="k">classifier denials
    ({100*w_cls/max(1,w_auto):.2f}% of auto-mode calls)</span></div>
  <div class="card"><span class="n">{ws['denials_by_kind'].get('permission-rule', 0)}</span>
    <span class="k">static deny-rule denials</span></div>
  <div class="card"><span class="n">{ws['denials_by_kind'].get('user-rejected', 0)}</span>
    <span class="k">rejected by the human</span></div>
  <div class="card"><span class="n">{pct(ws['post_denial_turns'], ws['assistant_turns'], 1)}</span>
    <span class="k">of turns spent in the wake of a denial</span></div>
</div>

<h3>Auto mode is the working default</h3>
<table>
  <tr><th>Permission mode</th><th class="n">Tool calls</th><th></th></tr>
  {rows(ws['tool_calls_by_mode'], sum(ws['tool_calls_by_mode'].values()), 'info')}
</table>

<h3>Who said no</h3>
<table>
  <tr><th>Source of the denial</th><th class="n">This week</th><th></th><th class="n">All time</th></tr>
  {"".join(
      f"<tr><td>{esc(S.DENY_KIND_LABEL.get(k, k))}</td><td class='n'>{ws['denials_by_kind'].get(k, 0)}</td>"
      f"<td class='barcell'>{bar(ws['denials_by_kind'].get(k, 0), w_total, 'deny')}</td>"
      f"<td class='n'>{as_['denials_by_kind'].get(k, 0)}</td></tr>"
      for k in ("permission-rule", "user-rejected", "automode-blocked", "automode-unavailable"))}
  <tr><td><strong>Total</strong></td><td class="n"><strong>{w_total}</strong></td><td></td>
      <td class="n"><strong>{a_total}</strong></td></tr>
</table>
<p class="sub">The classifier is the smallest of the three. Most friction comes from static deny
rules the user configured themselves — those never reach the classifier and produce no explanation.</p>

<h2>Why the classifier said no</h2>
<p>Across all {a_cls} classifier denials, the stated categories group into a handful of root causes.
Each is a case of the agent taking a one-way action the transcript showed no authorization for.</p>
<table>
  <tr><th>Root cause</th><th class="n">n</th><th></th><th>Why it happens</th></tr>
  {"".join(
      f"<tr><td>{esc(name)}</td><td class='n'>{n}</td>"
      f"<td class='barcell'>{bar(n, max(cluster_counts.values()), 'deny')}</td>"
      f"<td class='sub'>{CLUSTER_FIX.get(name, '')}</td></tr>"
      for name, n in sorted(cluster_counts.items(), key=lambda kv: -kv[1]) if n)}
</table>

<h3>Sample verdicts, verbatim</h3>
<ul class="tight">{top_reasons}</ul>

<h2>Did it cite the user's own configuration?</h2>
<p>A recurring question: is the classifier enforcing the user's written rules, or its own general
policy? For classifier denials, the reason text was matched against known config references;
for static denials, the blocked command was re-matched against the actual rule files.</p>
<table>
  <tr><th>Classifier reason cited …</th><th class="n">n</th><th></th><th class="n">share</th></tr>
  {"".join(
      f"<tr><td>{esc(k)}</td><td class='n'>{v}</td>"
      f"<td class='barcell'>{bar(v, a_cls, 'info')}</td><td class='n'>{pct(v, a_cls)}</td></tr>"
      for k, v in as_['classifier_citations'].most_common())}
  <tr><td>no configuration cited — general policy</td>
      <td class="n">{as_['classifier_no_citation']}</td>
      <td class="barcell">{bar(as_['classifier_no_citation'], a_cls, 'info')}</td>
      <td class="n">{pct(as_['classifier_no_citation'], a_cls)}</td></tr>
</table>
<p class="sub">Two thirds of classifier denials rest on general policy rather than on anything the
user wrote. Where a rule <em>was</em> quoted, it resolved to the central
<code>~/.claude/settings.json</code> in {as_['rule_sources'].get('central ~/.claude/settings.json deny rule', 0)}
of cases and to a per-project settings file in
{as_['rule_sources'].get('per-project .claude/settings.json deny rule', 0)}.</p>

<h3>Static deny rules: which ones actually fire</h3>
<table>
  <tr><th>Rule</th><th class="n">Hits (all time)</th><th></th></tr>
  {rows(as_['static_rule_hits'], None, 'deny', 8, fmt=lambda k: f"<code>{esc(k)}</code>")}
</table>
<p class="sub">All resolved to the central settings file; no per-project deny rule fired at all.
<code>Bash(rm -rf /*)</code> leads because it matches <em>any</em> absolute-path
<code>rm -rf</code>, including routine scratch cleanup under <code>/tmp</code>.</p>

<h2>What the agent did after being blocked</h2>
<p>The interesting question for an autonomous setup is not the denial count but the behaviour that
follows: does the agent respect the boundary, escalate, or route around it?</p>
<table>
  <tr><th>Outcome</th><th class="n">This week</th><th></th><th class="n">All time</th></tr>
  {"".join(
      f"<tr><td>{esc(k)}</td><td class='n'>{ws['followup'].get(k, 0)}</td>"
      f"<td class='barcell'>{bar(ws['followup'].get(k, 0), w_total)}</td>"
      f"<td class='n'>{as_['followup'].get(k, 0)}</td></tr>"
      for k, _ in as_['followup'].most_common())}
</table>
<div class="cards">
  <div class="card"><span class="n">{pct(sum(1 for e in we if e['literal_retries'] or e['variant_attempts']), w_total)}</span>
    <span class="k">of denials got another attempt at the same goal (this week)</span></div>
  <div class="card"><span class="n">{len(w_escalated)}</span>
    <span class="k">proceeded only after asking the human and getting a yes</span></div>
  <div class="card"><span class="n">{len(w_other)} <span style="font-size:.6em">of {len(w_workarounds)}</span></span>
    <span class="k">succeeded by a genuinely different mechanism, no human check</span></div>
  <div class="card"><span class="n">{len(a_other)} <span style="font-size:.6em">of {len(a_workarounds)}</span></span>
    <span class="k">same, all time (of all successful retries)</span></div>
</div>
<p>Most successful retries are the behaviour the denial message explicitly permits: re-run the
command with the blocked segment removed, or substitute a read-only equivalent. The cases worth a
human eye are those that reached the goal by a <em>new</em> state-changing step — for example a
blocked <code>git reset --hard origin/main</code> followed by an allowed
<code>git branch -f main origin/main</code>, which has the same effect on the ref.</p>

{"".join(cases)}
<p class="sub">Ranked by how far the allowed variant departs from the blocked command. The
heuristic over-reports: some of these are the same command minus its blocked segment plus extra
scaffolding, which is sanctioned behaviour. That is why they are shown verbatim.</p>

<h2>What it cost</h2>
<div class="cards">
  <div class="card"><span class="n">{ws['post_denial_turns']}</span>
    <span class="k">assistant turns in the ≤8-turn window after a denial
    ({pct(ws['post_denial_turns'], ws['assistant_turns'], 1)} of all turns)</span></div>
  <div class="card"><span class="n">{ws['post_denial_output_tokens']:,}</span>
    <span class="k">output tokens in those turns
    ({pct(ws['post_denial_output_tokens'], ws['output_tokens'], 1)} of all output)</span></div>
  <div class="card"><span class="n">{sorted(e['post_turns'] for e in we)[len(we)//2] if we else 0}</span>
    <span class="k">median turns per denial</span></div>
  <div class="card"><span class="n">{sum(1 for e in we if e['user_helped'])}</span>
    <span class="k">follow-up human prompts that mentioned permissions at all</span></div>
</div>
<p>Denial handling is a rounding error on throughput: about
{pct(ws['post_denial_turns'], ws['assistant_turns'], 1)} of turns and
{pct(ws['post_denial_output_tokens'], ws['output_tokens'], 1)} of output tokens this week. The human
was rarely dragged in to negotiate permissions — of
{sum(1 for e in we if e['user_stepped_in'])} denials where the agent stalled and the human prompted
again, only {sum(1 for e in we if e['user_helped'])} of those prompts mentioned permissions; the
rest were ordinary next-step direction.</p>

<h2>Method and limitations</h2>
<ul class="tight">
  <li><strong>Source.</strong> {len(as_['sessions'])} transcript files under
    <code>~/.claude/projects</code>. Denials are identified by the
    <code>toolDenialKind</code> field; classifier reasons are parsed from the tool-result text.</li>
  <li><strong>Deduplication.</strong> A resumed session replays the earlier session's records into a
    new file, so records are counted once by uuid; {as_['duplicate_records_skipped']:,} duplicate
    records were skipped. Before this was handled, several denials double-counted.</li>
  <li><strong>Approvals are unobservable.</strong> See the note at the top.</li>
  <li><strong>Retry classification is heuristic.</strong> A later call counts as another attempt at
    the same goal when it uses the same tool within 8 turns of the same prompt and either shares
    ≥50% of its tokens or repeats a <code>program subcommand</code> pair with ≥25% overlap. A
    successful variant counts as a real work-around only if it introduces a state-changing step the
    blocked command did not have. Both rules produce false positives; the flagged cases are printed
    verbatim so they can be audited by hand rather than trusted.</li>
  <li><strong>Attribution of static rules</strong> re-matches the command against the rule files
    with shell-glob semantics; when several patterns match, the first wins.</li>
  <li><strong>Cost attribution</strong> caps at 8 assistant turns per denial. Longer tails are
    ordinary progress, not fallout — but the cap also means a genuinely expensive derailment is
    under-counted.</li>
</ul>

<footer>
  Generated by <code>claude/permission_report.py</code> from
  <code>claude/permission_stats.py</code> · self-contained, no external assets ·
  windows: this week (since {esc(since)}) and all transcripts.
</footer>
</main></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-06")
    # Generated artifact: default outside the repo so it never gets committed.
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "claude-permission-report.html"))
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(S.PROJECTS, "*", "*.jsonl")))
    since = dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc)

    week = S.analyse(paths, since)
    alltime = S.analyse(paths, None)
    for st, _ in (week, alltime):
        st["sessions_n"] = len(st["sessions"])

    generated = dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    with open(args.out, "w") as fh:
        fh.write(build(week, alltime, args.since, generated))
    print(args.out)


if __name__ == "__main__":
    main()
