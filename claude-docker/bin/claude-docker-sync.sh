#!/usr/bin/env bash
# claude-docker-sync: copy claude-docker's session transcripts out of the
# claude-code-home named volume into the host's ~/.claude/projects, so
# whatever archives host sessions picks them up too.
# ~/.local/bin/claude-docker-sync links here; see claude-docker/install.py.
# Keep it out of the topic root: the shell rc files source <topic>/*.sh.
#
# One-way and additive. The volume is mounted read-only, nothing is deleted
# on either side (transcripts the container's 30-day cleanup removes stay on
# the host), and a host file is only replaced by a newer copy of itself.
# Container projects keep their -workspaces-<name> directory names, so they
# never merge into a host project. Their memory/ directories are skipped:
# auto-memory a container session wrote must not be loaded by host sessions
# (claude-docker's docs/security.md, "Persistence").
#
# The destination can be overridden from the environment, e.g.
# CLAUDE_DOCKER_SYNC_DEST=~/claude-docker-sessions to export elsewhere.
set -euo pipefail

image="claude-docker-sync:local"
volume="claude-code-home"
dest="${CLAUDE_DOCKER_SYNC_DEST:-$HOME/.claude/projects}"

# No docker means nothing to sync yet, not a failure: exit 0 so a caller
# that runs this on a schedule or before archiving keeps going.
if ! command -v docker >/dev/null 2>&1; then
  echo "claude-docker-sync: warning: docker not on PATH; nothing synced" >&2
  exit 0
fi
if ! docker info >/dev/null 2>&1; then
  echo "claude-docker-sync: warning: docker is not running; nothing synced" >&2
  exit 0
fi
if ! docker image inspect "$image" >/dev/null 2>&1; then
  echo "claude-docker-sync: image $image is missing; build it with:" >&2
  echo "  docker build -t $image ~/git/lsimons/lsimons-dotfiles/claude-docker/sync-image" >&2
  exit 1
fi
if ! docker volume inspect "$volume" >/dev/null 2>&1; then
  echo "claude-docker-sync: no $volume volume; has claude-docker run here without --ephemeral?" >&2
  exit 1
fi

mkdir -p "$dest"

# --user: on Linux the copies would otherwise be owned by root. The volume's
# files belong to the host user already (claude-docker's entrypoint chowns
# them), so this user can read them. -rt rather than -a: ownership and
# permissions are not worth carrying across. --omit-dir-times: Docker
# Desktop refuses to set times on the bind mount's root, which fails the
# run with code 23, and directory times don't matter for an archive.
docker run --rm --network none \
  --user "$(id -u):$(id -g)" \
  -v "$volume:/src:ro" \
  -v "$dest:/dest" \
  "$image" \
  -rt --omit-dir-times --update --itemize-changes \
  --exclude '/*/memory/' \
  /src/projects/ /dest/
