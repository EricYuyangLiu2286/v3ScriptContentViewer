# Judging guide

The index says what is connected. A *map* also needs to know what belongs to a theme ("the X civil war and its direct consequences"). That is a judgment, made by a person or an AI agent, and recorded with a reason.

## The three verdicts

| Verdict | Meaning | On the map |
|---|---|---|
| `in` | Belongs to the theme. Its neighbours are listed next. | Drawn, expanded |
| `boundary` | A different system, directly connected (name the system after `@`). | Drawn with a dashed border, not expanded |
| `out` | Unrelated: generic tools, parameters, incidental references. | Not drawn; listed in the report and in the side panel |

A rough test: if you removed the theme, would this node lose its purpose? Yes → `in`. Is it part of another system that the theme touches? → `boundary`. Is it a general utility or a value passed along? → `out`.

## The decisions file

One line each; `//` starts a comment. A later line for the same key wins. Per-node lines beat rules; among rules, the first match wins.

```
in event:my_events.3 # fires when the war starts
boundary je:my_other_je @Japan_politics # reads our war flag; a different system
out strigger:is_at_war_generic # generic helper
rule R1 in type=event file_regex=^events/my_war_events\.txt$ # every event of the war file belongs to the war
rule R2 boundary @Country type=tag # countries are drawn, not expanded
soft yes seffect:a_moves_pops|seffect:b_reads_pops|pop:my_culture_trigger # both handle the same group of pops
soft no *|*|law:* # laws are shared widely
```

Rule conditions: `type=a,b`, `id_regex=…` (bare id), `key_regex=…` (full key such as `seffect:x`), `file_regex=…` (any definition site), `root=game|mod|mod2` (where it is defined; `mod` = any mod layer), `undefined=1`.

Node types (the prefix of every key, used in `type=`): `je` journal entry, `event`, `decision`, `button`, `bar` progress bar, `law`, `dp` diplomatic play, `wargoal`, `modifier`, `var` variable, `gvar` global variable, `onaction`, `seffect` scripted effect, `strigger` scripted trigger, `svalue` script value, `tag` country, `chartemplate` character template, `culture`, `pop` pop object, `customloc`, `history`, `movement`, `govtype`, `dynname` dynamic name, `party`, `ideology`, `lawgroup`, `socialclass`, `socialhier`, `formation`, `treaty`, `subjtype`, `charinter`, `diplaction`, `objective`, `aistrat`, `srule`, `pbprinciple`, `pbname`, `flagdef`, `creation`, `movesupport`.

`_` in a system name is shown as a space.

## Soft edges

A soft edge is "one side writes an object, the other reads it", e.g. both move the same group of pops, or one sets a global variable another system reads. Candidates are listed for shared objects that are **not in theme**: objects judged `boundary` or `out`, and pop objects. (An in-theme object is expanded, so its writers and readers already appear as ordinary neighbours.) A boundary object is drawn, but its other readers and writers lie outside the map; that is why its candidates are still listed. Confirm only the links that matter for the theme; the candidate list gives both locations.

Line format: `soft yes|no WRITER|READER|OBJECT # reason`. The order is writer first, reader second. `*` can stand for the writer, the reader, or both; the object may be a whole type: `soft no *|*|law:*`. The most specific line wins (exact pair, then writer or reader wildcard, then `*|*|object`, then `*|*|type:*`).

On the map, several confirmed pairs through one drawn object become one dashed line between the outside node and that object.

## Common mistakes

- **Judging by the file a node is defined in.** Look at what it does and what starts it. A reform JE defined in a file of another feature can still belong to your theme.
- **Making a hub in-theme.** A variable or trigger read by dozens of systems pulls all of them in. Make it `boundary` and look at its readers in the side panel instead.
- **Generic laws and cultures as in-theme.** They are referenced hundreds of times, mostly as parameters.
- **`show_as_tooltip`.** Effects inside it are only displayed. The edge carries the `tooltip_only` flag; the report checks whether the effect is executed elsewhere.
- **Same name, different object.** A variable and a character template, or an event namespace and a variable, can share a name. The reverse check knows this; you should too.

## Index gaps

The report's reverse check lists every place an in-theme id appears in the mod's script files that no edge explains. Each one is either an index gap (fix the indexer and rebuild) or the same name used for something else. Never hand-add edges to the decisions file to cover a gap.
