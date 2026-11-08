"""Build the viewer payload for a set of drawn nodes, and export the standalone HTML."""
from __future__ import annotations
import json, time
from collections import defaultdict
from pathlib import Path

from . import i18n
from .i18n import T
from .sources import Sources, LineCache, layers_from_dicts

WEB = Path(__file__).resolve().parent / 'web'
MAX_SNIPPET = 90


def sources_of(g) -> Sources:
    return Sources(layers_from_dicts(g.get('layers', [])))


def build_payload(g, inc, bnd, info, conf=(), cache: LineCache | None = None, with_code=True):
    """info: key -> {v, sys, why, src, from, stopped, fresh}. Hard edges need one endpoint in `inc`."""
    cache = cache or LineCache(sources_of(g))
    inc_set = set(inc)
    drawn = inc_set | set(bnd)
    nodes = []
    for key in sorted(drawn):
        n = g['nodes'][key]
        j = info.get(key, {})
        site = n['sites'][-1] if n.get('sites') else None
        snippet = ''
        if site and with_code:
            ls = cache.lines(site['root'], site['file'])
            a, b = site['line'], min(site['end'], site['line'] + MAX_SNIPPET - 1)
            snippet = '\n'.join(ls[a - 1:b])
            if site['end'] > b:
                snippet += f"\n… ({site['end'] - site['line'] + 1} lines; {site['file']}:{site['line']})"
        nodes.append({
            'k': key, 't': n['type'], 'tz': n.get('type_zh') or n['type'], 'id': n['id'], 'name': n.get('name', n['id']),
            'noloc': bool(n.get('no_loc')), 'nk': n.get('name_key'), 'ls': n.get('loc_src'),
            'v': j.get('v', 'in'), 'sys': j.get('sys', ''), 'why': j.get('why', ''), 'src': j.get('src', ''),
            'from': j.get('from'), 'stopped': bool(j.get('stopped')), 'fresh': bool(j.get('fresh')),
            'dis': n.get('disabled'), 'sites': n.get('sites', []), 'code': snippet, 'defined': n.get('defined', False),
        })
    groups = defaultdict(list)
    for key in inc_set:
        for e in g['out'][key] + g['in'][key]:
            if e['s'] in drawn and e['t'] in drawn:
                groups[(e['s'], e['t'], e['k'], e['ctx'])].append(e)
    edges, seen_i = [], set()
    for (s, t, k, ctx), es in groups.items():
        es = [e for e in es if e['i'] not in seen_i]
        if not es:
            continue
        seen_i.update(e['i'] for e in es)
        sites = []
        for e in es[:12]:
            ls = cache.lines(e.get('root', 'game'), e['file'])
            line = ls[e['line'] - 1].strip() if 0 < e['line'] <= len(ls) else ''
            block = ' '.join(x.strip() for x in ls[e['line'] - 1:min(e.get('end', e['line']), e['line'] + 8)]) if e.get('end') else ''
            sites.append({'at': f"{e['file']}:{e['line']}" + (f"-{e['end']}" if e.get('end') else ''), 'rel': e['rel'],
                          'root': e.get('root', 'game'), 'file': e['file'], 'line': e['line'], 'end': e.get('end', e['line']),
                          'code': line[:200], **({'block': block[:300]} if block else {}),
                          **({'via': e['via']} if e.get('via') else {}), **({'acc': e['access']} if e.get('access') else {})})
        edges.append({'s': s, 't': t, 'k': k, 'ctx': ctx, 'n': len(es), 'flags': sorted({f for e in es for f in e.get('flags', [])}),
                      'sites': sites, 'rels': sorted({e['rel'] for e in es}), 'soft': False})
    # soft edges: drawn to the shared object when it is on the map, otherwise writer -> reader
    soft_out = {}
    for c in conf:
        w, r, obj = c['writer'], c['reader'], c['object']
        pairs = []
        if obj in drawn:
            if w not in inc_set:
                pairs.append((w, obj))
            if r not in inc_set:
                pairs.append((obj, r))
        else:
            pairs.append((w, r))
        for s, t in pairs:
            if s not in drawn or t not in drawn:
                continue
            se = soft_out.setdefault((s, t, obj), {'s': s, 't': t, 'k': 'soft', 'ctx': g['nodes'][obj]['id'], 'n': 0, 'flags': [],
                                                   'sites': [], 'rels': ['soft'], 'soft': True, 'obj': obj, 'why': c.get('reason', '')})
            se['n'] += 1
            se['sites'].append({'at': 'W ' + '; '.join(c['writer_at'][:3]), 'rel': 'write', 'code': w})
            se['sites'].append({'at': 'R ' + '; '.join(c['reader_at'][:3]), 'rel': 'read', 'code': r})
    edges += list(soft_out.values())
    hidden = {}
    for key in drawn:
        lst = []
        for d, es in (('out', g['out'][key]), ('in', g['in'][key])):
            for e in es:
                o = e['t'] if d == 'out' else e['s']
                if o in drawn:
                    continue
                j = info.get(o)
                lst.append({'d': d, 'o': o, 'name': g['nodes'][o].get('name', o), 'ctx': e['ctx'], 'at': f"{e['file']}:{e['line']}",
                            'v': (j or {}).get('v', 'unjudged_boundary' if key in bnd else 'unjudged_plain'),
                            'why': (j or {}).get('why', '')})
        if lst:
            hidden[key] = lst[:400]
    return nodes, edges, hidden


def info_from_judgments(jud):
    return {j['node']: {'v': j['verdict'], 'sys': j.get('system', ''), 'why': j.get('reason', ''),
                        'src': j.get('source', ''), 'from': j.get('from')} for j in jud}


def meta_for(g, case):
    return {'title': case.get('title', ''), 'theme': case.get('theme', ''), 'roots': case['roots'],
            'generated': time.strftime('%Y-%m-%d %H:%M'), 'layers': g.get('layers', []),
            'game_version': g.get('game_version'), 'language': g.get('language')}


def page(data: dict, title: str, lang=None) -> str:
    html = (WEB / 'viewer.html').read_text('utf-8')
    css = (WEB / 'viewer.css').read_text('utf-8')
    js = (WEB / 'viewer.js').read_text('utf-8')
    strings = json.dumps(i18n.table(lang), ensure_ascii=False).replace('</', '<\\/')
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    return (html.replace('/*__CSS__*/', css).replace('/*__JS__*/', js).replace('/*__DATA__*/null', payload)
            .replace('/*__L__*/null', strings).replace('__TITLE__', title).replace('__LANG__', 'zh-CN' if i18n.LANG == 'zh' else 'en'))


def write_outputs(case_dir: Path, g, case, nodes, edges, hidden):
    meta = meta_for(g, case)
    data = {'meta': meta, 'nodes': nodes, 'edges': edges, 'hidden': hidden}
    (case_dir / 'subgraph.json').write_text(json.dumps({'meta': meta, 'nodes': [{k: v for k, v in n.items() if k != 'code'} for n in nodes],
                                                        'edges': edges}, ensure_ascii=False, indent=1), 'utf-8')
    out = case_dir / 'map.html'
    out.write_text(page(data, f"{case.get('title', '')} · {T('ui.app')}"), 'utf-8')
    return out
