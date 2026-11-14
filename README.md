# v3tree: content maps for Victoria 3 mods

[中文说明](README.zh-CN.md)

Give v3tree a journal entry, event or decision (or a country tag). It finds the script content in your mod and the game that connects to it, and draws an interactive map you open by double-clicking. Every line on the map points to the file and line it came from.

It is for modders who have lost track of a large system: chains rewritten many times, or code written by others or by an AI.

![A map in the browser: the selected node's incoming links, each with file:line, on the right](docs/images/map.webp)

- **Mechanical, traceable index.** Parses the game and any number of mods in load order. Calls, condition reads, buttons, progress bars, variables, modifiers, laws, pops… each edge carries file:line. What it cannot resolve is listed, never guessed.
- **You decide the boundary.** A map needs to know what belongs to your theme. Do it by hand in a local web page (search N steps, accept / draw-only / remove, search further, complete), or let an AI agent judge every neighbour with a written reason.
- **Checks itself.** Every report re-checks 10 random edges against the source, searches the raw text for references the index missed, and lists suspected problems (variables written but never read, events nothing fires, effects only shown in tooltips…).
- **Offline, no dependencies.** Python 3.10+ standard library only. The map is one HTML file.

## Before you start

- **Languages.** The interface and reports are in English and Chinese. The map shows `english` and `simp_chinese` localisation; other languages are untested. If you work in another language, ask your AI agent to add it. The interface language and the localisation languages are two separate settings, and names and type labels are stored when the index is built: after changing either, **rebuild the index**.
- **What it maps.** Script content only: journal entries, events, decisions, triggers, effects, variables, modifiers, laws, pop moves, flag definitions and the like. It does not read GUI files, the map, buildings or production methods, and it does not run the game. Don't expect it to pick up everything; see [Limitations](docs/en/limitations.md).
- **Performance.** Maps with many links (roughly 1,000+ nodes, or nodes with heavy fan-out) lag in the browser. Be patient, as we all are with Victoria 3 itself, or fold levels and filter types to lighten the map. **Layout: compact** (the default) wraps long lists into columns so a big map fits the window instead of becoming a thin strip.

## Install

Python 3.10 or newer. Download or clone this repository. That is all; there is nothing else to install.

Run commands from the repository folder as `python run.py <command>`. Optional: `pip install -e .` gives you a `v3tree` command that works anywhere.

## Use it in the browser (no AI needed)

1. Double-click `start.bat` (Windows) or run `./start.sh` (macOS/Linux). Your browser opens.
2. **Settings:** the game install folder and/or your mod folder(s); at least one is required. "Import from launcher" reads your active playset in load order. Save, then **Build index** (10–30 seconds).
3. **New search:** type an id (autocomplete helps) or a country tag, choose the number of steps (1–10), keep or change the stop rules, **Start search**.

   ![New search: autocomplete for the root, stop rules below](docs/images/new-search.png)
4. Click nodes to see their code, file:line and every connection. **Accept**, **Draw, don't expand** or **Remove**; Ctrl-click to select several. **Search further** grows the tree from accepted and undecided nodes. **Undo** steps back.

   **Focus on this node** (in the node panel) hides the rest of the map and shows only that node and its direct neighbours: what calls or reads it on the left, what it calls or reads on the right. Click a node (or its **+**) to open its neighbours beside it; branches you opened before stay on screen, and **−** closes one again. The bar at the top shows the way from the start to the selected node; Esc undoes the last open.

   ![Focus chain: the path walked so far in the bar at the top, the last node's neighbours on the right](docs/images/focus-chain-en.webp)
5. **Complete:** the map, a report and a JSON file are saved in `output/cases/<name>/`. `map.html` opens by double-click, offline.

Everything is saved in the `output` folder inside the tool unless you set **Output folder** in Settings; tick "move the existing index and sessions too" to take your sessions along when you change it.

## Use it with an AI agent

Open the repository folder in Claude Code, Codex or a similar agent and say what you want, e.g. "map the X journal entry; my game is at … and my mod at …". The agent follows [AGENTS.md](AGENTS.md): it sets up and checks the configuration, asks for the root and theme, asks about boundaries (each with an explanation and a default), then judges every neighbour into `decisions.txt` with reasons.

## Command line

```bash
python run.py init                                  # first-time setup (asks questions), then a check
python run.py index                                 # build the index
python run.py search je_acw_countdown --steps 5     # automatic map with stop rules
python run.py new acw je_acw_countdown "The ACW countdown and the war"   # a case to judge
python run.py expand acw                            # list undecided neighbours
python run.py near nesnd_south_holdouts.1          # one node and its direct neighbours, each with file:line (--json for agents)
python run.py render acw                            # map.html + report.md + subgraph.json
python run.py serve                                 # the web interface
```

`examples/vanilla-acw/` holds a first round of judgments for the vanilla ACW countdown. Copy it to `output/cases/acw_example/` and run `expand acw_example`.

## Characters

Rebuild the index after updating. In the web interface, search a character's name or template id and pick the green **Character** node; **Focus on this node** opens it step by step in both directions. The older **character template** nodes can still be looked up on their own.

~~~sh
python run.py index --config config/vanilla.json
python run.py near character:agitator_karl_marx --json --config config/vanilla.json
python run.py person JAP_meiji_yamato --name meiji --context event:meiji.1 --config config/vanilla.json
~~~

`person` exports an offline map.html, subgraph.json, decisions.txt and coverage.json to `cases/NAME` in the configured output folder. The map holds every direct incoming and outgoing edge of the character and of the paths that carry it, each with layer, file and line. `--context` (repeatable) adds stages you have already checked as expansion points; only edges in the index are drawn. The export keeps locations only, not code, so third-party mods can be archived.

Creation blocks in history, events and journal entries, named templates and template-less creations are indexed separately. Scopes are qualified by the event or script that defines them. Variables are slots (countries reuse names), so one slot can hold different people; a character put into a variable list with `add_to_variable_list` is linked to that list, and operations inside `every_in_list` and similar blocks are linked to it too. `charselector` means a runtime search by office or condition; `charstate` means an operation or usage rule. Template, candidate and actual office holder mean different things. Generic random selection, implicit engine succession, script parameters and GUI expressions may not be recoverable statically; follow the locations back to the source. Two entries that happen to share a name are not proof of one person.

## Documents

- [Configuration and the startup check](docs/en/config.md)
- [Judging guide](docs/en/judging-guide.md)
- [How it works](docs/en/how-it-works.md): override rules, what the index records, the report
- [Limitations](docs/en/limitations.md)

## Tests

```bash
python -m unittest discover -s tests
```

The tests build a tiny synthetic game and two mods in a temporary folder; no Paradox files are included in this repository.

## Licence and credits

MIT, see [LICENSE](LICENSE). The script parser (`src/v3tree/clausewitz.py`) comes from the development tools of the *Neo-Era Southern and Northern Dynasties* mod. Victoria 3 is a trademark of Paradox Interactive; this project is not affiliated with Paradox.
