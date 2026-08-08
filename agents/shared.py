"""Shared coding-agent configuration and rendering."""

import re
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
DOTFILES_ROOT = AGENTS_DIR.parent
AGENTS_MD = AGENTS_DIR / "AGENTS.md"

# Skills are not maintained here: they live in the lsimons-skills repository,
# which vendors the full collection. It is expected to be checked out next to
# this repository.
SKILLS_DIR = DOTFILES_ROOT.parent / "lsimons-skills" / "skills"

_ATTRIBUTION_RE = re.compile(
    r"<!-- attribution:start -->.*?<!-- attribution:end -->", re.DOTALL
)


def build_attribution(email):
    """Return the Co-Authored-By attribution line for the given git email."""
    if email == "bot@leosimons.com":
        return "Co-Authored-By: Leo Simons <mail@leosimons.com>"
    return "Co-Authored-By: lsimons-bot <bot@leosimons.com>"


def render_instructions(email):
    """Render global instructions for agents without attribution settings."""
    attribution = build_attribution(email)
    block = (
        "- End **both** commit messages and PR descriptions with exactly this "
        "attribution line. Do NOT emit your own built-in co-author trailer "
        "(e.g. `Co-authored-by: Copilot`, `Co-authored-by: opencode`) — use "
        "this line instead, and do not remove or skip it:\n"
        f"  `{attribution}`"
    )
    return _ATTRIBUTION_RE.sub(block, AGENTS_MD.read_text(), count=1)
