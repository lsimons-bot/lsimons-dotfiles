# Issue tracker: GitHub

Issues for this project are managed as GitHub issues at
[lsimons/lsimons-dotfiles](https://github.com/lsimons/lsimons-dotfiles/issues).

The issues live in the same remote as the source code (the GitHub default).

Use the `gh` CLI for all operations. Learn about it with `gh issue --help`.

```bash
gh issue list
gh issue list --label needs-triage
gh issue view <n> --comments
gh issue create --title "<type>(<scope>): <description>" --label needs-triage
```

Issue titles follow the same [Conventional
Commits](https://conventionalcommits.org/) shape as commit messages —
`type(scope): description` — so an issue reads like the commit that will
close it. `scope` is normally the topic directory the issue is about
(`git`, `agents`, `install`, `colors`, ...).

## Labels

The following issue labels are used:

```
NAME              DESCRIPTION                                     COLOR
bug               Something isn't working                         #d73a4a
documentation     Improvements or additions to documentation      #0075ca
enhancement       New feature or request                          #a2eeef
needs-triage      Maintainer needs to evaluate this issue         #e6e6fa
needs-info        Waiting on reporter for more information        #e6e6fa
ready-for-agent   Fully specified, ready for an autonomous agent  #e6e6fa
ready-for-human   Requires human implementation                   #e6e6fa
wontfix           This will not be worked on                      #ffffff
duplicate         This issue or pull request already exists       #cfd3d7
good first issue  Good for newcomers                              #7057ff
help wanted       Extra attention is needed                       #008672
invalid           This doesn't seem right                         #e4e669
question          Further information is requested                #d876e3
```

The first eight are the set this project relies on. The rest are GitHub's
stock labels, kept because closed issues already carry them.

Re-read the live list rather than trusting this file if the two disagree:

```bash
gh label list
```

## Triage

A new issue starts at `needs-triage`. Triage moves it to exactly one of:

- `ready-for-agent` — the issue states the desired end state precisely
  enough that an autonomous agent can implement and verify it without
  asking a question.
- `ready-for-human` — needs a judgement call, a credential, a physical
  machine, or a decision about what the project should do.
- `needs-info` — the report is not yet actionable by anyone.
- closed, with `wontfix` or `invalid`.

### Triage must test the premise, not reason about it

This repo has a worked example of why. Issue #9, *"design(install): choose
a Python-free macOS bootstrap"*, was closed `invalid` / `wontfix` on the
reasoning that macOS always supplies a `python3`, so "the installer can run
and upgrade to Homebrew Python for everything afterward."

That conclusion was wrong at the moment it was written. The Command Line
Tools `python3` is 3.9.6; `script/install.py` imports `helpers`, which
imports `tomllib` (new in 3.11), so it could not start at all. The
`tomllib` import had landed five weeks before the issue was closed. One
`/usr/bin/python3 script/install.py` would have shown it.

Before closing an issue as "already works", run the thing.
