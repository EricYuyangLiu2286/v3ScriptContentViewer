"""Operations shared by the command line and the web server."""
from __future__ import annotations
import json, os, shutil, stat, sys, time
from pathlib import Path

from . import config as C, index as I, judge as J, search as S, render as R, report as RP, i18n
from .sources import Sources, layers_from_config, LineCache


def out_dir(cfg) -> Path:
    return Path(cfg.get('output_dir') or C.home() / 'output')


def _clear_readonly(func, path, _exc):
    # OneDrive and some sync tools mark folders read-only; Windows then refuses to remove them
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_tree(path):
    """shutil.rmtree that also removes read-only folders and files (otherwise an empty folder is left behind)."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_readonly)
    else:
        shutil.rmtree(path, onerror=_clear_readonly)


def _rmdir_if_empty(d: Path):
    try:
        if d.is_dir() and not any(d.iterdir()):
            os.chmod(d, stat.S_IWRITE)
            d.rmdir()
    except OSError:
        pass


def move_output(old, new) -> list:
    """Move the index and every session from one output folder to another. Nothing already in the new
    folder is overwritten: an index or a session of the same name there is left and reported.
    Returns [(level, message)] for the settings page."""
    old, new = Path(old).resolve(), Path(new).resolve()
    if old == new or not old.is_dir():
        return []
    new.mkdir(parents=True, exist_ok=True)
    moved, skipped = 0, []
    if (old / 'index').is_dir():
        if (new / 'index').exists():
            skipped.append('index')
        else:
            shutil.move(str(old / 'index'), str(new / 'index'))
    if (old / 'cases').is_dir():
        (new / 'cases').mkdir(exist_ok=True)
        for d in sorted((old / 'cases').iterdir()):
            if (new / 'cases' / d.name).exists():
                skipped.append(d.name)
            else:
                shutil.move(str(d), str(new / 'cases' / d.name))
                moved += 1
    for d in (old / 'cases', old):   # tidy up only folders the move left empty
        _rmdir_if_empty(d)
    out = [('ok', i18n.T('ui.out_moved', n=moved, p=new))]
    if skipped:
        out.append(('note', i18n.T('ui.out_move_skip', x=', '.join(skipped), p=old)))
    return out


def config_fingerprint(cfg) -> str:
    keep = {k: cfg.get(k) for k in ('game', 'mods', 'languages', 'ignore', 'extra_folders', 'ui_language')}
    return json.dumps(keep, sort_keys=True, ensure_ascii=False)


def build_index(cfg, progress=None, verbose=True):
    i18n.set_lang(cfg.get('ui_language', 'en'))
    layers = layers_from_config(cfg)
    if not layers:
        raise SystemExit(C.msg('need_path'))
    src = Sources(layers, cfg.get('ignore') or [])
    I.build(src, cfg.get('languages') or ['english'], C.script_docs_dir(cfg), cfg.get('extra_folders') or {},
            verbose=verbose, progress=progress)
    det = cfg.get('detected') or {}
    meta = {'game_version': det.get('game_version'), 'config_fingerprint': config_fingerprint(cfg)}
    stats = I.save(out_dir(cfg), meta=meta)
    (Path(out_dir(cfg)) / 'index' / 'meta.json').write_text(json.dumps(
        {**meta, 'built': time.strftime('%Y-%m-%d %H:%M'), 'nodes': stats['nodes_total'], 'edges': stats['edges_total'],
         'layers': [l.as_dict() for l in layers], 'language': i18n.LANG}, ensure_ascii=False, indent=1), 'utf-8')
    g = J.load_index(out_dir(cfg))
    RP.unresolved_md(g, out_dir(cfg))
    return stats


def index_status(cfg):
    mp = Path(out_dir(cfg)) / 'index' / 'meta.json'
    if not mp.exists():
        return {'exists': False}
    m = json.loads(mp.read_text('utf-8'))
    return {'exists': True, 'nodes': m['nodes'], 'edges': m['edges'], 'game_version': m.get('game_version'),
            'built': m.get('built'), 'stale': m.get('config_fingerprint') != config_fingerprint(cfg)}


def case_path(cfg, name) -> Path:
    return J.case_dir(out_dir(cfg), name) / 'case.json'


def list_cases(cfg):
    base = Path(out_dir(cfg)) / 'cases'
    out = []
    if base.exists():
        for d in sorted(base.iterdir()):
            cp = d / 'case.json'
            if cp.exists():
                c = json.loads(cp.read_text('utf-8'))
                out.append({'name': d.name, 'title': c.get('title'), 'theme': c.get('theme'), 'roots': c.get('roots'),
                            'mode': c.get('mode', 'llm'), 'accepted': (c.get('search') or {}).get('accepted', False),
                            'has_map': (d / 'map.html').exists(), 'mtime': d.stat().st_mtime})
    return sorted(out, key=lambda x: -x['mtime'])


def render_case(cfg, name, g=None):
    """Write map.html, report.md, subgraph.json for a case (AI-judged or UI session)."""
    i18n.set_lang(cfg.get('ui_language', 'en'))
    od = out_dir(cfg)
    g = g or J.load_index(od)
    cp = case_path(cfg, name)
    case = J.load_case(cp)
    if case.get('mode') == 'ui':
        inc, bnd, jud, view = S.drawn_from_session(case, g)
        cands, conf = {}, []
        inc_set = set(inc)
        info = {k: {'v': 'in' if k in inc_set else 'boundary', 'sys': v['sys'], 'why': v['why'] or i18n.T('v.unjudged'),
                    'src': v['src'] or 'ui'} for k, v in view.items()}
    else:
        _, case, inc, bnd, jud, pend, cands, conf = J.run_expand(od, cp, g=g, quiet=True)
        info = R.info_from_judgments(jud)
        for o in pend:
            info.setdefault(o, {'v': 'unjudged_plain', 'why': ''})
    pending_n = 0 if case.get('mode') == 'ui' else len(pend)
    src = R.sources_of(g)
    cache = LineCache(src)
    nodes, edges, hidden = R.build_payload(g, inc, bnd, info, conf, cache)
    html = R.write_outputs(cp.parent, g, case, nodes, edges, hidden)
    case['_out_dir'] = str(od)
    summary = RP.coverage(g, src, case, inc, bnd, jud, cands, conf, nodes, edges, cp.parent / 'report.md',
                          cfg.get('languages') or ['english'])
    summary['pending'] = pending_n
    summary['map'] = str(html)
    summary['report'] = str(cp.parent / 'report.md')
    return summary


def session_payload(cfg, name, g):
    """Live view of a UI session for the web app (with code snippets)."""
    cp = case_path(cfg, name)
    case = J.load_case(cp)
    view = S.view_nodes(case, g)
    inc = [k for k, v in view.items() if v['v'] in ('in', 'unjudged') and not v['stopped']]
    bnd = [k for k in view if k not in set(inc)]
    nodes, edges, hidden = R.build_payload(g, inc, bnd, view, (), LineCache(R.sources_of(g)))
    s = S.state(case)
    counts = {'i': sum(1 for v in view.values() if v['v'] == 'in'), 'u': sum(1 for v in view.values() if v['v'] == 'unjudged' and not v['stopped']),
              'b': sum(1 for v in view.values() if v['v'] == 'boundary'), 's': sum(1 for v in view.values() if v['v'] == 'unjudged' and v['stopped'])}
    meta = R.meta_for(g, case)
    meta.update({'round': s['round'], 'counts': counts, 'stop': s['stop'], 'accepted': s.get('accepted', False),
                 'can_undo': bool(s['history'])})
    return {'meta': meta, 'nodes': nodes, 'edges': edges, 'hidden': hidden}


def auto_search(cfg, root_spec, steps=3, name=None, theme='', stop=None, accept=True):
    """Command-line automatic mode: search N steps with the stop rules, optionally complete, render."""
    i18n.set_lang(cfg.get('ui_language', 'en'))
    od = out_dir(cfg)
    g = J.load_index(od)
    roots = J.resolve_roots(g, root_spec)
    if not roots:
        raise SystemExit(f'root not found: {root_spec}')
    name = name or safe_name(root_spec)
    cp = J.new_case(od, name, roots, theme, lang=i18n.LANG, mode='ui', vanilla_rule=J.has_mod_layers(g))
    case = J.load_case(cp)
    S.search(case, g, steps, stop)
    if accept:
        S.finalize(case, g, i18n.LANG)
    return render_case(cfg, name, g)


def safe_name(s):
    import re
    return re.sub(r'[^A-Za-z0-9_.\-]+', '_', s).strip('_')[:60] or 'case'
