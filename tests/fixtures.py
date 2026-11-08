"""A tiny synthetic game and two mods (no Paradox files), written to a temp folder.

Covers: same-path file override, REPLACE:, plain duplicate definitions, merged on_actions,
parameterised scripted effects, multi-line blocks, pops moved through a variable,
inline "scripted_bar_progress(x)", history file names with spaces, localisation replace/.
"""
from pathlib import Path

GAME = {
    'launcher/launcher-settings.json': '{"rawVersion": "9.9.9", "gameDataPath": "%USER_DOCUMENTS%/Paradox Interactive/Victoria 3"}',
    'game/common/journal_entries/00_je.txt': '''je_root = {
\timmediate = { trigger_event = { id = x.1 } }
\tscripted_button = btn_a
\tscripted_progress_bar = bar_a
\toutcome = {
\t\ttrigger = { has_global_variable = gv_ready }
\t\teffect = { set_global_variable = gv_done }
\t}
}
je_child = {
\tpossible = { always = no }
}
''',
    'game/common/scripted_buttons/00_btn.txt': '''btn_a = {
\tname = btn_a
\teffect = { helper_effect = { EVENT = x.2 } }
}
''',
    'game/common/scripted_progress_bars/00_bar.txt': 'bar_a = { name = bar_a }\n',
    'game/common/scripted_effects/00_eff.txt': '''helper_effect = {
\ttrigger_event = { id = $EVENT$ }
}
''',
    'game/common/scripted_effects/01_move.txt': '''mover = {
\trandom_scope_pop = {
\t\tlimit = { culture = cu:natives }
\t\tset_global_variable = { name = saved_pop value = this }
\t}
\tglobal_var:saved_pop = { move_pop = global_var:destination }
}
''',
    'game/common/on_actions/00_on.txt': 'on_monthly_pulse_country = { events = { x.3 } }\n',
    'game/events/x.txt': '''namespace = x
x.1 = {
\ttype = country_event
\ttitle = x.1.t
\ttrigger = { has_global_variable = gv_done }
\timmediate = { add_journal_entry = { type = je_child } }
\toption = { name = x.1.a mover = yes }
}
x.2 = {
\ttype = country_event
\timmediate = {
\t\ttrigger_event = {
\t\t\tid = x.3
\t\t\tdays = 5
\t\t}
\t}
}
x.3 = {
\ttype = country_event
\ttrigger = { "scripted_bar_progress(bar_a)" >= 10 }
}
''',
    'game/common/history/countries/usa - usa.txt': 'c:USA ?= { set_global_variable = gv_ready }\n',
    'game/localization/english/test_l_english.yml': '﻿l_english:\n je_root:0 "Root JE"\n x.1.t:0 "First event"\n',
}

MOD_A = {
    '.metadata/metadata.json': '{"name": "Mod A", "supported_game_version": "9.9.9"}',
    # same relative path as the game file: replaces it entirely (helper_effect now fires x.3)
    'common/scripted_effects/00_eff.txt': '''helper_effect = {
\ttrigger_event = { id = $EVENT$ }
\tset_variable = mod_a_was_here
}
''',
    'common/journal_entries/a_je.txt': '''REPLACE:je_child = {
\tpossible = { has_variable = mod_a_was_here }
}
''',
    'localization/english/replace/a_l_english.yml': '﻿l_english:\n je_root:0 "Root JE (mod A)"\n',
}

MOD_B = {
    '.metadata/metadata.json': '{"name": "Mod B"}',
    'common/on_actions/b_on.txt': 'on_monthly_pulse_country = { events = { x.4 } }\n',
    # sorts before events/x.txt, so this x.1 loads first and (by the first-wins assumption) is the effective one
    'events/00_b.txt': '''namespace = x
x.1 = {
\ttype = country_event
\ttitle = x.1.t
\timmediate = { set_global_variable = gv_from_mod_b }
}
x.4 = { type = country_event }
''',
}


def write(base: Path):
    for root, files in (('game', GAME), ('mod_a', MOD_A), ('mod_b', MOD_B)):
        for rel, text in files.items():
            p = base / root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, 'utf-8')
    return {'game': base / 'game', 'mod_a': base / 'mod_a', 'mod_b': base / 'mod_b'}


def config(base: Path, mods=('mod_a', 'mod_b'), game=True):
    roots = write(base)
    return {'schema': 1, 'game': {'path': str(roots['game']) if game else ''},
            'mods': [{'path': str(roots[m]), 'name': m} for m in mods],
            'load_order_source': 'manual', 'languages': ['english'], 'ui_language': 'en',
            'output_dir': str(base / 'out'), 'script_docs_dir': None, 'ignore': [], 'extra_folders': {}, 'detected': {}}
