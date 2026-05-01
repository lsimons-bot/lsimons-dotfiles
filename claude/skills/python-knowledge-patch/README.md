# python-knowledge-patch

Vendored skill that patches Claude's Python knowledge with features from
3.13 (Oct 2024) and 3.14 (Oct 2025) — released after the model's training
cutoff.

## Source

- **Upstream**: <https://github.com/Nevaberry/nevaberry-plugins>
- **Path**: `plugins/python-knowledge-patch/skills/python-knowledge-patch/`
- **Commit pin**: `0ff3fc71d471070736e63d3c1c82103be63bf33e`
- **License**: MIT (see [LICENSE.md](LICENSE.md))
- **Author**: Nevaberry

## Local edits

This copy diverges from upstream in minor ways (clarified PEP 758 wording,
deprecations split out from breaking changes, source pin in frontmatter).
When refreshing from upstream, diff against the pinned commit and re-apply.

## Updating

```sh
# Inspect upstream changes since the pin
git -C /tmp clone --depth=50 https://github.com/Nevaberry/nevaberry-plugins.git
git -C /tmp/nevaberry-plugins log 0ff3fc71d471070736e63d3c1c82103be63bf33e..HEAD \
    -- plugins/python-knowledge-patch
```

Then update files here, bump `version` and `metadata.upstream_commit` in
`SKILL.md`, and update the pin above.
