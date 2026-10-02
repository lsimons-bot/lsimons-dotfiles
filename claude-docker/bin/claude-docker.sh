#!/usr/bin/env bash
# claude-docker wrapper: runs the upstream run.sh against the personal child
# image (claude-docker/image) instead of the bare claude-code:local.
# ~/.local/bin/claude-docker links here; see claude-docker/install.py.
# Keep it out of the topic root: the shell rc files source <topic>/*.sh.
#
# Both defaults can be overridden from the environment, e.g.
# CLAUDE_DOCKER_IMAGE=claude-code:local to run the upstream image as-is.
set -euo pipefail

run_sh="${CLAUDE_DOCKER_RUN_SH:-$HOME/git/sbp/claude-docker/run.sh}"
export CLAUDE_DOCKER_IMAGE="${CLAUDE_DOCKER_IMAGE:-claude-code-lsimons:local}"

exec "$run_sh" "$@"
