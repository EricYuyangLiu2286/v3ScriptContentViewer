# Changelog

## Unreleased

- Map: **Layout: compact / tree** toggle. Compact (default) wraps long sibling lists and their subtrees into columns so the map fits the window shape; the choice is remembered per browser.
- Web interface: a root can no longer be given Remove or "Draw, don't expand" (it did nothing); its panel explains why.

## 0.1.0 (2026-11-08)

First standalone release, extracted from the NESND mod's development tools.

- Global reference index of the game plus any number of mods in load order; every edge carries file:line.
- Two ways to build a map: an AI agent judges each neighbour into a decisions file, or a person uses the local web interface (step search, accept / draw-only / remove, sign off).
- Automatic command-line mode (`v3tree search ROOT --steps N`).
- Standalone HTML map, coverage report (spot check, reverse check, suspected problems), subgraph JSON.
- `init` / `doctor` startup check; works without script docs (one diagnostic is skipped).
- Interface and reports in English and Chinese.
