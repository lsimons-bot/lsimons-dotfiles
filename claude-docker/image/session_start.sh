#!/bin/sh
# Claude Code SessionStart hook, wired up by claude-docker/install.py in
# ~/.claude/settings.docker.json. Its stdout lands in Claude's context.
#
# Tells Claude when the project pins mise tools that are not installed in
# the container yet: the shims then fall through to the image's own node,
# go and python without any error, which is easy to miss. Reports only;
# installing is left to `mise install`, which can take minutes on first use.
missing=$(mise ls --current --missing --json 2>/dev/null \
  | jq -r 'to_entries[] | .key as $tool | .value[] | "\($tool)@\(.version)"' 2>/dev/null \
  | tr '\n' ' ')
if [ -n "$missing" ]; then
  echo "mise: this project pins tools that are not installed in this container: ${missing% }."
  echo "Until \`mise install\` runs, those commands silently use the image's own versions instead."
fi
exit 0
