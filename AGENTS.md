# Instructions for AI agents (Claude Code, Codex, …)

You are helping a Victoria 3 modder map how their script content connects. The tool is v3tree (this repository). It indexes the game and mods mechanically; **you** decide which neighbours belong to the user's theme, and you write every decision down with a reason.

Reply in the language the user writes in. The docs come in English (`docs/en/`) and Chinese (`docs/zh/`).

## Hard rules

- Never modify anything inside the game folder or any mod folder. v3tree only reads them. You write only to the config file (`config/local.json`) and the output folder.
- Every connection you state must come from the index (an edge with file:line). If you believe two things are linked but the index has no edge, it can only be a *soft edge*: name the shared object and both locations, and record it in the decisions file.
- Write every judgment into the case's `decisions.txt` with a reason. Do not judge anything "in your head".
- Do not start the game.

## Opening sequence

1. Read this file, `docs/en/judging-guide.md` and `docs/en/config.md` (or the `docs/zh/` versions).
2. **Setup.** Check whether `config/local.json` exists and passes `python run.py doctor` (from the repository root; after `pip install -e .` the command `v3tree` works anywhere).
   - If not, ask the user in one message: the game install folder; the mod folder(s) in load order, or whether to take the launcher playset; the localisation languages (e.g. `simp_chinese,english`); interface language (`en`/`zh`). Then run the **non-interactive** form (never pipe answers into the interactive one):
     `python run.py init --game "<game folder>" --mod "<mod 1>" --mod "<mod 2>" --languages simp_chinese,english --ui en`
     or `python run.py init --game "<game folder>" --playset --ui en` to take the launcher's playset. `--game ""` means no vanilla. Use forward slashes or quote backslash paths. Output goes to `<repository>/output` unless you pass `--output`.
   - `init` runs the check itself and **does not save** a configuration with errors (exit code 2). Exit 0 = all good, 1 = notes only (fine to continue).
   - At least one path (the game or one mod) is required. With several mods, show the load order and ask the user to confirm it: **earlier loads first, later overrides earlier.**
   - Report the doctor output as it is. If it says ERR, stop and let the user fix it.
   - Then build the index: `python run.py index` (about 10–30 seconds).
3. **Ask what the user wants** (one message):
   - the root: a journal entry, event or decision id, or a country tag (then every JE/event/decision that writes `c:TAG` becomes a root);
   - the theme in one sentence, e.g. "the X civil war and its direct consequences";
   - who the map is for: their own overview, or explaining the system to someone else (this decides how wide the boundary is).
4. **Ask about boundaries** in one message. Give each item a one-line explanation and its default; the user may answer "defaults":

   | Question | Why it matters | Default |
   |---|---|---|
   | Include vanilla content? | Vanilla helpers and events show up everywhere and make the map large. | When a mod is loaded: vanilla definitions no mod changes are tools (out) or boundary; vanilla content a mod overrides is judged like mod content. With no mod: vanilla is the content. |
   | How far do countries and characters go? | Expanding a country pulls in everything that mentions it. | Countries and character templates are boundary nodes (drawn, not expanded). |
   | Draw variables as nodes? | They show who writes and who reads, but double the node count. | Yes; the map can hide them by type. |
   | Generic laws, cultures, ideologies? | They are referenced hundreds of times, usually as parameters. | Laws the theme reads are boundary; cultures and ideologies are not drawn; "the same group of pops" is shown as a soft edge. |
   | How far do soft edges go? | A soft edge is "one side writes X, the other reads X". | Candidates appear for shared objects that are not in theme (boundary objects included, since their other readers lie outside the map). Confirm only links that matter; reject families with wildcards such as `soft no *\|*\|law:*`. |

5. **Work.**
   - `python run.py new NAME ROOT "THEME"` creates `output/cases/NAME/` with `case.json` and `decisions.txt` (default rules already in it).
   - Loop: `python run.py expand NAME` → judge what it lists → append to `decisions.txt` → `expand` again. **Stop only when one `expand` run shows both `pending=0` and `soft_undecided=0`**: confirming a soft edge or judging a node `in` adds new neighbours, so always run `expand` once more after your last judgments. Typical systems take 3–8 rounds; use rules for clear families.
   - Reading `expand` output (also saved as `output/cases/NAME/pending.json`):
     ```
     == common/scripted_effects/my_file.txt                     <- file where the pending nodes are defined
       seffect:my_effect 「Name」 i3/o12 <- je:root out [outcome 1 (success) · effect] common/journal_entries/x.txt:40 (+2)
     ```
     `== -` groups nodes that have no definition file (variables, pop objects, undefined targets). `KEY` then the localised name (shortened to 24 characters here; full names are in `pending.json`), `i3/o12` = 3 incoming and 12 outgoing edges in the whole index (high numbers = hub), then the first edge that found it: which judged node, `out` (the judged node points to it) / `in` (it points to the judged node) / `soft`, the context in brackets, file:line; `(+2)` = two more edges from judged nodes.
     `S writer|reader|object` lines are soft-edge candidates with `W` (where it is written) and `R` (where it is read). Answer them with `soft yes|no …` lines; wildcards: `soft no *|*|law:*`.
   - The summary counts (`in`, `boundary`) include nodes judged by rules, the default rules too. In rules, `id_regex` matches the bare id (`my_effect`), `key_regex` the full key (`seffect:my_effect`).
   - Node type names for rules (`type=…`): `je event decision button bar law dp wargoal modifier var gvar onaction seffect strigger svalue tag chartemplate culture pop customloc history movement govtype dynname party ideology lawgroup socialclass socialhier formation treaty …` (the prefix of every node key).
   - Localised names are printed in UTF-8. If your shell shows garbled names, set `PYTHONIOENCODING=utf-8` (or `chcp 65001` on Windows), or read `pending.json`.
   - `python run.py render NAME` writes `map.html` (double-click to open), `report.md`, `subgraph.json`. It warns if neighbours are still pending (the map is then incomplete).
   - Alternatively the user can do it by hand in the web interface (`python run.py serve`, or `start.bat`); both write the same decisions file, so you can continue each other's work.
6. **Report back:** where the map and report are; node and edge counts (in theme / boundary / hard / soft); unresolved count; spot check and reverse check results; the suspected problems the report lists (only list them, do not fix the mod unless asked). The `render` summary fields:
   - `hard` / `soft`: edges after merging the same node pair and context; several confirmed soft pairs through one shared object on the map become one dashed line;
   - `reverse_unexplained`: places where an in-theme id appears in the source but no edge explains it (possible index gaps; see report section 6);
   - `spot_ok`/`spot_n`: random edges whose target id was found on the cited source lines;
   - `findings`: suspected problems in report section 8 (written but never read, read but never written, never fired, never called, tooltip only, disabled branch);
   - `pending`: undecided neighbours left.

## Example questions

Setup (step 2): "Where is Victoria 3 installed, and which mod folders should I load, in load order (the first loads first, later ones override earlier ones)? Or shall I take your launcher's current playset? Which localisation languages should names come from (for example simp_chinese, then english)? Interface language: English or Chinese?"

Root and theme (step 3): "Which journal entry, event or decision should the map start from (or a country tag)? In one sentence, what is the theme, for example 'the X civil war and its direct consequences'? Is the map for your own overview, or to explain the system to someone else?"

Boundaries (step 4): ask the five questions in the table, each with its one-line reason and default, and end with "Reply 'defaults' to accept all of them."

## While judging

- Judge by what a node does and what starts it, **not by which file it is defined in**.
- Prefer rules (`rule ID VERDICT type=… file_regex=… # reason`) for clear families; write per-node lines for everything that needs a look.
- Hubs (a variable or trigger read by dozens of systems) are usually boundary, not in-theme; making them in-theme pulls in unrelated systems.
- If the reverse check in the report lists occurrences the index did not explain, decide whether it is an index gap or the same name used for a different object. Index gaps get reported (or fixed in `src/v3tree/index.py` if the user wants); never patch them by hand-adding edges.
