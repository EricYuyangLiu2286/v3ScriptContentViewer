# Configuration

v3tree reads one JSON file. Default location: `<repository>/config/local.json` (not committed to git). Every command accepts `--config PATH`, so you can keep one file per mod combination.

Create it in one of three ways:

- `python run.py init` asks, in this order: interface language, game folder (it proposes one it found through Steam), whether to import the launcher playset (default no), mod folders one per line, localisation languages, output folder.
- `python run.py init --game "<folder>" --mod "<mod 1>" --mod "<mod 2>" --languages simp_chinese,english --ui en [--output <folder>]` asks nothing (use this from scripts and AI agents). `--playset` takes the mods from the launcher instead of `--mod`; `--game ""` means no vanilla.
- The web interface (Settings), or by hand as below.

`init` runs the check and does not save a configuration that has errors. The default output folder is `<repository>/output`.

```json
{
  "schema": 1,
  "game": { "path": "C:/Program Files (x86)/Steam/steamapps/common/Victoria 3" },
  "mods": [
    { "path": "C:/.../workshop/content/529340/3385002128", "name": "Community Mod Framework" },
    { "path": "C:/Users/me/Documents/Paradox Interactive/Victoria 3/mod/My Mod", "name": "My Mod" }
  ],
  "load_order_source": "manual",
  "languages": ["english"],
  "ui_language": "en",
  "output_dir": "C:/Users/me/v3tree-output",
  "script_docs_dir": null,
  "ignore": ["**/_backup*/**"],
  "extra_folders": {},
  "detected": {}
}
```

| Field | Meaning |
|---|---|
| `game.path` | The game install folder, or its `game` subfolder. May be empty, but `game` and `mods` cannot both be empty. |
| `mods` | Mod folders **in load order: earlier loads first, later overrides earlier.** May be empty. |
| `load_order_source` | `launcher` (read from the launcher) or `manual`. Changing the order by hand sets `manual`. |
| `languages` | Localisation folders for names, first one wins, e.g. `["simp_chinese", "english"]`. |
| `ui_language` | `en` or `zh`: interface, reports, and the context labels written into the index. Rebuild the index after changing it. |
| `output_dir` | Where the index and the cases go. |
| `script_docs_dir` | Folder with `effects.log`, `triggers.log`, `event_targets.log`. Empty: look in `<Documents>/Paradox Interactive/Victoria 3/docs`. |
| `ignore` | Glob patterns (relative to each mod folder) that are not read. |
| `extra_folders` | `{"common/new_folder": "type_name"}` to index database folders a newer game version adds, without changing code. |
| `detected` | Written by `doctor` (game version, Steam build). Do not edit. |

## Load order

- **From the launcher:** the launcher lists the active playset's enabled mods, in order, in `<Documents>/Paradox Interactive/Victoria 3/content_load.json` (`enabledMods`). `init` and the web Settings page can import it.
- **Not proven:** that this list order is the load order and that later mods override earlier ones. `doctor` shows the order and asks you to confirm it. To check yourself: make two tiny mods that define the same static modifier differently and see which one the game uses.
- If the launcher file is missing or the order is wrong, put the mods in order by hand.

## The startup check (`doctor`)

Exit code 0 = all good, 1 = notes only, 2 = errors (cannot continue).

| Check | Result |
|---|---|
| At least one path | Error if neither the game nor a mod is given. |
| Game folder | Error if there is no `game/common` under it. The version comes from `launcher/launcher-settings.json`. |
| Each mod | Name and supported version from `.metadata/metadata.json`; a note if the version differs from the game's; an error if the folder has neither metadata nor `common/`, `events/` or `localization/`. |
| No game folder | Note: references to vanilla content will show as undefined. |
| Load order | Note asking you to confirm it (only with two or more mods). |
| Script docs | Note if missing: the "unknown key" diagnostic is skipped; edges are not affected. Create them with the console command `script_docs` in the game. |
| Languages | Note if a language folder exists nowhere. |
| Output folder | Error if not writable. |
