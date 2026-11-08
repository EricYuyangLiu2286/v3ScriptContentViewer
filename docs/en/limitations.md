# Limitations

- **Static reading only.** v3tree does not run the game. It cannot tell when a JE's `possible` is checked, whether an on_action is fired by the engine, or what a scope resolves to at run time.
- **Conditions are not evaluated.** `NOT = { has_variable = x }` is recorded as a read of `x`, the same as `has_variable = x`. AND/OR/NOT logic is not modelled.
- **Unproven override rules.** Load order from the launcher, `REPLACE:`/`INJECT:` semantics and "first definition wins" for plain duplicates follow conventions and outside notes, not a file in the game folder. See `how-it-works.md` for the evidence.
- **Not indexed:** country definition fields, GUI files, maps, state and pop history, buildings and production methods. The reverse check lists occurrences in GUI files as unexplained.
- **Folder list.** The indexed folders match game version 1.15. A newer version may add folders; add them under `extra_folders` in the config.
- **Step search boundaries are coarse.** The stop rules are thresholds; a system closely tangled with others needs manual pruning in every round.
- **Context labels are in one language.** Labels inside the index use the interface language at build time; rebuild after switching.
- **No soft edges in step search.** Soft edges are judged only in the decisions file (AI or by hand).
- **Large maps.** Maps over about 1,000 nodes are slow to lay out; fold levels, filter types, or narrow the theme.
- **Script docs are not shipped.** They are game data. Without them, the "unknown key" diagnostic is skipped.
