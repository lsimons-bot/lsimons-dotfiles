"""Tests for the Omarchy desktop layer.

The topic writes into config Omarchy also owns, so these cover the
things that would be expensive to discover on a live desktop: a theme
missing a colour key its templates expand, the hyprland.lua require line
being appended more than once, and the foot font-size edit touching
anything other than the size attribute of the `font=` line.
"""

import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "script"))

import helpers


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


omarchy = load_module("dotfiles_omarchy", REPO_ROOT / "omarchy" / "install.py")
backgrounds = load_module("dotfiles_omarchy_bg", REPO_ROOT / "omarchy" / "backgrounds.py")

THEMES_DIR = REPO_ROOT / "omarchy" / "themes"

# Every key the stock themes define. Omarchy expands these in
# default/themed/*.tpl, and a theme that omits one renders a config with
# an empty value rather than failing, so assert on the whole set.
REQUIRED_COLOR_KEYS = {
    "mode",
    "accent",
    "selection",
    "muted",
    "background",
    "dark_background",
    "darker_background",
    "lighter_background",
    "foreground",
    "dark_foreground",
    "light_foreground",
    "bright_foreground",
    "red",
    "yellow",
    "orange",
    "green",
    "cyan",
    "blue",
    "magenta",
    "brown",
    "bright_red",
    "bright_yellow",
    "bright_green",
    "bright_cyan",
    "bright_blue",
    "bright_magenta",
}


def load_colors(slug):
    return tomllib.loads((THEMES_DIR / slug / "colors.toml").read_text())


class ThemeContentTests(unittest.TestCase):
    def test_every_theme_defines_every_key_the_templates_expand(self):
        for slug in omarchy.THEMES:
            with self.subTest(theme=slug):
                self.assertEqual(set(load_colors(slug)), REQUIRED_COLOR_KEYS)

    def test_colors_are_six_digit_hex(self):
        for slug in omarchy.THEMES:
            colors = load_colors(slug)
            for key, value in colors.items():
                if key == "mode":
                    continue
                with self.subTest(theme=slug, key=key):
                    self.assertRegex(value, r"^#[0-9a-f]{6}$")

    def test_modes_are_declared_and_distinct(self):
        self.assertEqual(load_colors("lsd-warm-dark")["mode"], "dark")
        self.assertEqual(load_colors("lsd-warm-light")["mode"], "light")

    def test_ansi_colors_match_the_ghostty_themes(self):
        """The palette has one source; the two theme formats must agree."""
        ghostty_to_colors = {
            1: "red",
            2: "green",
            3: "yellow",
            4: "blue",
            5: "magenta",
            6: "cyan",
            9: "bright_red",
            10: "bright_green",
            11: "bright_yellow",
            12: "bright_blue",
            13: "bright_magenta",
            14: "bright_cyan",
        }
        for slug, ghostty_file in (
            ("lsd-warm-dark", "LSD-Warm-Dark.symlink"),
            ("lsd-warm-light", "LSD-Warm-Light.symlink"),
        ):
            palette = {}
            for line in (REPO_ROOT / "ghostty" / ghostty_file).read_text().splitlines():
                key, _, value = line.partition("=")
                if key.strip() != "palette":
                    continue
                index, _, color = value.partition("=")
                palette[int(index)] = color.strip()

            colors = load_colors(slug)
            for index, key in ghostty_to_colors.items():
                with self.subTest(theme=slug, key=key):
                    self.assertEqual(colors[key], palette[index])
            self.assertEqual(colors["foreground"], _ghostty_value(ghostty_file, "foreground"))
            self.assertEqual(colors["background"], _ghostty_value(ghostty_file, "background"))


def _ghostty_value(ghostty_file, key):
    for line in (REPO_ROOT / "ghostty" / ghostty_file).read_text().splitlines():
        name, _, value = line.partition("=")
        if name.strip() == key:
            return value.strip()
    raise AssertionError(f"{key} not found in {ghostty_file}")


class BackgroundTests(unittest.TestCase):
    def test_output_is_a_png_of_the_declared_size(self):
        png = backgrounds.gradient_png("#000000", "#ffffff", width=8, height=4)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", png[16:24])
        self.assertEqual((width, height), (8, 4))

    def test_gradient_runs_between_the_two_colors(self):
        png = backgrounds.gradient_png("#102030", "#405060", width=2, height=3)
        rows = _decode_rows(png, width=2, height=3)
        self.assertEqual(rows[0][:3], (0x10, 0x20, 0x30))
        self.assertEqual(rows[-1][:3], (0x40, 0x50, 0x60))
        # Every pixel in a row is the same colour: this is a vertical ramp.
        self.assertEqual(rows[0][:3], rows[0][3:6])

    def test_dark_and_light_themes_ramp_in_opposite_directions(self):
        """The darkest end belongs at the top in dark mode, bottom in light."""
        for slug in omarchy.THEMES:
            colors = load_colors(slug)
            png = backgrounds.theme_background(THEMES_DIR / slug / "colors.toml")
            rows = _decode_rows(png, width=backgrounds.WIDTH, height=backgrounds.HEIGHT)
            top = _hex(rows[0][:3])
            bottom = _hex(rows[-1][:3])
            with self.subTest(theme=slug):
                if colors["mode"] == "dark":
                    self.assertEqual(top, colors["darker_background"])
                    self.assertEqual(bottom, colors["background"])
                else:
                    self.assertEqual(top, colors["background"])
                    self.assertEqual(bottom, colors["darker_background"])


def _hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _decode_rows(png, width, height):
    """Return each scanline of a filter-none, 8-bit RGB PNG as a byte tuple."""
    idat = b""
    offset = 8
    while offset < len(png):
        length = struct.unpack(">I", png[offset : offset + 4])[0]
        tag = png[offset + 4 : offset + 8]
        if tag == b"IDAT":
            idat += png[offset + 8 : offset + 8 + length]
        offset += 12 + length

    raw = zlib.decompress(idat)
    stride = width * 3 + 1
    rows = []
    for y in range(height):
        line = raw[y * stride : (y + 1) * stride]
        assert line[0] == 0, "expected filter type none"
        rows.append(tuple(line[1:]))
    return rows


class HyprModuleTests(unittest.TestCase):
    def setUp(self):
        helpers.set_dry_run(False)

    def test_require_line_is_appended_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            hypr_dir = Path(tmp) / "hypr"
            hypr_dir.mkdir()
            entrypoint = hypr_dir / "hyprland.lua"
            entrypoint.write_text('require("default.hypr.omarchy")\n')

            with mock.patch.object(omarchy, "HYPR_DIR", hypr_dir), mock.patch.object(
                omarchy, "HYPR_ENTRYPOINT", entrypoint
            ), mock.patch.object(omarchy, "link_file") as link:
                omarchy.install_hypr_module()
                first = entrypoint.read_text()
                omarchy.install_hypr_module()
                second = entrypoint.read_text()

        link.assert_called()
        self.assertEqual(first, second)
        self.assertEqual(first.count(omarchy.HYPR_REQUIRE_LINE), 1)
        # Omarchy's own defaults must still load first.
        self.assertLess(
            first.index("default.hypr.omarchy"), first.index(omarchy.HYPR_REQUIRE_LINE)
        )

    def test_missing_entrypoint_warns_instead_of_creating_one(self):
        """A hyprland.lua we did not write is Omarchy's to create, not ours."""
        with tempfile.TemporaryDirectory() as tmp:
            hypr_dir = Path(tmp) / "hypr"
            entrypoint = hypr_dir / "hyprland.lua"
            with mock.patch.object(omarchy, "HYPR_DIR", hypr_dir), mock.patch.object(
                omarchy, "HYPR_ENTRYPOINT", entrypoint
            ), mock.patch.object(omarchy, "link_file"):
                omarchy.install_hypr_module()
            self.assertFalse(entrypoint.exists())


FOOT_INI = """\
[main]
include=~/.local/state/omarchy/current/theme/foot.ini
font=JetBrainsMono Nerd Font:size=9
pad=14x14

[cursor]
style=block
"""


class FootFontSizeTests(unittest.TestCase):
    def setUp(self):
        helpers.set_dry_run(False)

    def run_with(self, foot_ini, config):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "foot.ini"
            if foot_ini is not None:
                path.write_text(foot_ini)
            with mock.patch.object(omarchy, "FOOT_CONFIG", path), mock.patch.object(
                omarchy, "get_omarchy_config", return_value=config
            ):
                omarchy.configure_terminal_font_size()
            return path.read_text() if path.exists() else None

    def test_replaces_only_the_size_attribute(self):
        result = self.run_with(FOOT_INI, {"terminalFontSize": 14})
        self.assertEqual(result, FOOT_INI.replace(":size=9", ":size=14"))

    def test_is_idempotent(self):
        once = self.run_with(FOOT_INI, {"terminalFontSize": 14})
        twice = self.run_with(once, {"terminalFontSize": 14})
        self.assertEqual(once, twice)

    def test_appends_a_size_when_the_font_line_has_none(self):
        result = omarchy.foot_config_with_font_size("font=Iosevka:weight=bold\n", 12)
        self.assertEqual(result, "font=Iosevka:weight=bold:size=12\n")

    def test_leaves_foot_alone_without_a_machine_setting(self):
        self.assertEqual(self.run_with(FOOT_INI, {}), FOOT_INI)

    def test_does_not_create_a_missing_foot_ini(self):
        """foot.ini is Omarchy's file to create, not ours."""
        self.assertIsNone(self.run_with(None, {"terminalFontSize": 14}))


class SkipWhenNotOmarchyTests(unittest.TestCase):
    def test_main_is_a_no_op_without_omarchy(self):
        with mock.patch.object(omarchy, "parse_dry_run"), mock.patch.object(
            omarchy, "is_omarchy", return_value=False
        ), mock.patch.object(omarchy, "install_themes") as themes:
            self.assertEqual(omarchy.main(), 0)
        themes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
