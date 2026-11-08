# How it works

## 1. Layers and files

The config gives the game and the mods in load order. Each becomes a layer: `game`, `mod1`, `mod2`, …

| Situation | What v3tree does | Basis |
|---|---|---|
| Same relative file path in several layers | The later layer's file replaces the earlier one entirely | Standard behaviour; mods rely on it to replace vanilla files |
| Files of one folder | All layers together, read in file-name order | Assumed (Jomini engine convention; no document in the game folder) |
| `REPLACE:`, `TRY_REPLACE:`, `REPLACE_OR_CREATE:` | The whole definition is replaced; the old site is listed as "replaced" | Paradox's published notes; not proven by a file in the game folder |
| `INJECT:`, `TRY_INJECT:`, `INJECT_OR_CREATE:` | Merged into the existing definition; both sites are walked | Same |
| Same name, no prefix | **First loaded definition wins**; the later site is listed as "ignored" and reported as a duplicate | Not proven. Evidence: Community Mod Framework names override files `00_com_…` so they load before vanilla, which only works if the first wins |
| Same-name on_actions | All definitions are merged (event lists add up) | Mods routinely add to `on_monthly_pulse_country` from several files |
| Localisation | Later keys win; `localization/<lang>/replace/` wins over normal files | Common convention |

## 2. The index

Every definition in about 40 folders (journal entries, events, decisions, buttons, progress bars, laws, diplomatic plays, war goals, modifiers, on_actions, scripted effects/triggers/values, history, character templates, government types, parties, …) is parsed and walked. Each reference becomes an edge:

- **call**: effects, event options, outcomes, button effects, `trigger_event`, `random_events`, `add_journal_entry`, scripted effects, writing variables, adding modifiers, enacting laws, moving pops;
- **read** (condition): triggers, `possible`, `is_shown`, `limit`, value blocks reading JEs, variables, laws, scripted triggers, script values;
- **structure**: a journal entry's buttons and progress bars.

Each edge records file, line (and end line for blocks), the context ("outcome 2 (failure) · effect", "option 3", "monthly pulse random 10/220", "after 5 days"), and flags (`tooltip_only`, `disabled`).

Special cases handled:

- Parameterised scripted effects: `$PARAM$` is filled in from every call site; the edge goes from the caller and notes the call site.
- Pops: the filter of a pop iteration (including the scripted triggers it uses) becomes a *pop object*; moving or converting pops writes it. Pops saved into a variable and moved later count too.
- Inline values such as `"scripted_bar_progress(bar)"`.
- Multi-line blocks: `trigger_event = {` newline `id = x }` is one edge spanning those lines.

Anything that cannot be resolved without running the game (scope targets, values held in variables, parameters no caller supplies) goes to `unresolved.md`. Nothing is guessed.

## 3. Two ways to build a map

**Judged (AI or person, command line).** `expand` lists every neighbour of every in-theme node that has no verdict yet. You judge them in `decisions.txt` until nothing is pending. Precise, explainable, slower.

**Step search (web interface or `v3tree search`).** From the root, take N steps along references. Stop rules keep it from swallowing the whole game: nodes referenced more than N times (default 40), countries, characters, cultures, laws, ideologies, engine on_actions, and (when a mod is loaded) vanilla-only definitions are drawn but not expanded. You accept, draw-only, or remove nodes and search further; signing off turns undecided nodes into in-theme and stop-rule nodes into boundary. Fast; the boundary is only as good as your pruning.

Both write the same decisions file, so you can switch between them.

## 4. The report

- Index and subtree numbers, unresolved references touching the map.
- Soft edges confirmed and rejected, with reasons.
- Every judgment with its reason and source (per-node line or rule).
- **Reverse check:** each in-theme id is searched in the raw script text; occurrences no edge explains are listed.
- **Spot check:** 10 random edges, checked against the source line.
- **Suspected problems:** variables written but never read (and not shown in localisation or GUI), read but never written, events nothing fires, helpers nothing calls, effects only in `show_as_tooltip`, branches under `always = no`.
