"""Step search: grow a tree from the root N steps at a time, prune by hand, accept.

State lives in case.json ("search") and every judgment is appended to the same
decisions file the AI path uses, so either path can continue the other's work.
"""
from __future__ import annotations
import json
from pathlib import Path

from . import judge
from .i18n import T

DEFAULT_STOP = {
    'hub': 40,                                    # nodes referenced more than this are not expanded
    'types': ['tag', 'chartemplate', 'culture', 'law', 'ideology', 'onaction', 'pop'],
    'vanilla': True,                              # definitions only the game defines are not expanded
}
MAX_STEPS = 10
UI_REASON = {
    'in': ('界面：接受', 'UI: accepted'),
    'boundary': ('界面：只画不展开', 'UI: draw, do not expand'),
    'out': ('界面：去掉', 'UI: removed'),
    'final_in': ('界面：验收时接受', 'UI: accepted at sign-off'),
    'final_stop': ('界面：停止规则节点，验收时画为边界', 'UI: stop-rule node, drawn as boundary at sign-off'),
}


def _r(key, lang):
    zh, en = UI_REASON[key]
    return zh if lang == 'zh' else en


def neighbours(g, k):
    for e in g['out'][k]:
        yield e['t']
    for e in g['in'][k]:
        yield e['s']


def state(case):
    s = case.setdefault('search', {})
    s.setdefault('stop', dict(DEFAULT_STOP))
    s.setdefault('found', {})          # key -> round it was found in
    s.setdefault('expanded', [])
    s.setdefault('round', 0)
    s.setdefault('history', [])
    return s


def save_case(case):
    p = Path(case['_path'])
    keep = {k: v for k, v in case.items() if not k.startswith('_') and k not in ('nodes', 'rules', 'soft')}
    p.write_text(json.dumps(keep, ensure_ascii=False, indent=1), 'utf-8')


def stop_reason(g, k, stop):
    n = g['nodes'][k]
    if n['type'] in set(stop.get('types') or []):
        return 'type'
    deg = len(g['in'][k]) + len(g['out'][k])
    if stop.get('hub') and deg > int(stop['hub']):
        return 'hub'
    if stop.get('vanilla') and n.get('sites') and all(s['root'] == 'game' for s in n['sites']):
        return 'vanilla'
    return None


def classify(case, g, k):
    """('in'|'boundary'|'out'|None, verdict dict or None)"""
    v = judge.verdict(case, g, k)
    return (v['verdict'] if v else None), v


def expandable(case, g, k, stop):
    if k in case['_roots']:
        return True
    v, _ = classify(case, g, k)
    if v == 'in':
        return True
    if v is None:
        return stop_reason(g, k, stop) is None
    return False


def _snapshot(case, s):
    dp = Path(case['_path']).parent / case.get('decisions_file', 'decisions.txt')
    n = len(dp.read_text('utf-8').splitlines()) if dp.exists() else 0
    s['history'].append({'lines': n, 'found': dict(s['found']), 'expanded': list(s['expanded']), 'round': s['round']})
    s['history'] = s['history'][-50:]


def search(case, g, steps=3, stop=None):
    """Expand from every expandable, not yet expanded node by up to `steps` steps."""
    case['_roots'] = set(case['roots'])
    fresh = 'search' not in case or 'stop' not in case['search']
    s = state(case)
    if fresh and not judge.has_mod_layers(g):
        s['stop']['vanilla'] = False      # vanilla-only index: everything is vanilla
    if stop:
        s['stop'] = {**s['stop'], **stop}
    stop = s['stop']
    steps = max(1, min(MAX_STEPS, int(steps)))
    _snapshot(case, s)
    s['round'] += 1
    for r in case['roots']:
        s['found'].setdefault(r, 0)
    expanded = set(s['expanded'])
    frontier = [k for k in s['found'] if k not in expanded and expandable(case, g, k, stop)]
    for _ in range(steps):
        nxt = []
        for c in frontier:
            if c in expanded:
                continue
            expanded.add(c)
            for nb in neighbours(g, c):
                if nb in s['found']:
                    continue
                v, _ = classify(case, g, nb)
                if v == 'out':
                    continue
                s['found'][nb] = s['round']
                if expandable(case, g, nb, stop):
                    nxt.append(nb)
        frontier = nxt
    s['expanded'] = sorted(expanded)
    save_case(case)
    return s


def judge_node(case, g, key, verdict, lang='zh', system=''):
    """Record a UI judgment and update the found set (removing pulls away what only hung on it)."""
    case['_roots'] = set(case['roots'])
    s = state(case)
    if key in case['_roots']:
        return s   # a root is always in theme; a verdict for it would be written but never used
    _snapshot(case, s)
    sysname = (system or ('界面' if lang == 'zh' else 'UI')).replace(' ', '_')
    line = f"{verdict} {key}" + (f" @{sysname}" if verdict == 'boundary' else '') + f" # {_r(verdict, lang)}"
    judge.append_decision(case, line)
    case['nodes'][key] = {'verdict': verdict, 'system': system, 'reason': _r(verdict, lang)}
    if verdict == 'out':
        _prune(case, g, s)
    # an accepted node that was stopped is not in "expanded" yet, so the next search grows from it
    save_case(case)
    return s


def _prune(case, g, s):
    """Keep only found nodes still reachable from a root through found, not-removed nodes."""
    found = s['found']
    keep, queue = set(), [r for r in case['roots'] if r in found]
    keep.update(queue)
    while queue:
        c = queue.pop()
        if c not in case['_roots'] and not expandable(case, g, c, s['stop']):
            continue   # removed, boundary and stop-rule nodes do not carry what lies behind them
        for nb in neighbours(g, c):
            if nb in found and nb not in keep:
                nv, _ = classify(case, g, nb)
                if nv == 'out':
                    continue
                keep.add(nb)
                queue.append(nb)
    for k in list(found):
        if k not in keep:
            del found[k]
    s['expanded'] = [k for k in s['expanded'] if k in found]


def undo(case):
    s = state(case)
    if not s['history']:
        return False
    h = s['history'].pop()
    dp = Path(case['_path']).parent / case.get('decisions_file', 'decisions.txt')
    if dp.exists():
        lines = dp.read_text('utf-8').splitlines()
        dp.write_text('\n'.join(lines[:h['lines']]) + '\n', 'utf-8')
    s['found'], s['expanded'], s['round'] = h['found'], h['expanded'], h['round']
    save_case(case)
    return True


def view_nodes(case, g):
    """Verdict view of the current session: {key: info} for every found node that is not removed."""
    case['_roots'] = set(case['roots'])
    s = state(case)
    out = {}
    for k, rnd in s['found'].items():
        v, vd = classify(case, g, k)
        if v == 'out':
            continue
        stopped = None if k in case['_roots'] else stop_reason(g, k, s['stop'])
        info = {'v': v or 'unjudged', 'round': rnd, 'fresh': rnd == s['round'] and rnd > 0,
                'stopped': bool(stopped and v is None), 'stop_reason': stopped,
                'sys': (vd or {}).get('system', ''), 'why': (vd or {}).get('reason', ''),
                'src': (vd or {}).get('source', '')}
        out[k] = info
    return out


def finalize(case, g, lang='zh'):
    """Sign-off: undecided nodes become in-theme; stop-rule nodes become boundary."""
    case['_roots'] = set(case['roots'])
    for k, info in view_nodes(case, g).items():
        if info['v'] != 'unjudged':
            continue
        if info['stopped']:
            sysname = T(f"type.{g['nodes'][k]['type']}").replace(' ', '_')
            judge.append_decision(case, f"boundary {k} @{sysname} # {_r('final_stop', lang)}")
        else:
            judge.append_decision(case, f"in {k} # {_r('final_in', lang)}")
    case.setdefault('search', {})['accepted'] = True
    save_case(case)
    return judge.load_case(case['_path'])


def drawn_from_session(case, g):
    """(in list, boundary set, judgments) for rendering a signed-off or in-progress session."""
    case['_roots'] = set(case['roots'])
    view = view_nodes(case, g)
    inc = [k for k, i in view.items() if i['v'] in ('in', 'unjudged') and not i['stopped']]
    bnd = {k for k, i in view.items() if i['v'] == 'boundary' or (i['v'] == 'unjudged' and i['stopped'])}
    jud = []
    for k, i in view.items():
        v = 'in' if k in inc else 'boundary'
        jud.append({'node': k, 'from': None, 'verdict': v, 'system': i['sys'], 'reason': i['why'] or T('v.unjudged'),
                    'source': i['src'] or 'ui'})
    return inc, bnd, jud, view
