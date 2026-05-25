#!/usr/bin/env python3
"""Serve lsd-colors.html with autosave-back-to-disk.

Usage:
  ./colors/serve.py              # binds to 127.0.0.1:8765, opens browser
  ./colors/serve.py --no-open    # don't open browser
  PORT=9000 ./colors/serve.py    # custom port

The page POSTs its current HTML to /save whenever an OKLCH value is edited.
The server validates the payload is a single HTML document and writes it
atomically (temp file + rename) to colors/lsd-colors.html. After each
successful save it regenerates colors/lsd-colors.md — a flat name→hex
summary for tooling/humans that don't want to open a browser.

Stdlib only. Binds to 127.0.0.1 so the save endpoint isn't reachable from
the network.
"""

from __future__ import annotations

import argparse
import http.server
import json
import math
import os
import re
import sys
import webbrowser
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET_HTML = HERE / "lsd-colors.html"
TARGET_MD = HERE / "lsd-colors.md"
TARGET_JSON = HERE / "lsd-colors.json"
DEFAULT_PORT = 8765


# --- OKLCH → hex ---------------------------------------------------------

_OKLCH_RE = re.compile(
    r"^\s*(-?\d*\.?\d+)\s*%?\s+(-?\d*\.?\d+)\s+(-?\d*\.?\d+)\s*°?\s*$"
)


def _lin_to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def oklch_to_hex(text: str) -> str | None:
    """Parse 'L% C H' (degrees) and return '#rrggbb', clamped to sRGB gamut."""
    m = _OKLCH_RE.match(text.strip().replace("oklch(", "").replace(")", ""))
    if not m:
        return None
    L = float(m.group(1)) / 100
    C = float(m.group(2))
    H = float(m.group(3))
    h = math.radians(H)
    a = C * math.cos(h)
    b = C * math.sin(h)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    lr = l_ ** 3
    lg = m_ ** 3
    lb_ = s_ ** 3
    r = 4.0767416621 * lr - 3.3077115913 * lg + 0.2309699292 * lb_
    g = -1.2684380046 * lr + 2.6097574011 * lg - 0.3413193965 * lb_
    bl = -0.0041960863 * lr - 0.7034186147 * lg + 1.7076147010 * lb_
    rs = max(0.0, min(1.0, _lin_to_srgb(r)))
    gs = max(0.0, min(1.0, _lin_to_srgb(g)))
    bs = max(0.0, min(1.0, _lin_to_srgb(bl)))
    return f"#{round(rs * 255):02x}{round(gs * 255):02x}{round(bs * 255):02x}"


# --- HTML → rows ---------------------------------------------------------


class _PaletteParser(HTMLParser):
    """Pull (h2, h3, name, oklch, desc) tuples out of lsd-colors.html."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self._h2 = None
        self._h3 = None
        self._in_h2 = False
        self._in_h3 = False
        self._in_table = False
        self._in_textarea = False
        self._in_desc = False
        self._row = None
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h2":
            self._in_h2 = True
            self._buf = ""
        elif tag == "h3":
            self._in_h3 = True
            self._buf = ""
        elif tag == "table" and "data-palette" in a:
            self._in_table = True
        elif tag == "tr" and self._in_table and "data-name" in a:
            self._row = {"name": a["data-name"], "oklch": "", "desc": ""}
        elif tag == "textarea" and self._row is not None:
            self._in_textarea = True
            self._buf = ""
        elif (
            tag == "td"
            and self._row is not None
            and "desc" in (a.get("class") or "").split()
        ):
            self._in_desc = True
            self._buf = ""

    def handle_endtag(self, tag):
        if tag == "h2" and self._in_h2:
            self._h2 = self._buf.strip()
            self._h3 = None
            self._in_h2 = False
        elif tag == "h3" and self._in_h3:
            self._h3 = self._buf.strip()
            self._in_h3 = False
        elif tag == "table":
            self._in_table = False
        elif tag == "textarea" and self._in_textarea:
            self._row["oklch"] = self._buf.strip()
            self._in_textarea = False
        elif tag == "td" and self._in_desc:
            self._row["desc"] = self._buf.strip()
            self._in_desc = False
        elif tag == "tr" and self._row is not None:
            self.rows.append(
                {**self._row, "h2": self._h2, "h3": self._h3}
            )
            self._row = None

    def handle_data(self, data):
        if self._in_h2 or self._in_h3 or self._in_textarea or self._in_desc:
            self._buf += data


def extract_palette(html: str) -> list[dict]:
    p = _PaletteParser()
    p.feed(html)
    return p.rows


# --- Markdown writer -----------------------------------------------------


def render_markdown(rows: list[dict]) -> str:
    """Group rows by (h2, h3), preserving first-occurrence order."""
    out: list[str] = []
    out.append("# LSD Warm — color names and hex values")
    out.append("")
    out.append(
        "Generated by `colors/serve.py` on every save. The canonical "
        "source is [`lsd-colors.html`](./lsd-colors.html) — open it via "
        "`./colors/serve.py` to edit interactively. A flat machine-readable "
        "version is also written to [`lsd-colors.json`](./lsd-colors.json)."
    )
    out.append("")

    seen_h2: list[str] = []
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        # Skip reference palettes (SBP, Caseum) — they aren't ours to redistribute
        # as flat hex tables. They stay in lsd-colors.html as visual context only.
        if (r["h2"] or "").startswith("Reference:"):
            continue
        key = (r["h2"] or "", r["h3"] or "")
        if r["h2"] and r["h2"] not in seen_h2:
            seen_h2.append(r["h2"])
        groups.setdefault(key, []).append(r)

    for h2 in seen_h2:
        out.append(f"## {h2}")
        out.append("")
        h3s_in_h2 = [k[1] for k in groups if k[0] == h2]
        for h3 in h3s_in_h2:
            if h3:
                out.append(f"### {h3}")
                out.append("")
            out.append("| Name | Hex | Description |")
            out.append("| ---- | --- | ----------- |")
            for r in groups[(h2, h3)]:
                hex_value = oklch_to_hex(r["oklch"]) or "?"
                desc = (r["desc"] or "").replace("|", "\\|")
                out.append(f"| `{r['name']}` | `{hex_value}` | {desc} |")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_json(rows: list[dict]) -> str:
    """Flat {variant: {name: "#hex"}} for machine consumption.

    Variant is derived from the last word of the row's h2 ("LSD Warm Light"
    → "light"). Reference palettes (h2 starts with "Reference:") are skipped.
    """
    out: dict = {
        "_meta": {
            "source": "lsd-colors.html",
            "note": "Generated by colors/serve.py on every save.",
        }
    }
    for r in rows:
        h2 = r["h2"] or ""
        if h2.startswith("Reference:") or not h2:
            continue
        variant = h2.strip().split()[-1].lower()
        hex_value = oklch_to_hex(r["oklch"])
        if not hex_value:
            continue
        out.setdefault(variant, {})[r["name"]] = hex_value
    return json.dumps(out, indent=2) + "\n"


def regenerate_outputs(html: str) -> None:
    """Regenerate lsd-colors.md and lsd-colors.json from the just-saved HTML."""
    try:
        rows = extract_palette(html)
    except Exception as e:
        sys.stderr.write(f"[serve] palette extract failed: {e}\n")
        return
    for target, render in (
        (TARGET_MD, render_markdown),
        (TARGET_JSON, render_json),
    ):
        try:
            content = render(rows)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(target)
        except Exception as e:
            # Don't break the save flow if a sidecar fails — just log.
            sys.stderr.write(f"[serve] {target.name} regen failed: {e}\n")


# --- HTTP server ---------------------------------------------------------


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[serve] {fmt % args}\n")

    def do_GET(self):
        # Swallow favicon requests silently — there's no icon file and the
        # 404 + log line are noise.
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if self.path in ("/", ""):
            self.path = "/lsd-colors.html"
        return super().do_GET()

    def log_request(self, code="-", size="-"):
        if "/favicon.ico" in self.requestline:
            return
        super().log_request(code, size)

    def do_POST(self):
        if self.path != "/save":
            self.send_error(404, "only /save accepts POST")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 5 * 1024 * 1024:
            self.send_error(413, "payload missing or too large")
            return
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            html = payload["html"]
            if not isinstance(html, str):
                raise ValueError("'html' must be a string")
            head = html.lstrip()[:64].lower()
            if not head.startswith("<!doctype html"):
                raise ValueError("payload is not a complete HTML document")
            tmp = TARGET_HTML.with_suffix(".html.tmp")
            tmp.write_text(html, encoding="utf-8")
            tmp.replace(TARGET_HTML)
        except Exception as e:
            self.send_error(400, str(e))
            return
        regenerate_outputs(html)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-open", action="store_true", help="don't launch browser")
    ap.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", DEFAULT_PORT)),
        help=f"TCP port (default {DEFAULT_PORT}, or $PORT)",
    )
    args = ap.parse_args()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"editing  {TARGET_HTML}")
    print(f"summary  {TARGET_MD}")
    print(f"json     {TARGET_JSON}")
    print(f"serving  {url}  (Ctrl-C to stop)")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
