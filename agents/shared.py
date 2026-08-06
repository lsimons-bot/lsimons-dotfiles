"""Shared coding-agent configuration and rendering."""

import re
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
AGENTS_MD = AGENTS_DIR / "AGENTS.md"
SKILLS_DIR = AGENTS_DIR / "skills"
SKILLS_MANIFEST = AGENTS_DIR / "skills.txt"

_ATTRIBUTION_RE = re.compile(
    r"<!-- attribution:start -->.*?<!-- attribution:end -->", re.DOTALL
)


def build_attribution(email):
    """Return the Co-Authored-By attribution line for the given git email."""
    if email == "bot@leosimons.com":
        return "Co-Authored-By: Leo Simons <mail@leosimons.com>"
    return "Co-Authored-By: lsimons-bot <bot@leosimons.com>"


def load_skills_manifest():
    """Return ``[(repository_url, skill_name), ...]`` from ``skills.txt``."""
    entries = []
    for lineno, line in enumerate(SKILLS_MANIFEST.read_text().splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(
                f"{SKILLS_MANIFEST}:{lineno}: expected '<repository-url> "
                f"<skill-name>', got: {line}"
            )
        entries.append((parts[0], parts[1]))
    return entries


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
