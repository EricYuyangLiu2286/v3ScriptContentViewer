"""Global reference index: every edge carries file:line.

Nothing is guessed: references that cannot be resolved mechanically go to
`unresolved`; typed references whose target is not defined go to `dangling`.
"""
from __future__ import annotations
import bisect, json, re, time
from collections import defaultdict
from pathlib import Path

from .clausewitz import parse, unquote, basekey
from .i18n import T, type_name, LANG
from . import i18n
from .sources import Sources, load_loc, loc_resolve

INDEX_VERSION = 1

# folder -> node type
FOLDERS = {
    'common/journal_entries': 'je',
    'common/scripted_buttons': 'button',
    'common/scripted_progress_bars': 'bar',
    'events': 'event',
    'common/decisions': 'decision',
    'common/laws': 'law',
    'common/diplomatic_plays': 'dp',
    'common/war_goal_types': 'wargoal',
    'common/static_modifiers': 'modifier',
    'common/on_actions': 'onaction',
    'common/scripted_effects': 'seffect',
    'common/scripted_triggers': 'strigger',
    'common/script_values': 'svalue',
    'common/country_definitions': 'tag',
    'common/character_templates': 'chartemplate',
    'common/cultures': 'culture',
    'common/customizable_localization': 'customloc',
    'common/political_movements': 'movement',
    'common/diplomatic_actions': 'diplaction',
    'common/dynamic_country_names': 'dynname',
    'common/government_types': 'govtype',
    'common/scripted_rules': 'srule',
    'common/subject_types': 'subjtype',
    'common/character_interactions': 'charinter',
    'common/country_formation': 'formation',
    'common/objectives': 'objective',
    'common/ai_strategies': 'aistrat',
    'common/treaty_articles': 'treaty',
    'common/power_bloc_principles': 'pbprinciple',
    'common/ideologies': 'ideology',
    'common/social_classes': 'socialclass',
    'common/social_hierarchies': 'socialhier',
    'common/law_groups': 'lawgroup',
    'common/parties': 'party',
    'common/political_movement_pop_support': 'movesupport',
    'common/power_bloc_names': 'pbname',
    'common/flag_definitions': 'flagdef',
    'common/country_creation': 'creation',
}
HISTORY_DIRS = ['countries', 'global', 'diplomacy', 'diplomatic_plays', 'characters',
                'power_blocs', 'treaties', 'political_movements', 'interests']


# ---------------------------------------------------------------- script docs (optional)
EFFECTS, TRIGGERS, TARGETS = set(), set(), set()
HAVE_DOCS = False


def load_docs(docs_dir):
    global EFFECTS, TRIGGERS, TARGETS, HAVE_DOCS

    def names(fname, marker):
        p = Path(docs_dir) / fname if docs_dir else None
        if not p or not p.exists():
            return set()
        return {l[len(marker):].strip() for l in p.read_text('utf-8', errors='replace').splitlines() if l.startswith(marker)}
    EFFECTS, TRIGGERS, TARGETS = names('effects.log', '## '), names('triggers.log', '## '), names('event_targets.log', '### ')
    HAVE_DOCS = bool(EFFECTS and TRIGGERS)


# ---------------------------------------------------------------- key tables
TRIGGER_KEYS = {'trigger', 'limit', 'possible', 'is_shown', 'is_shown_when_inactive', 'visible', 'is_valid',
                'can_enact', 'potential', 'allow', 'should_be_involved', 'should_show_when_not_involved',
                'complete', 'fail', 'invalid', 'filter', 'is_progressing', 'status_desc', 'desc', 'title',
                'triggered_desc', 'first_valid', 'can_be_enacted', 'is_visible', 'unlocking_trigger',
                'ai_chance', 'ai_will_do', 'weight', 'start_value', 'min_value', 'max_value',
                'monthly_progress', 'weekly_progress', 'current_value', 'goal_add_value', 'value',
                'cooldown', 'can_take', 'selection_trigger', 'ai_weight', 'requirement_to_maintain',
                'is_enabled', 'pause_progress', 'possible_trigger', 'can_use', 'country_trigger',
                'can_research', 'enactment_setback_chance', 'progressbar_value'}
EFFECT_KEYS = {'immediate', 'effect', 'option', 'after', 'when_taken', 'on_complete', 'on_fail', 'on_timeout',
               'on_invalid', 'on_enact', 'on_activate', 'on_deactivate', 'on_start', 'on_end', 'on_success',
               'on_failure', 'on_war_begins', 'on_weekly_pulse', 'on_monthly_pulse', 'on_yearly_pulse',
               'on_accept', 'on_decline', 'on_created', 'on_pass', 'on_fail_vote', 'on_use', 'on_effect',
               'on_finish', 'on_trigger'}
ITER_POP = re.compile(r'^(every|any|random|ordered)_(scope_)?pop$')
POP_WRITE = {'move_pop', 'move_partial_pop', 'change_pop_culture', 'change_pop_religion', 'change_poptype',
             'kill_population', 'kill_population_percent', 'kill_population_in_state',
             'kill_population_percent_in_state', 'convert_population', 'add_pop_wealth'}
VAR_W = {'set_variable', 'change_variable', 'remove_variable', 'clamp_variable', 'add_to_variable_list',
         'remove_list_variable', 'clear_variable_list', 'add_to_variable_map', 'remove_variable_map',
         'clear_variable_map', 'round_variable'}
VAR_R = {'has_variable', 'has_variable_list', 'is_target_in_variable_list', 'variable_list_size',
         'has_variable_map', 'is_key_in_variable_map'}
GVAR_W = {k.replace('variable', 'global_variable') for k in VAR_W} | {'remove_list_global_variable'}
GVAR_R = {k.replace('variable', 'global_variable') for k in VAR_R}
LIST_ITER = {'any_in_list', 'every_in_list', 'random_in_list', 'ordered_in_list',
             'any_in_global_list', 'every_in_global_list', 'random_in_global_list', 'ordered_in_global_list'}
JE_ADD = {'add_journal_entry', 'add_contextless_journal_entry'}
JE_READ = {'has_journal_entry', 'has_inactive_journal_entry', 'is_involved_in_journal_entry'}
MOD_W = {'add_modifier', 'remove_modifier'}
MOD_R = {'has_modifier'}
LAW_W = {'activate_law', 'enact_law', 'start_enactment', 'deactivate_law', 'set_law', 'add_law_progress'}
CULT_W = {'add_primary_culture', 'remove_primary_culture', 'add_culture_acceptance_modifier', 'add_acceptance',
          'add_culture_standard_of_living_modifier', 'change_pop_culture', 'change_character_culture',
          'set_culture_acceptance'}
BAR_KEYS = {'add_progress': 'write', 'set_bar_progress': 'write', 'scripted_bar_progress': 'read'}
TEMPLATE_KEYS = {'has_template', 'template', 'is_template_used'}

TOK_VAR = re.compile(r'(?<![\w])(global_var|var|local_var):([A-Za-z0-9_$]+)')
TOK_TAG = re.compile(r'(?<![\w:])c:([A-Za-z0-9_$]+)')
TOK_LAW = re.compile(r'law_type:([A-Za-z0-9_$]+)')
TOK_CU = re.compile(r'(?<![\w])cu:([A-Za-z0-9_$]+)')
TOK_JE = re.compile(r'(?<![\w])je:([A-Za-z0-9_$]+)')
TOK_MOD = re.compile(r'(?<![\w])modifier:([A-Za-z0-9_$]+)')
TOK_BARFN = re.compile(r'scripted_bar_progress\(([A-Za-z0-9_]+)\)')


def is_num(s):
    return bool(re.fullmatch(r'-?\d+(\.\d+)?', s or ''))


# ---------------------------------------------------------------- files
class SourceFile:
    def __init__(self, root, rel, path):
        self.root, self.rel, self.path = root, rel, path
        self.text = path.read_text('utf-8-sig', errors='replace')
        self.nl = [i for i, c in enumerate(self.text) if c == '\n']

    def line(self, off):
        return bisect.bisect_right(self.nl, off - 1) + 1 if off else 1

    def lines(self, a, b):
        ls = self.text.split('\n')
        return '\n'.join(ls[a - 1:b])


# ---------------------------------------------------------------- index
class Index:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.unresolved = []
        self.dangling = []
        self.unknown_keys = defaultdict(list)
        self.parse_errors = []
        self.overridden_files = []
        self.duplicates = []
        self.param_refs = defaultdict(list)   # seffect/strigger key -> refs with $PARAM$
        self.call_args = []                   # (caller, callee_key, args, file, line)
        self.defs = {}                        # node key -> (SourceFile, Node)
        self.saved_pops = defaultdict(list)   # (var kind, name) -> pop filters it was saved under
        self.pop_moves = []                   # move_pop executed on a pop held in a variable
        self.files = {}

    def node(self, ntype, nid, **kw):
        key = f'{ntype}:{nid}'
        n = self.nodes.get(key)
        if n is None:
            n = self.nodes[key] = {'key': key, 'type': ntype, 'id': nid, 'sites': [], 'defined': False}
        n.update({k: v for k, v in kw.items() if v is not None})
        return n

    # ---------------- definitions
    def define(self, ntype, nid, sf, blk, how):
        key = f'{ntype}:{nid}'
        existing = self.nodes.get(key)
        site = {'root': sf.root, 'file': sf.rel, 'line': sf.line(blk.start),
                'end': sf.line(blk.end), 'how': how}
        dup = existing and existing['defined'] and how == 'define' and ntype not in ('onaction', 'history')
        if dup:
            self.duplicates.append({'key': key, 'first': existing['sites'][0], 'again': site})
        n = self.node(ntype, nid)
        if dup:
            # Plain duplicate without REPLACE: assume the FIRST loaded definition wins (unproven; Community
            # Mod Framework names its override files "00_com_..." so they load before vanilla, which only
            # works if the first wins). The later site is listed, marked ignored, and not walked.
            site['ignored'] = True
            n['sites'].append(site)
        elif how == 'replace':
            for s in n['sites']:
                s['replaced'] = True
            n['sites'].append(site)
            self.defs[key] = [(sf, blk)]
        else:
            n['sites'].append(site)
            self.defs.setdefault(key, []).append((sf, blk))
        n['defined'] = True
        return n


IDX = None
GENERIC_TYPES = ('lawgroup', 'socialhier', 'socialclass', 'govtype', 'movement', 'formation', 'subjtype', 'pbprinciple')
GENERIC_IDS = {}


def edge(src, dst, kind, rel, ctx, sf, off, flags=(), extra=None, end=None):
    e = {'s': src, 't': dst, 'k': kind, 'rel': rel, 'ctx': ctx, 'file': sf.rel, 'root': sf.root,
         'line': sf.line(off)}
    if end is not None and end > off:
        le = sf.line(end)
        if le > e['line']:
            e['end'] = le
    if flags:
        e['flags'] = sorted(set(flags))
    if extra:
        e.update(extra)
    IDX.edges.append(e)


def outcome_kind(blk):
    flags = blk.get('flags')
    fv = flags.values() if flags is not None and flags.children is not None else []
    header = (blk.scalar('header') or '').lower()
    if 'invalid_outcome' in fv:
        return T('outcome.invalid')
    if 'timeout' in fv or 'timeout' in header:
        return T('outcome.timeout')
    if 'failure' in header or 'fail' in header:
        return T('outcome.failure')
    return T('outcome.success')


def always_no(blk):
    if blk is None or blk.children is None:
        return False
    ch = [c for c in blk.children]
    return len(ch) == 1 and ch[0].key == 'always' and ch[0].value == 'no'


def top_label(k):
    key = f'ctx.{k}'
    return T(key) if key in i18n.S else k


class Walker:
    def __init__(self, owner, sf, otype, blk=None):
        self.owner, self.sf, self.otype = owner, sf, otype
        self.top = {id(c) for c in (blk.children or [])} if blk is not None else set()

    # mode: 'call' | 'cond'
    def walk_children(self, blk, mode, ctx, flags):
        if blk.children is None:
            return
        local_flags = set(flags)
        lim = blk.get('limit') or blk.get('trigger')
        if always_no(lim):
            local_flags.add('disabled')
        for c in blk.children:
            self.visit(c, mode, ctx, local_flags, blk)

    def visit(self, n, mode, ctx, flags, parent):
        k, sf, own = n.key, self.sf, self.owner
        self._end = n.end if n.children is not None else None
        v = unquote(n.value) if n.value is not None else None
        kb = basekey(k) if k else None
        # --- token scan on scalar key/value text
        for text, off in ((k, n.start), (v, n.vstart)):
            if text:
                self.scan_tokens(text, mode, ctx, flags, off, k)
        if k is None:
            if n.children is not None:
                self.walk_children(n, mode, ctx, flags)
            return
        # --- specific keys
        if k == 'trigger_event':
            tid = v if n.children is None else (n.scalar('id') or n.scalar('on_action'))
            if n.children is not None and n.get('on_action') is not None:
                self.ref('onaction', n.scalar('on_action'), 'call', 'trigger_on_action', ctx, flags, n.start)
            delay = ''
            if n.children is not None:
                for u in ('days', 'weeks', 'months', 'years'):
                    dv = n.scalar(u)
                    if dv is not None:
                        delay = T('ctx.delay', n=dv, unit=T(f'unit.{u}'))
            if tid and n.get('on_action') is None:
                self.ref('event', tid, 'call', 'trigger_event', ctx + (f' {delay}' if delay else ''), flags, n.start)
            return
        if k == 'random_events' and n.children is not None:
            pairs = [(c.key, unquote(c.value)) for c in n.children if c.key is not None and c.value is not None]
            total = sum(float(w) for w, _ in pairs if is_num(w))
            for c in n.children:
                if c.key is not None and not is_num(c.key):
                    continue  # chance_of_no_event etc.
                if c.key is not None and c.value is not None and unquote(c.value) not in ('0', ''):
                    w = c.key
                    lbl = T('ctx.random_weight', ctx=ctx, w=w, total=f'{total:g}') if is_num(w) else ctx
                    self.ref('event', unquote(c.value), 'call', 'random_event', lbl, flags, c.start)
                elif c.key is None and c.value is not None:
                    self.ref('event', unquote(c.value), 'call', 'random_event', ctx, flags, c.start)
            return
        if k == 'events' and self.otype == 'onaction' and n.children is not None:
            for c in n.children:
                if c.value is not None:
                    self.ref('event', unquote(c.value), 'call', 'onaction_event', ctx, flags, c.start)
            return
        if k == 'on_actions' and n.children is not None:
            for c in n.children:
                if c.value is not None:
                    self.ref('onaction', unquote(c.value), 'call', 'onaction_chain', ctx, flags, c.start)
            return
        if k in JE_ADD or k in JE_READ or k == 'remove_journal_entry':
            tid = v if n.children is None else n.scalar('type')
            if tid and tid not in ('yes', 'no'):
                kind = 'call' if (k in JE_ADD or k == 'remove_journal_entry') else 'cond'
                self.ref('je', tid, kind, k, ctx, flags, n.start)
            if n.children is not None:
                self.walk_children(n, mode, ctx, flags)
            return
        if k in ('scripted_button', 'scripted_progress_bar') and v:
            t = 'button' if k == 'scripted_button' else 'bar'
            self.ref(t, v, 'struct', k, T('ctx.button') if t == 'button' else T('ctx.bar'), flags, n.start)
            return
        if k in BAR_KEYS and n.children is not None:
            nm = n.scalar('name')
            if nm:
                self.ref('bar', nm, 'call' if BAR_KEYS[k] == 'write' else 'cond', k, ctx, flags, n.start,
                         access=BAR_KEYS[k])
            self.walk_children(n, 'cond', ctx, flags)
            return
        if k in VAR_W or k in VAR_R or k in GVAR_W or k in GVAR_R:
            g = 'gvar' if 'global' in k else 'var'
            name = v if n.children is None else n.scalar('name')
            acc = 'write' if (k in VAR_W or k in GVAR_W) else 'read'
            if name and name not in ('yes', 'no'):
                self.ref(g, name, 'call' if acc == 'write' else 'cond', k, ctx, flags, n.start, access=acc)
            if n.children is not None:
                for c in n.children:
                    if c.key != 'name':
                        self.visit(c, 'cond' if acc == 'read' else mode, ctx, flags, n)
            return
        if k in LIST_ITER and n.children is not None:
            for vk, g in (('variable', 'var'), ('global_variable', 'gvar')):
                nm = n.scalar(vk)
                if nm:
                    self.ref(g, nm, 'cond', k, ctx, flags, n.start, access='read')
            self.walk_children(n, mode, ctx, flags)
            return
        if k in MOD_W or k in MOD_R:
            name = v if n.children is None else n.scalar('name')
            if name:
                acc = 'write' if k in MOD_W else 'read'
                tf = set(flags)
                self.ref('modifier', name, 'call' if acc == 'write' else 'cond', k, ctx, tf, n.start, access=acc)
            if n.children is not None:
                for c in n.children:
                    if c.key != 'name':
                        self.visit(c, mode, ctx, flags, n)
            return
        if k == 'modifiers_while_active' and n.children is not None:
            for c in n.children:
                if c.key is None and c.value is not None:
                    self.ref('modifier', unquote(c.value), 'call', 'modifiers_while_active', T('ctx.modifiers_while_active'), flags,
                             c.start, access='write')
            return
        if kb and n.children is None and v and f'law:{kb}' in IDX.nodes and IDX.nodes[f'law:{kb}']['defined']                 and not v.startswith('law_type:'):
            self.ref('law', kb, 'cond', 'law_stance', ctx, flags, n.start, access='read')
            return
        # less common database objects named by value (group = lawgroup_x, set_social_hierarchy = x ...)
        # or used as a block key (ideology stances per law group)
        if v and n.children is None and v in GENERIC_IDS and k not in ('name', 'desc', 'text', 'title'):
            self.ref(GENERIC_IDS[v], v, 'call' if (mode == 'call' and k.startswith('set_')) else 'cond', k, ctx, flags, n.vstart)
        if kb and n.children is not None and kb in GENERIC_IDS:
            self.ref(GENERIC_IDS[kb], kb, 'cond', 'keyed_block', ctx, flags, n.start)
        if k in TEMPLATE_KEYS and v:
            self.ref('chartemplate', v, mode, k, ctx, flags, n.start)
            return
        if k == 'create_diplomatic_play' or k == 'add_war_goal' or k == 'is_diplomatic_play_type':
            t = v if n.children is None else n.scalar('type')
            if t:
                tt = 'dp' if k != 'add_war_goal' else 'wargoal'
                self.ref(tt, t, 'call' if k != 'is_diplomatic_play_type' else 'cond', k, ctx, flags, n.start)
            if n.children is not None:
                for c in n.children:
                    if c.key != 'type':
                        self.visit(c, mode, ctx, flags, n)
                    # war goals inside create_diplomatic_play
            return
        if k in ('war_goal', 'war_goal_type') and v and n.children is None:
            self.ref('wargoal', v, mode, k, ctx, flags, n.start)
            return
        if k == 'type' and v and parent is not None:
            for tt in ('dp', 'wargoal'):
                if f'{tt}:{v}' in IDX.nodes and IDX.nodes[f'{tt}:{v}']['defined']:
                    self.ref(tt, v, mode, 'type', ctx, flags, n.start)
        if n.children is not None and mode == 'call':
            mv = re.fullmatch(r'(global_var|var):([A-Za-z0-9_]+)', k or '')
            if mv and any(x.key in POP_WRITE for x in n.walk()):
                IDX.pop_moves.append({'owner': self.owner, 'var': ('gvar' if mv.group(1) == 'global_var' else 'var', mv.group(2)),
                                      'sf': self.sf, 'off': n.start, 'end': n.end, 'ctx': ctx, 'flags': sorted(flags)})
        if k == 'show_as_tooltip' and n.children is not None:
            self.walk_children(n, mode, ctx, set(flags) | {'tooltip_only'})
            return
        if ITER_POP.match(k or '') and n.children is not None:
            self.pop_object(n, mode, ctx, flags)
            # continue normal walk too
        if k == 'create_pop' and n.children is not None:
            cu = n.scalar('culture')
            if cu and cu.startswith('cu:'):
                self.ref('pop', 'culture:' + cu[3:], 'call', 'create_pop', ctx, flags, n.start, access='write')
        if k == 'random_list' and n.children is not None:
            for c in n.children:
                if c.children is not None:
                    lbl = T('ctx.random_branch', ctx=ctx, w=c.key) if c.key else ctx
                    self.walk_children(c, mode, lbl, flags)
            return
        if k == 'random' and n.children is not None:
            ch = n.scalar('chance')
            self.walk_children(n, mode, T('ctx.random_chance', ctx=ctx, ch=ch) if ch else ctx, flags)
            return
        # --- scripted effects / triggers / values by key
        if kb:
            hit = False
            if mode == 'call' and f'seffect:{kb}' in IDX.nodes and IDX.nodes[f'seffect:{kb}']['defined']:
                self.ref('seffect', kb, 'call', 'scripted_effect', ctx, flags, n.start)
                self.record_args(f'seffect:{kb}', n)
                hit = True
            elif f'strigger:{kb}' in IDX.nodes and IDX.nodes[f'strigger:{kb}']['defined'] and \
                    (mode == 'cond' or f'seffect:{kb}' not in IDX.nodes):
                self.ref('strigger', kb, 'cond', 'scripted_trigger', ctx, flags, n.start)
                self.record_args(f'strigger:{kb}', n)
                hit = True
            elif f'seffect:{kb}' in IDX.nodes and IDX.nodes[f'seffect:{kb}']['defined']:
                self.ref('seffect', kb, 'call', 'scripted_effect', ctx, flags, n.start)
                self.record_args(f'seffect:{kb}', n)
                hit = True
            elif f'svalue:{kb}' in IDX.nodes and IDX.nodes[f'svalue:{kb}']['defined']:
                self.ref('svalue', kb, 'cond', 'script_value', ctx, flags, n.start)
                if v and n.children is None and f'svalue:{v}' in IDX.nodes and IDX.nodes[f'svalue:{v}']['defined']:
                    self.ref('svalue', v, 'cond', 'script_value', ctx, flags, n.vstart)
                hit = True
            if hit:
                return
            if '$' in kb:
                self.param_or_unresolved('key', kb, mode, ctx, flags, n.start)
            elif HAVE_DOCS and n.children is None and v in ('yes', 'no') and id(n) not in self.top and 'nounk' not in flags and kb not in EFFECTS and kb not in TRIGGERS \
                    and kb not in TARGETS and not kb.startswith(('scope:', 'c:', 'var:', 'global_var:')):
                IDX.unknown_keys[kb].append(f'{sf.rel}:{sf.line(n.start)}')
        # value is a script value?
        if v and n.children is None and not is_num(v) and f'svalue:{v}' in IDX.nodes \
                and IDX.nodes[f'svalue:{v}']['defined']:
            self.ref('svalue', v, 'cond', 'script_value', ctx, flags, n.vstart)
        if v and '$' in v and k not in ('text', 'name', 'desc') and n.children is None:
            pass  # values with params are handled by token scan when typed
        # --- descend
        if n.children is not None:
            nm = mode
            if k in TRIGGER_KEYS or (k.startswith(('any_', 'trigger_if', 'trigger_else')) and mode == 'cond'):
                nm = 'cond'
            elif k in EFFECT_KEYS or k in ('hidden_effect', 'custom_tooltip', 'if', 'else_if', 'else', 'while'):
                nm = mode if k in ('custom_tooltip', 'if', 'else_if', 'else', 'while') else 'call'
            if k in ('modifier', 'modifiers', 'possible_modifiers') or ntype_is_def(self.otype):
                flags = set(flags) | ({'nounk'} if k in ('modifier', 'modifiers', 'possible_modifiers') or self.otype in ('dp', 'wargoal', 'law', 'movement', 'diplaction', 'history') else set())
            self.walk_children(n, nm, ctx, flags)

    def record_args(self, callee, n):
        if n.children is not None:
            args = {c.key: unquote(c.value) for c in n.children if c.key and c.value is not None}
            if args:
                IDX.call_args.append((self.owner, callee, args, self.sf.rel, self.sf.line(n.start)))

    def scan_tokens(self, text, mode, ctx, flags, off, key):
        for m in TOK_VAR.finditer(text):
            kind, name = m.group(1), m.group(2)
            if kind == 'local_var':
                continue
            self.ref('gvar' if kind == 'global_var' else 'var', name, 'cond', 'var_token', ctx, flags, off,
                     access='read')
        for m in TOK_TAG.finditer(text):
            k = 'call' if mode == 'call' else 'cond'
            self.ref('tag', m.group(1), k, 'scope_country' if key == text else 'country_ref', ctx, flags, off)
        for m in TOK_LAW.finditer(text):
            if key in LAW_W:
                self.ref('law', m.group(1), 'call', key, ctx, flags, off, access='write')
            else:
                self.ref('law', m.group(1), 'cond' if mode == 'cond' or key.startswith(('has_', 'is_')) else 'ref',
                         key or 'law_ref', ctx, flags, off, access='read')
        for m in TOK_CU.finditer(text):
            acc = 'write' if (mode == 'call' and key in CULT_W) else 'read'
            self.ref('culture', m.group(1), 'call' if acc == 'write' else 'cond', key or 'culture_ref', ctx, flags,
                     off, access=acc)
        for m in re.finditer(r'active_law:([A-Za-z0-9_]+)', text):
            if m.group(1) in GENERIC_IDS:
                self.ref(GENERIC_IDS[m.group(1)], m.group(1), 'cond', 'active_law', ctx, flags, off)
        for m in TOK_BARFN.finditer(text):
            self.ref('bar', m.group(1), 'cond', 'scripted_bar_progress', ctx, flags, off, access='read')
        for m in TOK_JE.finditer(text):
            self.ref('je', m.group(1), 'call' if (mode == 'call' and key == text) else 'cond', 'je_scope', ctx,
                     flags, off)

    def pop_object(self, n, mode, ctx, flags):
        k = n.key
        filt = n.get('limit') if (k.startswith(('every', 'random', 'ordered'))) else n
        if filt is None or filt.children is None:
            return
        objs = set()
        for x in filt.walk():
            if x.key:
                kb = basekey(x.key)
                if f'strigger:{kb}' in IDX.nodes and IDX.nodes[f'strigger:{kb}']['defined']:
                    objs.update(strigger_closure(kb))
                if x.key in ('pop_type', 'is_pop_type') and x.value:
                    objs.add('pop_type:' + unquote(x.value))
            for t in (x.key, x.value):
                if t:
                    for m in TOK_CU.finditer(t):
                        objs.add('culture:' + m.group(1))
        if not objs:
            return
        writes = any(x.key in POP_WRITE for x in n.walk()) and mode == 'call'
        for x in n.walk():
            if x.key in ('set_variable', 'set_global_variable') and x.children is not None and x.scalar('value') == 'this':
                vn = x.scalar('name')
                if vn:
                    IDX.saved_pops[('gvar' if 'global' in x.key else 'var', vn)].append(
                        {'objs': sorted(objs), 'at': f'{self.sf.rel}:{self.sf.line(x.start)}'})
        for o in sorted(objs):
            self.ref('pop', o, 'cond', k, ctx, flags, n.start, access='read')
            if writes:
                self.ref('pop', o, 'call', k, ctx, flags, n.start, access='write')

    def param_or_unresolved(self, rtype, target, mode, ctx, flags, off):
        if self.otype in ('seffect', 'strigger'):
            IDX.param_refs[self.owner].append({'rtype': rtype, 'target': target, 'mode': mode, 'ctx': ctx,
                                               'file': self.sf.rel, 'line': self.sf.line(off), 'flags': sorted(flags),
                                               'root': self.sf.root})
        else:
            IDX.unresolved.append({'src': self.owner, 'rtype': rtype, 'target': target, 'file': self.sf.rel,
                                   'line': self.sf.line(off), 'reason': T('unres.dynamic_param_outside')})

    def ref(self, ttype, tid, kind, rel, ctx, flags, off, access=None):
        if tid is None:
            return
        tid = unquote(tid)
        if '$' in tid:
            self.param_or_unresolved(ttype, tid, kind, ctx, flags, off)
            return
        if tid in ('root', 'prev', 'this', 'from') or tid.startswith(('scope:', 'var:', 'global_var:', 'local_var:', 'root.', 'prev.', 'this.')) or ('.' in tid and ttype != 'event'):
            IDX.unresolved.append({'src': self.owner, 'rtype': ttype, 'target': tid, 'file': self.sf.rel,
                                   'line': self.sf.line(off), 'reason': T('unres.dynamic_target')})
            return
        if kind == 'ref':
            kind = 'cond'
        key = f'{ttype}:{tid}'
        if key not in IDX.nodes:
            IDX.node(ttype, tid)
        edge(self.owner, key, kind, rel, ctx, self.sf, off, flags, {'access': access} if access else None,
             end=getattr(self, '_end', None))


def ntype_is_def(t):
    return t in ('dp', 'wargoal', 'law', 'movement', 'diplaction', 'history')


_STC = {}


def strigger_closure(name, seen=None):
    """Scripted trigger names reachable from `name` (for pop-object keys)."""
    if name in _STC:
        return _STC[name]
    seen = seen or set()
    seen.add(name)
    out = {name}
    for sf, blk in IDX.defs.get(f'strigger:{name}', []):
        for x in blk.walk():
            if x.key:
                kb = basekey(x.key)
                if kb not in seen and f'strigger:{kb}' in IDX.nodes and IDX.nodes[f'strigger:{kb}']['defined']:
                    out |= strigger_closure(kb, seen)
            for t in (x.key, x.value):
                if t:
                    for m in TOK_CU.finditer(t):
                        out.add('culture:' + m.group(1))
    _STC[name] = out
    return out


# ---------------------------------------------------------------- top-level walking per type
def walk_definition(key, ntype, sf, blk, loc):
    w = Walker(key, sf, ntype, blk)
    if ntype in ('seffect', 'history'):
        w.walk_children(blk, 'call', T('ctx.seffect_body') if ntype == 'seffect' else T('ctx.history_body'), set())
        return
    if ntype in ('strigger', 'svalue', 'customloc'):
        w.walk_children(blk, 'cond', T('ctx.strigger_body') if ntype == 'strigger' else (T('ctx.svalue_body') if ntype == 'svalue' else T('ctx.customloc_body')), set())
        return
    if ntype in ('modifier', 'tag', 'culture'):
        return  # definitions only; no outgoing references indexed
    if ntype in ('ideology', 'socialclass', 'socialhier', 'lawgroup', 'party', 'movesupport', 'pbname', 'flagdef', 'creation'):
        w.walk_children(blk, 'cond', type_name(ntype), set())
        return
    if ntype in ('chartemplate', 'dynname'):
        # templates: only on_created runs script; dynamic names: trigger blocks inside each entry
        w.walk_children(blk, 'cond', T('ctx.template_body') if ntype == 'chartemplate' else T('ctx.dynname_body'), set())
        return
    oc = 0
    opt = 0
    for c in blk.children or []:
        k = c.key
        if k is None:
            continue
        if ntype == 'je' and k == 'outcome' and c.children is not None:
            oc += 1
            kind = outcome_kind(c)
            dis = {'disabled'} if always_no(c.get('trigger')) else set()
            for cc in c.children:
                if cc.key == 'trigger':
                    w.walk_children(cc, 'cond', T('ctx.outcome', n=oc, kind=kind, part=T('ctx.outcome.trigger')), dis)
                elif cc.key == 'effect':
                    w.walk_children(cc, 'call', T('ctx.outcome', n=oc, kind=kind, part=T('ctx.outcome.effect')), dis)
                elif cc.key == 'event_outcome_effect_desc' and cc.children is not None:
                    # describes the follow-up event's effect in the tooltip; not executed here
                    w.walk_children(cc, 'call', T('ctx.outcome', n=oc, kind=kind, part=T('ctx.outcome.effect')),
                                    dis | {'tooltip_only'})
            continue
        if ntype == 'event' and k == 'option' and c.children is not None:
            opt += 1
            dis = {'disabled'} if always_no(c.get('trigger')) else set()
            for cc in c.children:
                if cc.key in ('trigger', 'ai_chance', 'show_as_unavailable'):
                    w.visit(cc, 'cond', T('ctx.option_trigger', n=opt), dis, c)
                elif cc.key not in ('name', 'default_option', 'highlighted_option', 'fallback'):
                    w.visit(cc, 'call', T('ctx.option', n=opt), dis, c)
            continue
        if k in ('on_monthly_pulse', 'on_weekly_pulse', 'on_yearly_pulse') and c.children is not None:
            lbl = top_label(k)
            for cc in c.children:
                if cc.key == 'effect':
                    w.walk_children(cc, 'call', lbl, set())
                elif cc.key == 'events' and cc.children is not None:
                    for ev in cc.children:
                        if ev.value is not None:
                            w.ref('event', unquote(ev.value), 'call', 'pulse_event', lbl, set(), ev.start)
                elif cc.key == 'random_events':
                    w.visit(cc, 'call', lbl, set(), c)
                else:
                    w.visit(cc, 'cond', lbl, set(), c)
            continue
        lbl = top_label(k)
        if ntype == 'button' and k == 'effect':
            lbl = T('ctx.button_effect')
        if ntype == 'onaction' and k == 'effect':
            lbl = T('ctx.onaction_effect')
        if ntype == 'event' and k == 'immediate':
            lbl = T('ctx.event_immediate')
        if k in EFFECT_KEYS or (ntype == 'onaction' and k == 'effect'):
            mode = 'call'
        elif k in TRIGGER_KEYS or k in ('modifiers_while_active',):
            mode = 'cond'
        else:
            mode = 'cond'
        w.visit(c, mode, lbl, set(), blk)


# ---------------------------------------------------------------- build
def build(src: Sources, languages=('english',), docs_dir=None, extra_folders=None, verbose=True, progress=None):
    """Build the index. `progress(done, total, folder)` is called per folder when given."""
    global IDX, _STC
    IDX = Index()
    _STC = {}
    IDX.src = src
    load_docs(docs_dir)
    t0 = time.time()
    loc, locsrc = load_loc(src, languages)
    parsed = []  # (ntype, key, sf, blk, how)
    folders = list(FOLDERS.items()) + list((extra_folders or {}).items()) + \
        [(f'common/history/{d}', 'history') for d in HISTORY_DIRS]
    for fi, (folder, ntype) in enumerate(folders):
        if progress:
            progress(fi, len(folders), folder)
        files, over = src.collect(folder)
        IDX.overridden_files += over
        for label, rel, p in files:
            try:
                sf = SourceFile(label, rel, p)
                tree = parse(sf.text)
            except Exception as e:  # noqa: BLE001
                IDX.parse_errors.append({'file': rel, 'root': label, 'error': str(e)[:200]})
                continue
            IDX.files[rel] = sf
            if ntype == 'history':
                # ids must not contain whitespace (they are written to the decisions file); vanilla history
                # files are named like "usa - usa.txt"
                nid = re.sub(r'\s+', '_', rel.split('common/history/', 1)[1].rsplit('.', 1)[0])
                blk = tree
                n = IDX.define('history', nid, sf, blk, 'define')
                parsed.append(('history', n['key'], sf, blk))
                continue
            for c in tree.children or []:
                if c.key is None or c.children is None or c.key.startswith('@') or c.key == 'namespace':
                    continue
                how = 'define'
                if ':' in c.key and c.key.split(':', 1)[0] in ('REPLACE', 'TRY_REPLACE', 'REPLACE_OR_CREATE'):
                    how = 'replace'
                elif c.key.startswith(('INJECT:', 'TRY_INJECT:', 'INJECT_OR_CREATE:')):
                    how = 'inject'
                nid = basekey(c.key)
                if ntype == 'event' and '.' not in nid:
                    continue
                if ntype == 'onaction' and how == 'define' and IDX.nodes.get(f'onaction:{nid}', {}).get('defined'):
                    how = 'merge'
                n = IDX.define(ntype, nid, sf, c, how)
                parsed.append((ntype, n['key'], sf, c))
    GENERIC_IDS.clear()
    for key, n in IDX.nodes.items():
        if n['type'] in GENERIC_TYPES and n['defined']:
            GENERIC_IDS[n['id']] = n['type']
    if verbose:
        print(f'parsed {len(parsed)} definitions in {time.time()-t0:.1f}s', flush=True)
    # walk (after all definitions are known)
    for ntype, key, sf, blk in parsed:
        # walk only the effective definition(s)
        if not any(b is blk for a, b in IDX.defs.get(key, [])):
            continue
        walk_definition(key, ntype, sf, blk, loc)
    # pop moved through a variable -> the pop objects it was selected by
    for mvd in IDX.pop_moves:
        for sv in IDX.saved_pops.get(mvd['var'], []):
            for o in sv['objs']:
                IDX.node('pop', o)
                edge(mvd['owner'], f'pop:{o}', 'call', 'move_pop_via_var', mvd['ctx'], mvd['sf'], mvd['off'], mvd['flags'],
                     {'access': 'write', 'via_var': f"{mvd['var'][0]}:{mvd['var'][1]}", 'selected_at': sv['at']}, end=mvd['end'])
    # parameter resolution
    by_callee = defaultdict(list)
    for caller, callee, args, f, l in IDX.call_args:
        by_callee[callee].append((caller, args, f, l))
    for callee, refs in IDX.param_refs.items():
        for r in refs:
            params = re.findall(r'\$([A-Za-z0-9_]+)\$', r['target'])
            resolved_any = False
            for caller, args, f, l in by_callee.get(callee, []):
                if all(p in args for p in params):
                    resolved_any = True  # parameter supplied; non-component targets (scopes) need no edge
                    tgt = r['target']
                    for p in params:
                        tgt = tgt.replace(f'${p}$', args[p])
                    if r['rtype'] == 'key':
                        kb = tgt
                        mt = re.fullmatch(r'c:([A-Za-z0-9_]+)', kb)
                        if mt:
                            IDX.node('tag', mt.group(1))
                            IDX.edges.append({'s': caller, 't': f'tag:{mt.group(1)}', 'k': 'call' if r['mode'] == 'call' else 'cond',
                                              'rel': 'via_param', 'ctx': T('ctx.via_param', callee=callee.split(':', 1)[1]),
                                              'file': r['file'], 'line': r['line'], 'root': r['root'],
                                              'via': {'callee': callee, 'call_site': f'{f}:{l}', 'args': args}})
                        for tt in ('seffect', 'strigger'):
                            if f'{tt}:{kb}' in IDX.nodes and IDX.nodes[f'{tt}:{kb}']['defined']:
                                IDX.edges.append({'s': caller, 't': f'{tt}:{kb}', 'k': 'call' if tt == 'seffect' else 'cond',
                                                  'rel': 'via_param', 'ctx': T('ctx.via_param', callee=callee.split(':', 1)[1]),
                                                  'file': r['file'], 'line': r['line'], 'root': r['root'],
                                                  'via': {'callee': callee, 'call_site': f'{f}:{l}', 'args': args}})
                                resolved_any = True
                                break
                        continue
                    if '$' in tgt:
                        continue
                    key = f"{r['rtype']}:{tgt}"
                    if key not in IDX.nodes:
                        IDX.node(r['rtype'], tgt)
                    IDX.edges.append({'s': caller, 't': key, 'k': 'call' if r['mode'] == 'call' else 'cond',
                                      'rel': 'via_param', 'ctx': T('ctx.via_param', callee=callee.split(':', 1)[1]),
                                      'file': r['file'], 'line': r['line'], 'root': r['root'],
                                      'via': {'callee': callee, 'call_site': f'{f}:{l}', 'args': args},
                                      **({'flags': r['flags']} if r['flags'] else {})})
                    resolved_any = True
            if not resolved_any and r['rtype'] != 'key':
                IDX.unresolved.append({'src': callee, 'rtype': r['rtype'], 'target': r['target'], 'file': r['file'],
                                       'line': r['line'], 'reason': T('unres.param_no_caller')})
            if r['rtype'] == 'key' and not resolved_any and not r['target'].startswith('scope:')                     and re.fullmatch(r'[A-Za-z0-9_]*\$[A-Za-z0-9_]+\$[A-Za-z0-9_$]*', r['target']):
                IDX.unresolved.append({'src': callee, 'rtype': 'key', 'target': r['target'], 'file': r['file'],
                                       'line': r['line'], 'reason': T('unres.param_key_no_caller')})
    # names / localisation
    for key, n in IDX.nodes.items():
        t, nid = n['type'], n['id']
        name_key = None
        defs = IDX.defs.get(key, [])
        blk = defs[-1][1] if defs else None
        if t == 'event' and blk is not None:
            tk = blk.scalar('title')
            name_key = tk if tk else f'{nid}.t'
        elif t in ('button', 'bar') and blk is not None:
            name_key = blk.scalar('name') or nid
        elif t in ('je', 'decision', 'law', 'dp', 'wargoal', 'modifier', 'tag', 'culture', 'movement', 'diplaction',
                   'govtype', 'formation', 'objective', 'subjtype', 'charinter', 'treaty', 'pbprinciple',
                   'ideology', 'lawgroup', 'socialclass', 'socialhier'):
            name_key = nid
        elif t == 'dynname':
            name_key = nid
        if name_key:
            v = loc_resolve(loc, name_key)
            if v is None and t == 'event' and blk is not None and blk.get('title') is not None and blk.get('title').children:
                # first plain desc inside a triggered title
                for x in blk.get('title').walk():
                    if x.key == 'desc' and x.value and loc.get(unquote(x.value)):
                        name_key = unquote(x.value); v = loc_resolve(loc, name_key); break
            n['name_key'] = name_key
            if v is not None and t == 'dynname':
                v = f"{v}{T('name.dynname_suffix')}"
            if v is not None:
                n['name'] = v
                n['loc_src'] = locsrc.get(name_key)
        if 'name' not in n:
            n['name'] = nid
            n['no_loc'] = True
        if t == 'event' and blk is not None and blk.get('hidden') is not None and blk.scalar('hidden') == 'yes':
            n['hidden_event'] = True
    # disabled detection
    incoming_add = defaultdict(int)
    for e in IDX.edges:
        if e['rel'] in JE_ADD or e['rel'] in ('trigger_event', 'random_event', 'onaction_event'):
            incoming_add[e['t']] += 1
    for key, defs in IDX.defs.items():
        n = IDX.nodes[key]
        sf, blk = defs[-1]
        t = n['type']
        reason = None
        if t == 'event' and always_no(blk.get('trigger')):
            reason = T('dis.event')
        elif t == 'decision' and (always_no(blk.get('is_shown')) or always_no(blk.get('possible'))):
            reason = T('dis.decision')
        elif t == 'button' and (always_no(blk.get('visible')) or always_no(blk.get('possible'))):
            reason = T('dis.button')
        elif t == 'je' and always_no(blk.get('possible')) and incoming_add[key] == 0:
            reason = T('dis.je')
        if reason:
            n['disabled'] = reason
    # dangling targets
    for e in IDX.edges:
        tn = IDX.nodes[e['t']]
        if not tn['defined'] and tn['type'] not in ('var', 'gvar', 'pop'):
            IDX.dangling.append({'edge_src': e['s'], 'target': e['t'], 'file': e['file'], 'line': e['line']})
    for k, n in IDX.nodes.items():
        n['type_zh'] = type_name(n['type'])
    if verbose:
        print(f'built in {time.time()-t0:.1f}s: {len(IDX.nodes)} nodes, {len(IDX.edges)} edges', flush=True)
    return IDX


def save(out_dir, meta=None, idx=None):
    """Write <out_dir>/index/graph.json and stats.json. `meta` records layers, version, languages."""
    idx = idx or IDX
    out = Path(out_dir) / 'index'
    out.mkdir(parents=True, exist_ok=True)
    data = {
        'index_version': INDEX_VERSION,
        'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
        'language': i18n.LANG,
        'layers': [l.as_dict() for l in idx.src.layers],
        **(meta or {}),
        'have_script_docs': HAVE_DOCS,
        'nodes': idx.nodes, 'edges': idx.edges,
        'unresolved': idx.unresolved, 'dangling': idx.dangling,
        'unknown_keys': {k: v[:5] + ([f'... {len(v)}'] if len(v) > 5 else []) for k, v in sorted(idx.unknown_keys.items())},
        'parse_errors': idx.parse_errors, 'overridden_files': idx.overridden_files,
        'duplicates': idx.duplicates,
    }
    (out / 'graph.json').write_text(json.dumps(data, ensure_ascii=False), 'utf-8')
    defined = [n for n in idx.nodes.values() if n['defined']]
    stats = {
        'nodes_total': len(idx.nodes), 'nodes_defined': len(defined),
        'nodes_mod': sum(1 for n in defined if any(s['root'] != 'game' for s in n['sites'])),
        'edges_total': len(idx.edges),
        'edges_by_kind': {k: sum(1 for e in idx.edges if e['k'] == k) for k in ('call', 'cond', 'struct')},
        'edges_from_mod_files': sum(1 for e in idx.edges if e.get('root') != 'game'),
        'nodes_by_type': {t: sum(1 for n in idx.nodes.values() if n['type'] == t) for t in sorted({n['type'] for n in idx.nodes.values()})},
        'unresolved': len(idx.unresolved), 'dangling': len(idx.dangling),
        'unknown_keys': len(idx.unknown_keys), 'parse_errors': len(idx.parse_errors),
        'overridden_files': len(idx.overridden_files), 'duplicates': len(idx.duplicates),
        'have_script_docs': HAVE_DOCS,
    }
    (out / 'stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), 'utf-8')
    return stats
