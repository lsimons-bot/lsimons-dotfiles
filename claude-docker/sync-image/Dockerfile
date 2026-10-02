# rsync and nothing else, for bin/claude-docker-sync.sh: it copies the
# session transcripts out of the claude-code-home named volume, which only a
# container can read.
#
# Built by claude-docker/install.py when missing. Rebuild by hand to pick up
# a newer alpine or rsync:
#   docker build -t claude-docker-sync:local ~/git/lsimons/lsimons-dotfiles/claude-docker/sync-image
#
# Pinned to the multi-arch index digest, so the same line builds natively on
# arm64 and amd64. Bump with: docker buildx imagetools inspect alpine:3
FROM alpine:3.24.2@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6

RUN apk add --no-cache rsync

ENTRYPOINT ["rsync"]
