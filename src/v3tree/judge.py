"""Cases, the decisions file, and expansion (who is in theme, who is pending)."""
from __future__ import annotations
import json, re
from collections import defaultdict
from pathlib import Path

from .i18n import T, type_name

SHARED_TYPES = {'var', 'gvar', 'modifier', 'law', 'culture', 'pop'}
ROOT_TYPES = ('je', 'event', 'decision')


# ---------------------------------------------------------------- index
def index_path(out_dir) -> Path:
    return Path(out_dir) / 'index' / 'graph.json'


def load_index(out_dir) -> dict:
    p = index_path(out_dir)
    if not p.exists():
        raise SystemExit(f'No index at {p}. Run: v3tree index')
    g = json.loads(p.read_text('utf-8'))
    out_e, in_e = defaultdict(list), defaultdict(list)
    for i, e in enumerate(g['edges']):
        e['i'] = i
        out_e[e['s']].append(e)
        in_e[e['t']].append(e)
    g['out'], g['in'] = out_e, in_e
    return g


def resolve_roots(g, spec):
    """A node key, any defined id, or a country TAG (every JE / event / decision that writes c:TAG)."""
    if spec in g['nodes']:
        return [spec]
    tag = f'tag:{spec}'
    if re.fullmatch(r'[A-Z0-9]{2,4}', spec) and tag in g['nodes']:
        return sorted({e['s'] for e in g['in'][tag] if e['s'].split(':', 1)[0] in ROOT_TYPES})
    hits = [k for k, n in g['nodes'].items() if n['id'] == spec and n.get('defined') and n['type'] != 'dynname']
    if hits:
        return hits
    if tag in g['nodes']:
        return sorted({e['s'] for e in g['in'][tag] if e['s'].split(':', 1)[0] in ROOT_TYPES})
    return []


def suggest(g, q, limit=30):
    q = q.lower().strip()
    if not q:
        return []
    out = []
    for k, n in g['nodes'].items():
        if not n.get('defined') and n['type'] not in ('var', 'gvar'):
            continue
        if q in n['id'].lower() or q in (n.get('name') or '').lower():
            score = (0 if n['id'].lower() == q else 1 if n['id'].lower().startswith(q) else 2, len(n['id']))
            out.append((score, {'key': k, 'id': n['id'], 'name': n.get('name'), 'type': n.get('type_zh')}))
    out.sort(key=lambda x: x[0])
    return [x[1] for x in out[:limit]]


# ---------------------------------------------------------------- cases and decisions
DEC_RE = re.compile(r'^(in|boundary|out)\s+(\S+)(?:\s+@(\S+))?\s*(?:#\s*(.*))?$')
SOFT_RE = re.compile(r'^soft\s+(yes|no)\s+(\S+)\s*(?:#\s*(.*))?$')
RULE_RE = re.compile(r'^rule\s+(\S+)\s+(in|boundary|out)(?:\s+@(\S+))?((?:\s+\w+=\S+)*)\s*(?:#\s*(.*))?$')

DECISIONS_HEADER = {
    'zh': ['// 判定记录。主题：{theme}。根：{roots}',
           '// in|boundary|out KEY [@系统] # 理由 ; rule ID VERDICT [@系统] 条件 # 理由 ; soft yes|no 写方|读方|对象 # 理由',
           '// 系统名里的 _ 显示为空格。逐项判定优先于规则；同一 KEY 以后出现的为准。'],
    'en': ['// Decisions. Theme: {theme}. Roots: {roots}',
           '// in|boundary|out KEY [@System] # reason ; rule ID VERDICT [@System] conditions # reason ; soft yes|no WRITER|READER|OBJECT # reason',
           '// "_" in a system name shows as a space. Per-node lines beat rules; a later line for the same KEY wins.'],
}
DEFAULT_RULES = [
    'rule T1 boundary @{country} type=tag # {r_tag}',
    'rule P1 boundary @{person} type=chartemplate # {r_person}',
    'rule V1 out type=seffect,strigger,svalue,onaction,decision,button,bar root=game # {r_vanilla}',
    'rule OA1 boundary @{engine} type=onaction id_regex=^on_ # {r_engine}',
]
DEFAULT_RULE_TEXT = {
    'zh': {'country': '国家', 'person': '人物', 'engine': '引擎_on_action', 'r_tag': '国家实体画成边界：展开会牵出引用该国的全部内容',
           'r_person': '人物模板只画出，不展开到该人物的全部用法', 'r_vanilla': '原版定义（未被任何 MOD 改写），只作工具',
           'r_engine': '引擎 on_action（多个系统挂载），只画不展开'},
    'en': {'country': 'Country', 'person': 'Character', 'engine': 'Engine_on_action', 'r_tag': 'countries are drawn but not expanded (expanding pulls in everything that mentions them)',
           'r_person': 'character templates are drawn but not expanded', 'r_vanilla': 'vanilla definitions no mod changes are treated as tools',
           'r_engine': 'engine on_actions (shared by many systems) are drawn but not expanded'},
}


def case_dir(out_dir, name) -> Path:
    return Path(out_dir) / 'cases' / name


def has_mod_layers(g) -> bool:
    return any(l.get('kind') == 'mod' for l in g.get('layers', []))


def new_case(out_dir, name, roots, theme, lang='zh', mode='llm', default_rules=True, vanilla_rule=True) -> Path:
    """vanilla_rule: add the "vanilla definitions are tools" rule (only sensible when a mod is loaded)."""
    d = case_dir(out_dir, name)
    d.mkdir(parents=True, exist_ok=True)
    cp = d / 'case.json'
    cp.write_text(json.dumps({'title': name, 'theme': theme, 'roots': roots, 'decisions_file': 'decisions.txt',
                              'mode': mode}, ensure_ascii=False, indent=1), 'utf-8')
    dp = d / 'decisions.txt'
    if not dp.exists():
        L = [x.format(theme=theme, roots=', '.join(roots)) for x in DECISIONS_HEADER[lang]]
        if default_rules:
            L += [r.format(**DEFAULT_RULE_TEXT[lang]) for r in DEFAULT_RULES if vanilla_rule or ' V1 ' not in r]
        dp.write_text('\n'.join(L) + '\n', 'utf-8')
    return cp


def load_decisions(case, path):
    for ln, line in enumerate(Path(path).read_text('utf-8-sig').splitlines(), 1):
        t = line.strip()
        if not t or t.startswith('//'):
            continue
        m = DEC_RE.match(t)
        if m:
            case['nodes'][m.group(2)] = {'verdict': m.group(1), 'system': (m.group(3) or '').replace('_', ' '),
                                         'reason': m.group(4) or '', 'line': ln}
            continue
        m = SOFT_RE.match(t)
        if m:
            case['soft'][m.group(2)] = {'verdict': m.group(1), 'reason': m.group(3) or '', 'line': ln}
            continue
        m = RULE_RE.match(t)
        if m:
            match = {}
            for kv in m.group(4).split():
                k, v = kv.split('=', 1)
                match[k] = v.split(',') if k == 'type' else (True if k == 'undefined' else v)
            case['rules'].append({'id': m.group(1), 'verdict': m.group(2), 'system': (m.group(3) or '').replace('_', ' '),
                                  'match': match, 'reason': m.group(5) or ''})
            continue
        raise SystemExit(f'{path}:{ln}: cannot parse: {line}')


def load_case(path):
    path = Path(path)
    if path.is_dir():
        path = path / 'case.json'
    case = json.loads(path.read_text('utf-8'))
    case['_path'] = str(path)
    case.setdefault('nodes', {})
    case.setdefault('rules', [])
    case.setdefault('soft', {})
    df = case.get('decisions_file')
    if df and (path.parent / df).exists():
        load_decisions(case, path.parent / df)
    return case


def append_decision(case, line: str):
    parts = line.split(' ', 2)
    if len(parts) < 2 or not DEC_RE.match(line.strip()):
        raise ValueError(f'not a valid decisions line: {line!r}')
    p = Path(case['_path']).parent / case.get('decisions_file', 'decisions.txt')
    with p.open('a', encoding='utf-8') as f:
        f.write(line.rstrip('\n') + '\n')


def rule_match(rule, n):
    m = rule['match']
    if 'type' in m and n['type'] not in m['type']:
        return False
    if 'key_regex' in m and not re.search(m['key_regex'], n['key']):
        return False
    if 'id_regex' in m and not re.search(m['id_regex'], n['id']):
        return False
    if 'file_regex' in m:
        files = [s['file'] for s in n.get('sites', [])]
        if not any(re.search(m['file_regex'], f) for f in files):
            return False
    if m.get('undefined') is True and n.get('defined'):
        return False
    if 'root' in m:
        roots = {x['root'] for x in n.get('sites', [])}
        if not roots:
            return False
        want = m['root']
        if want == 'mod':
            if 'game' in roots:
                return False
        elif roots != {want}:
            return False
    return True


def verdict(case, g, key):
    if key in case['_roots']:
        return {'verdict': 'in', 'system': '', 'reason': T('v.root'), 'source': 'root'}
    d = case['nodes'].get(key)
    if d:
        return {**d, 'source': 'explicit'}
    n = g['nodes'][key]
    for r in case['rules']:
        if rule_match(r, n):
            return {'verdict': r['verdict'], 'system': r.get('system', ''), 'reason': r['reason'],
                    'source': f"rule {r['id']}"}
    return None


def soft_lookup(case, w, r, obj):
    otype = obj.split(':', 1)[0]
    for k in (f'{w}|{r}|{obj}', f'{w}|*|{obj}', f'*|{r}|{obj}', f'*|*|{obj}', f'*|*|{otype}:*'):
        if k in case['soft']:
            return case['soft'][k]
    return None


def expand(case, g):
    """Return (in_nodes, boundary, judgments, pending, soft_candidates, soft_confirmed)."""
    case['_roots'] = set(case['roots'])
    included, boundary, seen = [], set(), set()
    judgments, pending = [], {}
    soft_cands, soft_conf = {}, []
    queue = list(case['_roots'])
    seen.update(queue)
    for r in queue:
        judgments.append({'node': r, 'from': None, 'verdict': 'in', 'system': '', 'reason': T('v.root'), 'source': 'root'})

    def consider(nb, frm, via):
        if nb in seen:
            return
        v = verdict(case, g, nb)
        if v is None:
            p = pending.setdefault(nb, {'node': nb, 'via': []})
            p['via'].append({'from': frm, **via})
            return
        seen.add(nb)
        judgments.append({'node': nb, 'from': frm, **v, 'via': via})
        if v['verdict'] == 'in':
            queue.append(nb)
        elif v['verdict'] == 'boundary':
            boundary.add(nb)

    i = 0
    while i < len(queue):
        cur = queue[i]
        i += 1
        included.append(cur)
        for e in g['out'][cur]:
            consider(e['t'], cur, {'dir': 'out', 'ctx': e['ctx'], 'rel': e['rel'], 'at': f"{e['file']}:{e['line']}"})
        for e in g['in'][cur]:
            consider(e['s'], cur, {'dir': 'in', 'ctx': e['ctx'], 'rel': e['rel'], 'at': f"{e['file']}:{e['line']}"})
        # soft candidates: shared objects this node writes or reads, when the object itself is not in theme
        for e in g['out'][cur]:
            obj = e['t']
            if obj.split(':', 1)[0] not in SHARED_TYPES:
                continue
            ov = verdict(case, g, obj)
            if ov and ov['verdict'] == 'in':
                continue
            acc = e.get('access') or ('write' if e['k'] == 'call' else 'read')
            other = 'read' if acc == 'write' else 'write'
            for e2 in g['in'][obj]:
                acc2 = e2.get('access') or ('write' if e2['k'] == 'call' else 'read')
                if acc2 != other or e2['s'] == cur:
                    continue
                w, r = (cur, e2['s']) if acc == 'write' else (e2['s'], cur)
                sk = f'{w}|{r}|{obj}'
                c = soft_cands.setdefault(sk, {'key': sk, 'writer': w, 'reader': r, 'object': obj,
                                               'writer_at': set(), 'reader_at': set()})
                we, re_ = (e, e2) if acc == 'write' else (e2, e)
                c['writer_at'].add(f"{we['file']}:{we['line']}")
                c['reader_at'].add(f"{re_['file']}:{re_['line']}")
                dec = soft_lookup(case, w, r, obj)
                if dec and dec['verdict'] == 'yes':
                    if sk not in {s['key'] for s in soft_conf}:
                        c['reason'] = dec['reason']
                        soft_conf.append(c)
                    consider(e2['s'], cur, {'dir': 'soft', 'ctx': obj, 'rel': 'soft', 'at': f"{e2['file']}:{e2['line']}"})
    for c in soft_cands.values():
        c['writer_at'] = sorted(c['writer_at'])
        c['reader_at'] = sorted(c['reader_at'])
        c['decision'] = soft_lookup(case, c['writer'], c['reader'], c['object'])
    return included, boundary, judgments, pending, soft_cands, soft_conf


def describe(g, key):
    n = g['nodes'][key]
    site = n['sites'][-1] if n.get('sites') else None
    return {'key': key, 'name': n.get('name'), 'type': n.get('type_zh') or type_name(n['type']),
            'at': f"{site['file']}:{site['line']}" if site else '-',
            'deg_in': len(g['in'][key]), 'deg_out': len(g['out'][key]),
            **({'disabled': n['disabled']} if n.get('disabled') else {})}


def run_expand(out_dir, case_path, g=None, quiet=False):
    """Expand a case, write pending.json next to it, print a summary grouped by file."""
    g = g or load_index(out_dir)
    case = load_case(case_path)
    inc, bnd, jud, pend, cands, conf = expand(case, g)
    pend_list = []
    for k, p in sorted(pend.items()):
        d = describe(g, k)
        d['via'] = [f"{v['from']} {v['dir']} [{v['ctx']}] {v['at']}" for v in p['via'][:6]]
        pend_list.append(d)
    undecided = [c for c in cands.values() if c['decision'] is None and (c['writer'] in inc or c['reader'] in inc)]
    cdir = Path(case['_path']).parent
    (cdir / 'pending.json').write_text(json.dumps({
        'in': len(inc), 'boundary': len(bnd), 'pending': pend_list,
        'soft_undecided': [{k: v for k, v in c.items() if k != 'decision'} for c in undecided],
    }, ensure_ascii=False, indent=1, default=list), 'utf-8')
    if not quiet:
        groups = defaultdict(list)
        for d in pend_list:
            groups[d['at'].rsplit(':', 1)[0]].append(d)
        for f in sorted(groups):
            print(f'== {f}')
            for d in groups[f]:
                more = f" (+{len(d['via'])-1})" if len(d['via']) > 1 else ''
                dis = ' DISABLED' if d.get('disabled') else ''
                print(f"  {d['key']} 「{(d['name'] or '')[:24]}」 i{d['deg_in']}/o{d['deg_out']}{dis} <- {d['via'][0][:150]}{more}")
        for c in undecided:
            print(f"S {c['key']}\n    W {c['writer_at'][:2]} R {c['reader_at'][:2]}")
        print(f'in={len(inc)} boundary={len(bnd)} pending={len(pend_list)} soft_undecided={len(undecided)} soft_confirmed={len(conf)}')
    return g, case, inc, bnd, jud, pend, cands, conf
