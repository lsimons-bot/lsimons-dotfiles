#!/usr/bin/env bash
# git sign [--no-push] [<base>]
#
# Re-sign every commit on the current branch since it forked from <base>
# (default: origin/main), verify the signatures, then push.
# Meant for the host: claude-docker sessions commit unsigned by design.
# ~/.local/bin/git-sign links here, which makes it `git sign`; see
# claude-docker/install.py.
set -euo pipefail

push=1
if [ "${1:-}" = "--no-push" ]; then
  push=0
  shift
fi
base_ref="${1:-origin/main}"

branch=$(git symbolic-ref --short HEAD)
if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
  echo "git sign: refusing to rewrite $branch" >&2
  exit 1
fi

# Without this, signed commits report %G? = N, same as unsigned ones.
if [ -z "$(git config --get gpg.ssh.allowedSignersFile)" ]; then
  echo "git sign: gpg.ssh.allowedSignersFile is not set; signatures can't be verified" >&2
  exit 1
fi

# No fetch on purpose: fetching would move origin/<branch> and weaken
# --force-with-lease below.
fork_point=$(git merge-base HEAD "$base_ref")
if [ -z "$(git rev-list "$fork_point..HEAD")" ]; then
  echo "git sign: no commits on $branch since $base_ref"
  exit 0
fi

# Replay onto the fork point, not $base_ref, so the base never moves and
# nothing can conflict. -f is required: without it git sees the branch as
# up to date and signs nothing.
if ! git rebase --force-rebase --gpg-sign "$fork_point"; then
  echo "git sign: rebase failed; run 'git rebase --abort' to get back" >&2
  exit 1
fi

git log --format='%h %G? %GS %s' "$fork_point..HEAD"
# Captured first rather than piped: with pipefail, grep -q exiting early
# can SIGPIPE git log, fail the pipeline, and so skip this check.
statuses=$(git log --format='%G?' "$fork_point..HEAD")
if grep -qv '^G$' <<<"$statuses"; then
  echo "git sign: some commits lack a good signature (see above); not pushing" >&2
  exit 1
fi

if [ "$push" = "0" ]; then
  exit 0
fi
if git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' >/dev/null 2>&1; then
  git push --force-with-lease --force-if-includes
else
  git push --set-upstream origin HEAD
fi
