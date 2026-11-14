"""Export a character and its binding paths with optional evidence-backed context."""
import json
from collections import deque
from pathlib import Path

from . import judge, render
from .sources import LineCache

BINDINGS = {'save_scope_as','set_variable','set_global_variable','scripted_character_receiver','event_scope_argument','script_scope_result'}

def dossier(g, roots, context, folder, title, with_code=False):
    missing = set(roots + context) - g['nodes'].keys()
    if missing:
        raise ValueError('Unknown nodes: '+', '.join(sorted(missing)))
    included = dict.fromkeys(roots, '研究起点 / root')
    queue = deque(roots)
    while queue:
        key = queue.popleft()
        if key.startswith('charscope:'):
            for e in g['in'][key]:
                if e['rel']=='save_scope_as' and e['s'].startswith('charselector:') and e['s'] not in included:
                    included[e['s']] = '为本作用域提供候选 / competing source'
                    queue.append(e['s'])
        if key.startswith('character:'):
            for e in g['in'][key]:
                if e['rel']=='candidate_template' and e['s'] not in included:
                    included[e['s']] = '候选条件（可能含排除或回退） / selector condition'
                    queue.append(e['s'])
        for e in g['out'][key]:
            target = e['t']
            if e['rel']=='scripted_character_receiver' and len({x['s'] for x in g['in'][target]})>1:
                continue  # shared helper: inspecting it is useful, importing every other caller is not
            if e['rel'] in BINDINGS and target not in included:
                included[target] = '人物保存或传递 / handle: '+e['file']+':'+str(e['line'])
                queue.append(target)
    for key in context:
        included.setdefault(key, '案例卡列出的阶段 / explicit case context')
    neighbours = {e['t'] for k in included for e in g['out'][k]}
    neighbours.update(e['s'] for k in included for e in g['in'][k])
    boundary = neighbours - included.keys()
    info = {k:{'v':'in','why':reason} for k,reason in included.items()}
    info.update({k:{'v':'boundary','why':'直接相邻 / direct neighbour'} for k in boundary})
    nodes,edges,hidden = render.build_payload(g,included,boundary,info,cache=LineCache(render.sources_of(g)),with_code=with_code)
    if not with_code:
        # Archive third-party diagrams as identifiers and evidence, without importing authored prose.
        mods = {layer['id'] for layer in g.get('layers',[]) if layer['kind']=='mod'}
        if mods:
            def display(key, original):
                n = g['nodes'][key]
                if n['type']!='character' and (not n['sites'] or any(s['root'] in mods for s in n['sites'])):
                    return n['id']
                return original
            for n in nodes:
                n['name'] = display(n['k'],n['name'])
            for neighbours in hidden.values():
                for n in neighbours:
                    n['name'] = display(n['o'],n['name'])
    folder = Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    case = {'roots':roots,'theme':title,'title':title}
    render.write_outputs(folder,g,case,nodes,edges,hidden)
    (folder/'decisions.txt').write_text('\n'.join(f"{info[k]['v']} {k} # {info[k]['why']}" for k in sorted(info))+'\n','utf-8')
    incident = {e['i'] for key in included for e in g['out'][key]+g['in'][key]}
    sites = sum(len(e['sites']) for e in edges)
    if len(incident) != sites:
        raise ValueError(f'Incomplete evidence: {sites} sites for {len(incident)} edges')
    summary = {'roots':roots,'context':context,'expanded':len(included),'boundary':len(boundary),
               'raw_edges':len(incident),'drawn_edges':len(edges),'source_sites':sites}
    (folder/'coverage.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
    return summary
