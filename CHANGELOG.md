# Changelog

## 0.1.0 (2026-11-08)

First standalone release, extracted from the NESND mod's development tools.

- Global reference index of the game plus any number of mods in load order; every edge carries file:line.
- Two ways to build a map: an AI agent judges each neighbour into a decisions file, or a person uses the local web interface (step search, accept / draw-only / remove, sign off).
- Automatic command-line mode (`v3tree search ROOT --steps N`).
- Standalone HTML map, coverage report (spot check, reverse check, suspected problems), subgraph JSON.
- `init` / `doctor` startup check; works without script docs (one diagnostic is skipped).
- Interface and reports in English and Chinese.
