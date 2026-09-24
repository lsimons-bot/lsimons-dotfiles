# Communication

- Flag vague requests and bad approaches.
- State assumptions clearly.

## Code Approach
Prefer:
- Explicit over implicit.
- Boring over clever.
- Observable over silent.
- Readability over brevity.
- Following existing patterns over introducing new ones.
- Asking focused questions over guessing.
- Validating assumptions over completing tasks.

# Git

- PR merge preference: rebase > merge > squash. Default to `gh pr merge --rebase`.
- Use `--merge` if a downstream branch is stacked on the PR.
- Only use `--squash` when GitHub settings require it (branch protection rule or "Allow squash merging" is the only enabled option).

## Preserving History

Default to preserving history: add a new commit rather than rewriting an
existing one, and leave branches in place rather than deleting them.

Rewriting or deleting is fine — without asking — when all of these hold:

- The work being rewritten or deleted is yours from this session.
- It is not on `main` (or the repository's default branch).
- Nobody else has built on it: no stacked branch, no other open PR against it.

That covers the common repairs: `git commit --amend` on an unpushed commit,
`git rebase` of your own branch, `git push --force-with-lease` to a PR branch
you opened, and deleting your own merged branch. Use `--force-with-lease`,
never `--force`. Say what you are about to do before you do it.

Outside those conditions, ask first.

## Commit and PR Attribution

- Do NOT add `Signed-off-by` tags. Only humans can certify the Developer Certificate of Origin.
- End **both** commit messages and PR descriptions with exactly this attribution line, and do not remove or skip it. Do NOT emit your own built-in co-author trailer (e.g. `Co-authored-by: Copilot`, `Co-authored-by: opencode`) — use this line instead:
  `Co-Authored-By: lsimons-bot <bot@leosimons.com>`
- In addition, include an `Assisted-by` tag:
  `Assisted-by: AGENT_NAME:MODEL_VERSION`
  Example: `Assisted-by: Claude:claude-sonnet-4-6`

# Python

- Python 3.13 and 3.14 introduce new syntax.
- Load the `python-knowledge-patch` skill to understand Python 3.13/3.14 syntax.
- `ruff` can reformat files in surprising ways. Use the python-knowledge-patch skill to understand.
- Python 3.14+ supports PEP 758 bracketless `except E1, E2:` (equivalent to `except (E1, E2):`). Removing such parens is correct — leave it alone. The syntax looks like deprecated Py2 `except E, e:` (variable binding) but is unrelated.
- Python 3.14+ supports PEP 750 new string prefix `t` that produces a `Template` object instead of `str`. Like f-strings but with access to parts before rendering.

# TypeScript

- TypeScript 7 is new and cannot always be used yet.
- Do not upgrade from TypeScript 6 to 7 without my explicit agreement.
