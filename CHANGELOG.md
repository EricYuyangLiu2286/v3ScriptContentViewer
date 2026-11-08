# Changelog

## Unreleased

- Map: **Layout: compact / tree** toggle. Compact (default) wraps long sibling lists and their subtrees into columns so the map fits the window shape; the choice is remembered per browser.
- Map: **Focus on this node** shows only that node and its neighbours; click a neighbour to walk the chain step by step, with a path bar to go back (Esc steps back).
- Command line: `v3tree near ID [--json]` lists one node's direct neighbours with file:line, for walking a chain without a map.
- Settings: the output folder field shows the default, explains what is stored there, and can move existing sessions and the index to the new folder.
- Deleting a session in a OneDrive (read-only) folder no longer leaves an empty folder behind.
- Web interface: a root can no longer be given Remove or "Draw, don't expand" (it did nothing); its panel explains why.

## 0.1.0 (2026-11-08)

First standalone release, extracted from the NESND mod's development tools.

- Global reference index of the game plus any number of mods in load order; every edge carries file:line.
- Two ways to build a map: an AI agent judges each neighbour into a decisions file, or a person uses the local web interface (step search, accept / draw-only / remove, sign off).
- Automatic command-line mode (`v3tree search ROOT --steps N`).
- Standalone HTML map, coverage report (spot check, reverse check, suspected problems), subgraph JSON.
- `init` / `doctor` startup check; works without script docs (one diagnostic is skipped).
- Interface and reports in English and Chinese.
