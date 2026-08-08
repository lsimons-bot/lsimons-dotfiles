# Communication

- Flag vague requests and bad approaches.
- Be terse in interactions.
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

## Commit and PR Attribution

- Do NOT add `Signed-off-by` tags. Only humans can certify the Developer Certificate of Origin.
<!-- attribution:start -->
- `Co-Authored-By` attribution is configured (e.g. in `~/.claude/settings.json`) and is applied automatically to both commit messages and PR descriptions — do not remove or skip it.
<!-- attribution:end -->
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

# Skills by development phase

- **Define:** ao-interview-me, ao-idea-refine, ao-spec-driven-development
- **Plan:** ao-planning-and-task-breakdown
- **Build:** ao-incremental-implementation + ao-test-driven-development (one task at a time), or ao-autonomous-plan-execution (the whole plan, hands-off after one approval); also ao-context-engineering, ao-source-driven-development, ao-doubt-driven-development, ao-frontend-ui-engineering, ao-api-and-interface-design
- **Verify:** ao-browser-testing-with-devtools, ao-debugging-and-error-recovery
- **Review:** ao-code-review-and-quality, ao-code-simplification, ao-security-and-hardening, ao-performance-optimization
- **Ship:** ao-git-workflow-and-versioning, ao-ci-cd-and-automation, ao-deprecation-and-migration, ao-documentation-and-adrs, ao-observability-and-instrumentation, ao-shipping-and-launch
