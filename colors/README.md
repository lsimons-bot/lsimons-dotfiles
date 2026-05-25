# colors

The active palette across all tooling is **LSD Warm Light** (light) and
**LSD Warm Dark** (dark) — a warm-amber palette. The canonical source
swatch lives in [lsd-colors.html](./lsd-colors.html); open it in a browser
to see every named token rendered inline.

This topic installs [`pastel`](https://github.com/sharkdp/pastel), a CLI
for inspecting and transforming colors, and documents where each tool's
theme lives so the palette stays in sync as it evolves.

## Where the colors live

| Tool | File(s) | Notes |
| ---- | ------- | ----- |
| **Ghostty** (terminal) | `ghostty/Claude-Light.symlink`, `ghostty/Claude-Dark.symlink`, `ghostty/LSD-Warm-Light.symlink`, `ghostty/LSD-Warm-Dark.symlink` | Native ghostty theme files. Selected via `theme = ...` in `ghostty/config.symlink`. Palette is `palette = N=#rrggbb` (16 ANSI slots) plus `background` / `foreground` / `cursor-color` / `selection-*`. |
| **Zed** (editor) | `zed/lsd-warm.json.symlink` | Custom theme JSON containing both `LSD Warm Dark` and `LSD Warm Light` variants. Active theme selected in `zed/settings.json.symlink` (`"theme": ...`). Edit per-token colors under `style.syntax.*`; edit the chrome under the other top-level keys (`background`, `border`, `text`, ...). |
| **Powerlevel10k** (zsh prompt) | `oh-my-zsh/p10k.zsh.symlink` | All ~95 segment foregrounds route through a `local -A clr=(...)` table near the top of the file, populated from the LSD Warm Light palette. See [p10k.COLORS.md](./p10k.COLORS.md) for the full mapping and re-application recipe (after re-running `p10k configure`). |
| **Oh My Zsh** prompt | `oh-my-zsh/powerline10k.zsh` | Loads the p10k config above. |

## Adjusting colors

### Live editing via `serve.py`

For interactive tuning of the LSD palette, run the helper server:

```sh
./colors/serve.py
# or: python3 colors/serve.py --no-open --port 9000
```

It binds to `127.0.0.1:8765`, opens `lsd-colors.html` in your browser, and
autosaves the file every time you edit an OKLCH value. A status pill in
the top-right shows `connected — autosave on` / `saving…` / `saved hh:mm:ss`.
Stop with Ctrl-C.

Implementation: stdlib `http.server`, no extra deps. Writes are atomic
(temp file + rename); listens on loopback only so the save endpoint isn't
reachable from the network. The same file works offline (just open it
directly in a browser) — the status pill shows `offline` and the JS
falls back to in-memory editing without persisting.

### One-off tweaks with `pastel`

`pastel` is the workhorse for inspecting and nudging individual colors.
A few patterns that come up often:

```sh
# Show a color with all its representations (RGB / HSL / Lab / Lch / swatch).
pastel color '#d4a054'

# Darken / desaturate a too-bright color and pipe it back out.
pastel color '#378a20' | pastel darken 0.05 | pastel desaturate 0.1

# Show a whole palette inline.
printf '%s\n' '#1e1408' '#d42020' '#2e7d16' '#1a60c0' | pastel format hex --on-color

# Pick the closest named CSS color (sometimes useful for naming the palette).
pastel color '#c47a14' | pastel format name
```

Once you've found a value you like, edit it in the right file from the
table above and reload the affected tool (ghostty reloads on save; zed
reloads on save; for p10k run `source ~/.zshrc` or open a new shell).

### Coordinated palette changes

The four tools above share a palette by convention, not by linkage —
each has its own file. When changing the palette intentionally:

1. Update the canonical source first: `colors/lsd-colors.html`. It's the
   plain-language palette doc and the only place to edit human-readable
   names alongside hex values.
2. Mirror the changes into `zed/lsd-warm.json.symlink` (richest set of
   named tokens — chrome, syntax, terminal ansi).
3. Mirror the ANSI slots to `ghostty/LSD-Warm-{Light,Dark}.symlink`.
4. Update the `clr` table in `oh-my-zsh/p10k.zsh.symlink` to match.
   p10k segment colors are referenced symbolically through that table,
   so individual segment lines rarely need to change.

For the rationale behind the p10k mapping and how to redo it after a
fresh `p10k configure` run, see [p10k.COLORS.md](./p10k.COLORS.md).

### Switching between Light and Warm Light (or Dark variants)

- **Ghostty:** edit `ghostty/config.symlink`, change the `theme = ...`
  line to one of `Claude Light` / `Claude Dark` / `LSD Warm Light` /
  `LSD Warm Dark`.
- **Zed:** edit `zed/settings.json.symlink`, change `"theme"` to the
  matching theme name.
- **p10k:** the prompt uses no background color (transparent), so it
  inherits the terminal palette and works against both light and dark
  ghostty themes without changes.

## Future ideas

A more interactive editor (load palette → tab between entries → tune
HSB sliders → write back) would be nicer than pastel-pipe iteration.
Two candidate paths if this becomes a recurring need:

- A small [Textual](https://textual.textualize.io/) script that loads
  `clr[...]` and rewrites it in place.
- [`huetone`](https://huetone.ardov.me/) — web tool, doesn't know about
  our files, but the best palette-tuning UX in the wild.
