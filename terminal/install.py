#!/usr/bin/env python3
"""Installation script for the macOS built-in Terminal.app.

Builds an "LSD Warm Light" Terminal profile that mirrors the Ghostty
theme of the same name (see ghostty/LSD-Warm-Light.symlink) and uses the
same font family and size as the Ghostty config (ghostty/config.symlink).

Terminal stores profiles in the com.apple.Terminal preferences domain
under "Window Settings". Colors are NSColor objects and the font is an
NSFont object, both serialised as NSKeyedArchiver binary plists embedded
as Data. We rebuild those archives here, write a re-importable
``.terminal`` file, then import the profile into the preferences domain
via ``defaults export``/``defaults import`` (which goes through cfprefsd,
avoiding stale-cache problems from editing the plist file directly).
"""

import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path
from plistlib import UID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "script"))
from helpers import (
    XDG_CONFIG_HOME,
    dry,
    error,
    info,
    is_dry_run,
    success,
    write_file,
)

PROFILE_NAME = "LSD Warm Light"
TERMINAL_DOMAIN = "com.apple.Terminal"

DOTFILES_ROOT = Path(__file__).resolve().parent.parent
GHOSTTY_DIR = DOTFILES_ROOT / "ghostty"
GHOSTTY_THEME = GHOSTTY_DIR / "LSD-Warm-Light.symlink"
GHOSTTY_CONFIG = GHOSTTY_DIR / "config.symlink"

# Map a Ghostty/display font family to its macOS PostScript name. Terminal
# stores the PostScript name in the archived NSFont, not the family name.
FONT_POSTSCRIPT_NAMES = {
    "Lilex Nerd Font Mono": "LilexNFM-Regular",
}


def parse_ghostty_config(path):
    """Parse a Ghostty key=value config/theme file into a dict.

    Repeated ``palette`` keys are collected into a list under "palette".
    """
    config = {}
    palette = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "palette":
            # value looks like "0=#241100"
            idx, color = value.split("=", 1)
            palette[int(idx.strip())] = color.strip()
        else:
            config[key] = value
    config["palette"] = palette
    return config


def _hex_to_components(hex_color):
    """Convert ``#rrggbb`` to (r, g, b) floats in the 0..1 range."""
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return r, g, b


def ns_color(hex_color):
    """Build an NSKeyedArchiver NSColor archive (calibrated RGB) as bytes.

    This matches the encoding Terminal itself produces: an NSColor with
    NSColorSpace=1 and an NSRGB Data value of space-separated 0..1
    components terminated by a NUL byte.
    """
    r, g, b = _hex_to_components(hex_color)
    components = f"{r:.10g} {g:.10g} {b:.10g}".encode() + b"\x00"
    archive = {
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {"root": UID(1)},
        "$objects": [
            "$null",
            {"$class": UID(2), "NSColorSpace": 1, "NSRGB": components},
            {"$classname": "NSColor", "$classes": ["NSColor", "NSObject"]},
        ],
    }
    return plistlib.dumps(archive, fmt=plistlib.FMT_BINARY)


def ns_font(postscript_name, size):
    """Build an NSKeyedArchiver NSFont archive as bytes."""
    archive = {
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {"root": UID(1)},
        "$objects": [
            "$null",
            {
                "$class": UID(3),
                "NSName": UID(2),
                "NSSize": float(size),
                "NSfFlags": 16,
            },
            postscript_name,
            {"$classname": "NSFont", "$classes": ["NSFont", "NSObject"]},
        ],
    }
    return plistlib.dumps(archive, fmt=plistlib.FMT_BINARY)


def build_profile():
    """Assemble the Terminal profile dict mirroring the Ghostty theme."""
    theme = parse_ghostty_config(GHOSTTY_THEME)
    config = parse_ghostty_config(GHOSTTY_CONFIG)

    palette = theme["palette"]
    font_family = config.get("font-family", "Lilex Nerd Font Mono")
    font_size = config.get("font-size", "15")
    postscript_name = FONT_POSTSCRIPT_NAMES.get(font_family, font_family)

    ansi_keys = [
        "ANSIBlackColor",
        "ANSIRedColor",
        "ANSIGreenColor",
        "ANSIYellowColor",
        "ANSIBlueColor",
        "ANSIMagentaColor",
        "ANSICyanColor",
        "ANSIWhiteColor",
        "ANSIBrightBlackColor",
        "ANSIBrightRedColor",
        "ANSIBrightGreenColor",
        "ANSIBrightYellowColor",
        "ANSIBrightBlueColor",
        "ANSIBrightMagentaColor",
        "ANSIBrightCyanColor",
        "ANSIBrightWhiteColor",
    ]

    profile = {
        "name": PROFILE_NAME,
        "type": "Window Settings",
        "ProfileCurrentVersion": 2.09,
        "FontAntialias": True,
        "Font": ns_font(postscript_name, font_size),
        "BackgroundColor": ns_color(theme["background"]),
        "TextColor": ns_color(theme["foreground"]),
        "TextBoldColor": ns_color(theme["foreground"]),
        "CursorColor": ns_color(theme["cursor-color"]),
        "CursorTextColor": ns_color(theme["cursor-text"]),
        "SelectionColor": ns_color(theme["selection-background"]),
    }
    for i, key in enumerate(ansi_keys):
        profile[key] = ns_color(palette[i])

    return profile


def import_profile(profile):
    """Import the profile into the Terminal domain and make it default."""
    with tempfile.NamedTemporaryFile(suffix=".plist", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            ["defaults", "export", TERMINAL_DOMAIN, str(tmp_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            error(f"defaults export failed: {result.stderr.strip()}")
            return False

        with open(tmp_path, "rb") as f:
            prefs = plistlib.load(f)

        prefs.setdefault("Window Settings", {})[PROFILE_NAME] = profile
        prefs["Default Window Settings"] = PROFILE_NAME
        prefs["Startup Window Settings"] = PROFILE_NAME

        with open(tmp_path, "wb") as f:
            plistlib.dump(prefs, f, fmt=plistlib.FMT_XML)

        result = subprocess.run(
            ["defaults", "import", TERMINAL_DOMAIN, str(tmp_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            error(f"defaults import failed: {result.stderr.strip()}")
            return False
        return True
    finally:
        tmp_path.unlink(missing_ok=True)


def main():
    # Local import so the module is importable without mutating helpers state.
    from helpers import parse_dry_run

    parse_dry_run()
    info("Installing Terminal.app profile...")

    if not GHOSTTY_THEME.exists() or not GHOSTTY_CONFIG.exists():
        error("Ghostty theme/config not found; cannot mirror the profile")
        return 1

    profile = build_profile()

    # Write a re-importable .terminal file alongside the Ghostty themes layout.
    terminal_file = XDG_CONFIG_HOME / "terminal" / "themes" / f"{PROFILE_NAME}.terminal"
    write_file(terminal_file, plistlib.dumps(profile, fmt=plistlib.FMT_XML).decode())
    success(f"Wrote {terminal_file}")

    if is_dry_run():
        dry(f"would import '{PROFILE_NAME}' into {TERMINAL_DOMAIN}")
        dry(f"would set '{PROFILE_NAME}' as the default and startup profile")
        return 0

    if not import_profile(profile):
        return 1

    success(f"Imported '{PROFILE_NAME}' profile and set it as default")
    return 0


if __name__ == "__main__":
    sys.exit(main())
