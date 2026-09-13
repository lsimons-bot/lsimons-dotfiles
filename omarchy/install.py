#!/usr/bin/env python3
"""Installation script for the Omarchy desktop layer.

Omarchy owns the Hyprland desktop; this topic only layers the dotfiles'
own design system and tool choices on top of it, in the three places
Omarchy documents as user-owned:

* ``~/.config/omarchy/themes/`` — the LSD Warm Dark and Light themes,
  generated from the same palette as the Ghostty, Zed and Claude themes.
* ``~/.config/hypr/lsimons.lua`` — extra keybindings for the TUIs this
  repo installs, required from ``hyprland.lua`` after Omarchy's defaults.
* Omarchy's default-application selection, pointed at the terminal and
  editor these dotfiles actually install.
* The font size in Omarchy's own ``~/.config/foot/foot.ini``, when the
  machine config asks for one (``omarchy.terminalFontSize``).

Nothing here writes to ``/usr/share/omarchy``, and nothing replaces a
stock config file, so ``omarchy update`` and ``omarchy refresh`` keep
working. The one exception is the single ``require`` line appended to
``~/.config/hypr/hyprland.lua``; ``omarchy refresh hyprland`` drops it,
and the next run of this installer puts it back.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    OMARCHY_ROOT,
    XDG_CONFIG_HOME,
    command_exists,
    dry,
    get_omarchy_config,
    info,
    is_dry_run,
    is_omarchy,
    link_directory,
    link_file,
    make_dir,
    parse_dry_run,
    run_cmd,
    success,
    warn,
    write_file,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backgrounds import theme_background

TOPIC_DIR = Path(__file__).resolve().parent

# Theme directory names double as Omarchy's theme slugs.
THEMES = ["lsd-warm-dark", "lsd-warm-light"]
DEFAULT_THEME = "lsd-warm-dark"

HYPR_DIR = XDG_CONFIG_HOME / "hypr"
HYPR_MODULE = "lsimons"
HYPR_ENTRYPOINT = HYPR_DIR / "hyprland.lua"
HYPR_REQUIRE_LINE = f'require("hypr.{HYPR_MODULE}")'

# Omarchy's default-app choices, most preferred first. Each is only
# applied if the program is actually installed — on aarch64 neither
# Ghostty nor Zed has a build, and pointing Omarchy at a missing binary
# is worse than leaving its own default (foot / nvim) in place.
TERMINAL_PREFERENCE = [("ghostty", "ghostty")]
EDITOR_PREFERENCE = [("zeditor", "zed")]

# foot is Omarchy's stock terminal. Its config is Omarchy's file, not
# ours, so only the size attribute of the `font=` line is touched — the
# same line `omarchy-font-set` rewrites (and resets to size 9, which is
# why the next install run has to put the size back).
FOOT_CONFIG = XDG_CONFIG_HOME / "foot" / "foot.ini"
FOOT_FONT_LINE = re.compile(r"^font=(?P<family>[^:\n]*)(?P<attrs>(?::[^\n]*)?)$", re.MULTILINE)
FOOT_SIZE_ATTR = re.compile(r":size=[0-9.]+")


def install_themes():
    """Symlink each theme into ~/.config/omarchy/themes/<slug>."""
    themes_dir = OMARCHY_ROOT / "themes"
    make_dir(themes_dir)
    for slug in THEMES:
        link_directory(TOPIC_DIR / "themes" / slug, themes_dir / slug)


def install_backgrounds():
    """Render each theme's background into Omarchy's user backgrounds dir.

    Not into the theme directory itself: that is a symlink into this
    repository, and a generated PNG there would show up as an untracked
    file on every install. Omarchy looks in
    ``~/.config/omarchy/backgrounds/<slug>/`` as well, which is exactly
    the escape hatch for this.
    """
    for slug in THEMES:
        destination = OMARCHY_ROOT / "backgrounds" / slug / f"{slug}.png"
        colors_toml = TOPIC_DIR / "themes" / slug / "colors.toml"

        if is_dry_run():
            dry(f"would render {destination} from {colors_toml.name}")
            continue

        png = theme_background(colors_toml)
        if destination.exists() and destination.read_bytes() == png:
            success(f"Background for {slug} already up to date")
            continue

        make_dir(destination.parent)
        destination.write_bytes(png)
        success(f"Rendered {destination}")


def install_hypr_module():
    """Link the Hyprland layer and make hyprland.lua require it."""
    link_file(TOPIC_DIR / "hypr" / f"{HYPR_MODULE}.lua", HYPR_DIR / f"{HYPR_MODULE}.lua")

    if not HYPR_ENTRYPOINT.exists():
        warn(f"{HYPR_ENTRYPOINT} does not exist; not adding {HYPR_REQUIRE_LINE}")
        return

    content = HYPR_ENTRYPOINT.read_text()
    if HYPR_REQUIRE_LINE in content:
        success(f"{HYPR_ENTRYPOINT.name} already requires hypr.{HYPR_MODULE}")
        return

    if is_dry_run():
        dry(f"would append {HYPR_REQUIRE_LINE} to {HYPR_ENTRYPOINT}")
        return

    separator = "" if content.endswith("\n") else "\n"
    write_file(
        HYPR_ENTRYPOINT,
        f"{content}{separator}\n"
        "-- Added by omarchy/install.py: personal Hyprland layer from the\n"
        "-- dotfiles. Loaded last, so it only adds to everything above.\n"
        f"{HYPR_REQUIRE_LINE}\n",
    )
    success(f"Added {HYPR_REQUIRE_LINE} to {HYPR_ENTRYPOINT}")


def _omarchy_default(kind, command, value):
    """Point `omarchy default <kind>` at `value`, if `command` is installed.

    Goes through the omarchy CLI rather than writing its state files
    directly: the editor and terminal defaults live in different
    directories (state vs. config), and that is Omarchy's business to
    know, not this installer's.
    """
    if not command_exists(command):
        info(f"{command} is not installed; leaving the Omarchy default {kind} alone")
        return False

    current = run_cmd(
        ["omarchy", "default", kind], check=False, capture_output=True
    )
    if (current.stdout or "").strip() == value:
        success(f"Omarchy default {kind} is already {value}")
        return True

    if is_dry_run():
        dry(f"would run: omarchy default {kind} {value}")
        return True

    result = run_cmd(
        ["omarchy", "default", kind, value], check=False, capture_output=True
    )
    if result.returncode != 0:
        warn(f"Could not set the Omarchy default {kind}: {(result.stderr or '').strip()}")
        return False
    success(f"Omarchy default {kind} set to {value}")
    return True


def configure_defaults():
    for kind, preference in (
        ("terminal", TERMINAL_PREFERENCE),
        ("editor", EDITOR_PREFERENCE),
    ):
        for command, value in preference:
            if _omarchy_default(kind, command, value):
                break


def foot_config_with_font_size(content, size):
    """Return `content` with the first `font=` line's size set to `size`.

    fontconfig syntax: `Family:size=9:weight=bold`. An existing size is
    replaced in place; a line without one gets `:size=` appended.
    Returns the content unchanged when there is no `font=` line at all.
    """
    match = FOOT_FONT_LINE.search(content)
    if not match:
        return content
    attrs = match.group("attrs")
    if FOOT_SIZE_ATTR.search(attrs):
        attrs = FOOT_SIZE_ATTR.sub(f":size={size}", attrs, count=1)
    else:
        attrs = f"{attrs}:size={size}"
    return content[: match.start()] + f"font={match.group('family')}{attrs}" + content[match.end() :]


def configure_terminal_font_size():
    """Apply `omarchy.terminalFontSize` from the machine config to foot."""
    size = get_omarchy_config().get("terminalFontSize")
    if size is None:
        return
    if not FOOT_CONFIG.exists():
        warn(f"{FOOT_CONFIG} does not exist; not setting the foot font size")
        return

    content = FOOT_CONFIG.read_text()
    updated = foot_config_with_font_size(content, size)
    if updated == content and not FOOT_FONT_LINE.search(content):
        warn(f"{FOOT_CONFIG} has no font= line; not setting the foot font size")
        return
    if updated == content:
        success(f"foot font size is already {size}")
        return

    if is_dry_run():
        dry(f"would set font size {size} in {FOOT_CONFIG}")
        return
    write_file(FOOT_CONFIG, updated)
    success(f"Set foot font size to {size} in {FOOT_CONFIG} (new windows only)")


def current_theme():
    result = run_cmd(["omarchy", "theme", "current"], check=False, capture_output=True)
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip().lower().replace(" ", "-")


def apply_theme():
    """Switch to the LSD Warm theme, unless one of ours is already active.

    Checking first keeps a deliberate dark/light switch from being undone
    by the next install run — the pair counts as already applied.
    """
    if is_dry_run():
        dry(f"would apply the {DEFAULT_THEME} theme if no LSD Warm theme is active")
        return

    active = current_theme()
    if active in THEMES:
        success(f"Omarchy theme is already {active}")
        return

    result = run_cmd(
        ["omarchy", "theme", "set", DEFAULT_THEME], check=False, capture_output=True
    )
    if result.returncode != 0:
        warn(f"Could not apply the {DEFAULT_THEME} theme: {(result.stderr or '').strip()}")
        return
    success(f"Applied the {DEFAULT_THEME} theme")


def main():
    parse_dry_run()

    if not is_omarchy():
        info("Omarchy is not installed on this machine; skipping the desktop layer")
        return 0

    info("Installing the Omarchy desktop layer...")

    install_themes()
    install_backgrounds()
    install_hypr_module()
    configure_terminal_font_size()

    if not command_exists("omarchy"):
        warn("The omarchy CLI is not on PATH; skipping defaults and theme")
        return 0

    configure_defaults()
    apply_theme()
    return 0


if __name__ == "__main__":
    sys.exit(main())
