"""Shared coding-agent configuration and rendering."""

from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
DOTFILES_ROOT = AGENTS_DIR.parent
AGENTS_MD = AGENTS_DIR / "AGENTS.md"

# Skills are not maintained here: they live in the lsimons-skills repository,
# which vendors the full collection. It is expected to be checked out next to
# this repository.
SKILLS_DIR = DOTFILES_ROOT.parent / "lsimons-skills" / "skills"

# sbp-brandbook is not open source, so it lives in the private sbp-skills
# checkout instead of lsimons-skills. It's symlinked into SKILLS_DIR so it
# still reaches every agent through the same shared mechanism.
SBP_BRANDBOOK_SRC = DOTFILES_ROOT.parent / "sbp-skills" / "skills" / "sbp-brandbook"

# AGENTS.md carries the human-as-co-author line verbatim, which is what every
# machine but the bot's own wants. Rendering only has to swap it out when the
# bot is the one committing, so the line itself is the substitution anchor.
DEFAULT_ATTRIBUTION = "Co-Authored-By: lsimons-bot <bot@leosimons.com>"
BOT_ATTRIBUTION = "Co-Authored-By: Leo Simons <mail@leosimons.com>"


def build_attribution(email):
    """Return the Co-Authored-By attribution line for the given git email."""
    if email == "bot@leosimons.com":
        return BOT_ATTRIBUTION
    return DEFAULT_ATTRIBUTION


def render_instructions(email):
    """Render global instructions with the attribution line for this machine.

    Every agent gets the literal line in its instructions, including Claude
    Code: its built-in `attribution` setting produced trailers that disagreed
    with these instructions, so it is switched off (see `write_settings()` in
    claude/install.py) and the instructions are the only source of trailers.
    """
    text = AGENTS_MD.read_text()
    if DEFAULT_ATTRIBUTION not in text:
        raise ValueError(f"{AGENTS_MD} no longer contains {DEFAULT_ATTRIBUTION!r}")
    return text.replace(DEFAULT_ATTRIBUTION, build_attribution(email))
