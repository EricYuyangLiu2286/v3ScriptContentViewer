"""Coverage report: index numbers, subtree numbers, unresolved, soft decisions, judgments,
reverse check, spot check, and suspected problems. Plus the global unresolved list."""
from __future__ import annotations
import json, random, re, time
from collections import Counter, defaultdict
from pathlib import Path

from . import i18n
from .sources import Sources


def tr(zh, en):
    return zh if i18n.LANG == 'zh' else en


# ---------------------------------------------------------------- checks
def reverse_check(g, src: Sources, nodes_in):
    """Occurrences of each in-theme id in mod script files (game files when no mod is loaded) that no edge
    or definition explains. Files replaced by a later layer are skipped (they are not loaded)."""
    ids = {}
    for k in nodes_in:
        n = g['nodes'][k]
        if n['type'] not in ('pop', 'tag', 'culture'):
            ids.setdefault(n['id'], [])
    if not ids:
        return []
    for k, n in g['nodes'].items():          # same id, other object (variable vs template, namespace ...)
        if n['id'] in ids:
            ids[n['id']].append(k)
    want = {k for ks in ids.values() for k in ks}
    spans = defaultdict(list)
    for e in g['edges']:
        for k in (e['s'], e['t']):
            if k in want:
                spans[(e.get('root'), e['file'])].append((e['line'], e.get('end', e['line']), k))
        cs = (e.get('via') or {}).get('call_site')
        if cs and e['t'] in want:
            f, l = cs.rsplit(':', 1)
            for layer in src.layers:
                spans[(layer.id, f)].append((int(l), int(l) + 3, e['t']))
    for k in want:
        for s_ in g['nodes'][k].get('sites', []):
            spans[(s_['root'], s_['file'])].append((s_['line'], s_['end'], k))
    pat = re.compile(r'(?<![\w.])(' + '|'.join(sorted((re.escape(i) for i in ids), key=len, reverse=True)) + r')(?![\w.])')
    later = {}
    for i, layer in enumerate(src.layers):
        later[layer.id] = {l.path for l in src.layers[i + 1:]}
    out = []
    for layer in (src.mod_layers() or src.layers):     # vanilla-only: check the game files themselves
        files = list(layer.path.glob('common/**/*.txt')) + list(layer.path.glob('events/**/*.txt')) + list(layer.path.glob('gui/**/*.gui'))
        for p in files:
            rel = p.relative_to(layer.path).as_posix()
            if any((lp / rel).exists() for lp in later[layer.id]):
                continue
            try:
                lines = p.read_text('utf-8-sig', errors='replace').split('\n')
            except OSError:
                continue
            sp = spans.get((layer.id, rel), [])
            for i, line in enumerate(lines, 1):
                code = line.split('#', 1)[0]
                if code.lstrip().startswith('namespace'):
                    continue
                for m in pat.finditer(code):
                    pre = code[max(0, m.start() - 22):m.start()]
                    if pre.endswith('scope:') or re.search(r'(save_scope_as|clear_saved_scope|save_temporary_scope_as)\s*=\s*$', pre):
                        continue
                    if re.search(r'\b(desc|name|title|text|tooltip|custom_tooltip|localization_key)\s*=\s*"?$', pre):
                        continue   # a localisation key that happens to equal the id
                    keys = set(ids[m.group(1)])
                    if any(a <= i <= b and k in keys for a, b, k in sp):
                        continue
                    out.append({'id': m.group(1), 'at': f'{layer.name}: {rel}:{i}', 'code': line.strip()[:160],
                                'unindexed': rel.startswith('gui/')})
    return out


def _text_reads(src: Sources, languages):
    blobs = []
    for layer in src.mod_layers():
        pats = [f'localization/{l}/**/*.yml' for l in set(languages) | {'english'}] + ['gui/**/*.gui']
        for pat in pats:
            for p in layer.path.glob(pat):
                try:
                    blobs.append((f'{layer.name}: ' + p.relative_to(layer.path).as_posix(), p.read_text('utf-8-sig', errors='replace')))
                except OSError:
                    pass
    return blobs


def _executed_elsewhere(g, owner, target, depth=5):
    start = {owner} | {e['s'] for e in g['in'][owner] if e['k'] == 'call'}
    seen, frontier = set(start), list(start)
    for _ in range(depth):
        nxt = []
        for k in frontier:
            for e in g['out'][k]:
                if e['k'] != 'call':
                    continue
                if e['t'] == target and 'tooltip_only' not in e.get('flags', []):
                    return f"{e['file']}:{e['line']}"
                if e['t'].split(':', 1)[0] in ('seffect', 'event', 'je', 'onaction') and e['t'] not in seen:
                    seen.add(e['t']); nxt.append(e['t'])
        frontier = nxt
    return None


def findings(g, src, inc, languages):
    out, texts = [], None
    for k in inc:
        n = g['nodes'][k]
        t = n['type']
        ins, outs = g['in'][k], g['out'][k]
        if t in ('var', 'gvar'):
            w = [e for e in ins if e.get('access') == 'write']
            r = [e for e in ins if e.get('access') != 'write']
            if w and not r:
                texts = texts if texts is not None else _text_reads(src, languages)
                shown = [f for f, b in texts if re.search(r'(?<![\w])' + re.escape(n['id']) + r'(?![\w])', b)]
                if shown:
                    out.append((tr('只在文本中读取', 'Read only in text'), k,
                                tr(f"脚本无读取，只在 {shown[0]} 等 {len(shown)} 个文本文件中显示（写入如 {w[0]['file']}:{w[0]['line']}）",
                                   f"No script reads it; shown in {shown[0]} and {len(shown) - 1} more text files (written at {w[0]['file']}:{w[0]['line']})")))
                else:
                    out.append((tr('只写不读', 'Written, never read'), k,
                                tr(f"写入 {len(w)} 处（如 {w[0]['file']}:{w[0]['line']}），脚本、本地化与 GUI 中均无读取",
                                   f"Written {len(w)} times (e.g. {w[0]['file']}:{w[0]['line']}); no script, localisation or GUI reads it")))
            if r and not w:
                out.append((tr('只读不写', 'Read, never written'), k,
                            tr(f"读取 {len(r)} 处（如 {r[0]['file']}:{r[0]['line']}），没有任何写入",
                               f"Read {len(r)} times (e.g. {r[0]['file']}:{r[0]['line']}); nothing writes it")))
        if t == 'event' and not n.get('disabled'):
            if not [e for e in ins if e['rel'] in ('trigger_event', 'random_event', 'onaction_event', 'via_param')]:
                out.append((tr('无触发入口', 'Nothing fires it'), k,
                            tr('没有 trigger_event / random_events / on_action 指向该事件', 'No trigger_event / random_events / on_action points at this event')))
        if t in ('seffect', 'strigger', 'svalue') and not ins:
            out.append((tr('无调用', 'Never called'), k, tr('定义了但没有任何调用', 'Defined but never used')))
        if not n.get('defined') and t not in ('var', 'gvar', 'pop'):
            out.append((tr('目标未定义', 'Undefined target'), k, tr('被引用但没有定义', 'Referenced but not defined')))
        for e in outs:
            if 'tooltip_only' in e.get('flags', []) and e['k'] == 'call' and not _executed_elsewhere(g, k, e['t']):
                out.append((tr('仅提示、未见执行', 'Tooltip only'), k,
                            tr(f"{e['file']}:{e['line']} 的 {e['rel']} → {e['t']} 写在 show_as_tooltip 内；同一事件及其调用的效果中未见实际执行",
                               f"{e['file']}:{e['line']}: {e['rel']} → {e['t']} sits in show_as_tooltip and is not executed elsewhere in this chain")))
            if 'disabled' in e.get('flags', []):
                out.append((tr('禁用分支', 'Disabled branch'), k,
                            tr(f"{e['file']}:{e['line']} 的 {e['rel']} → {e['t']} 位于 always = no 条件之下",
                               f"{e['file']}:{e['line']}: {e['rel']} → {e['t']} sits under always = no")))
    return out


# ---------------------------------------------------------------- report
def coverage(g, src, case, inc, bnd, jud, cands, conf, nodes, edges, out_path: Path, languages=('english',)):
    st = json.loads((Path(case['_out_dir']) / 'index' / 'stats.json').read_text('utf-8'))
    hard = [e for e in edges if not e['soft']]
    soft = [e for e in edges if e['soft']]
    bset, sub = set(bnd), set(inc) | set(bnd)
    L = []
    L.append(tr(f"# 覆盖率报告：{case.get('title')}\n", f"# Coverage report: {case.get('title')}\n"))
    L.append(tr(f"- 主题：{case.get('theme')}\n- 根：{', '.join(case['roots'])}\n- 生成：{time.strftime('%Y-%m-%d %H:%M')}",
                f"- Theme: {case.get('theme')}\n- Roots: {', '.join(case['roots'])}\n- Generated: {time.strftime('%Y-%m-%d %H:%M')}"))
    L.append(tr('- 数据层（按加载顺序）：', '- Layers (load order): ') + ' → '.join(f"{l['name']}" for l in g.get('layers', [])) + '\n')
    L.append(tr('## 1. 全局索引\n', '## 1. Global index\n'))
    L.append(tr(f"- 节点 {st['nodes_total']}（有定义 {st['nodes_defined']}，其中 MOD 定义 {st['nodes_mod']}）；边 {st['edges_total']}（调用 {st['edges_by_kind']['call']}，条件读取 {st['edges_by_kind']['cond']}，结构 {st['edges_by_kind']['struct']}）。",
                f"- Nodes {st['nodes_total']} (defined {st['nodes_defined']}, by mods {st['nodes_mod']}); edges {st['edges_total']} (call {st['edges_by_kind']['call']}, read {st['edges_by_kind']['cond']}, structure {st['edges_by_kind']['struct']})."))
    L.append(tr(f"- 未解析 {st['unresolved']}；目标未定义 {st['dangling']}；未识别键 {st['unknown_keys']}；解析失败 {st['parse_errors']}；被后层取代的文件 {st['overridden_files']}；同名定义 {st['duplicates']}。",
                f"- Unresolved {st['unresolved']}; undefined targets {st['dangling']}; unknown keys {st['unknown_keys']}; parse failures {st['parse_errors']}; files replaced by a later layer {st['overridden_files']}; duplicate definitions {st['duplicates']}."))
    if not st.get('have_script_docs'):
        L.append(tr('- 没有接口清单（effects.log 等），“未识别键”检查已跳过。', '- No script docs (effects.log etc.); the unknown-key check was skipped.'))
    L.append('')
    L.append(tr('## 2. 子树\n', '## 2. Subtree\n'))
    dis = [n for n in nodes if n['dis']]
    by_t = Counter(n['tz'] for n in nodes if n['k'] in set(inc))
    L.append(tr(f"- 同主题 {len(inc)}；边界 {len(bnd)}；其中禁用 {len(dis)}（图中默认隐藏）。",
                f"- In theme {len(inc)}; boundary {len(bnd)}; disabled {len(dis)} (hidden by default)."))
    L.append(tr(f"- 边（同一对节点、同一触发方式合并后）：硬边 {len(hard)}（连到边界 {sum(1 for e in hard if e['s'] in bset or e['t'] in bset)}），软边 {len(soft)}；合并前 {sum(e['n'] for e in hard)} 处引用。",
                f"- Edges (merged per node pair and context): hard {len(hard)} (to boundary {sum(1 for e in hard if e['s'] in bset or e['t'] in bset)}), soft {len(soft)}; {sum(e['n'] for e in hard)} references before merging."))
    L.append(tr('- 同主题按类型：', '- In theme by type: ') + ', '.join(f'{k} {v}' for k, v in by_t.most_common()))
    systems = Counter(n['sys'] for n in nodes if n['k'] in bset)
    L.append(tr('- 边界所属系统：', '- Boundary systems: ') + ', '.join(f'{k or "-"} {v}' for k, v in systems.most_common()) + '\n')
    un = [u for u in g['unresolved'] if u['src'] in sub]
    L.append(tr('## 3. 未解析清单\n', '## 3. Unresolved\n'))
    L.append(tr(f"全局 {len(g['unresolved'])} 条（见 index/unresolved.md）；涉及本图的 {len(un)} 条：\n",
                f"{len(g['unresolved'])} in the whole index (index/unresolved.md); {len(un)} touch this map:\n"))
    L += [f"- `{u['src']}` → `{u['target']}` ({u['rtype']}) {u['file']}:{u['line']} — {u['reason']}" for u in un]
    L.append('')
    L.append(tr('## 4. 软边\n', '## 4. Soft edges\n'))
    L.append(tr(f'### 确认（{len(conf)} 对，画出 {len(soft)} 条虚线）\n', f'### Confirmed ({len(conf)} pairs, {len(soft)} dashed lines)\n'))
    for c in conf:
        L.append(f"- `{c['writer']}` ⇢ `{c['reader']}` ({c['object']}). W {'; '.join(c['writer_at'][:2])}; R {'; '.join(c['reader_at'][:2])}. {c.get('reason', '')}")
    rej = defaultdict(list)
    for c in cands.values():
        if c.get('decision') and c['decision']['verdict'] == 'no' and (c['writer'] in sub or c['reader'] in sub):
            rej[(c['object'], c['decision']['reason'])].append(c)
    L.append(tr(f"\n### 剔除（{sum(len(v) for v in rej.values())} 对）\n", f"\n### Rejected ({sum(len(v) for v in rej.values())} pairs)\n"))
    for (obj, why), cs in sorted(rej.items(), key=lambda x: -len(x[1])):
        L.append(f"- `{obj}`: {len(cs)} (e.g. `{cs[0]['writer']}` ⇢ `{cs[0]['reader']}`). {why}")
    L.append('')
    L.append(tr('## 5. 判定记录\n', '## 5. Judgments\n'))
    L.append(tr(f"判定文件：`{case.get('decisions_file')}`。共 {len(jud)} 条。\n", f"Decisions file: `{case.get('decisions_file')}`. {len(jud)} entries.\n"))
    for vv in ('in', 'boundary', 'out'):
        js = [j for j in jud if j['verdict'] == vv]
        L.append(f"### {i18n.T('v.' + vv)}: {len(js)}\n")
        L.append(tr('| 节点 | 名称 | 由谁发现 | 系统 | 理由 | 来源 |', '| Node | Name | Found via | System | Reason | Source |') + '\n|---|---|---|---|---|---|')
        for j in sorted(js, key=lambda x: x['node']):
            n = g['nodes'][j['node']]
            via = j.get('via') or {}
            frm = f"{j.get('from') or ''} {via.get('dir', '')} [{via.get('ctx', '')}]" if j.get('from') else '—'
            L.append(f"| `{j['node']}` | {str(n.get('name', ''))[:24]} | {frm} | {j.get('system', '')} | {j.get('reason', '')} | {j.get('source', '')} |")
        L.append('')
    rc = reverse_check(g, src, inc)
    L.append(tr('## 6. 反向检查\n', '## 6. Reverse check\n'))
    L.append(tr('每个同主题节点的 id，在各 MOD（没有 MOD 时为原版）的 common/、events/、gui/ 原文中逐行搜索；不能由某条边或定义解释的出现列在下面（可能是索引漏抓）。\n',
                'Each in-theme id is searched line by line in every mod\'s common/, events/ and gui/ (the game\'s when no mod is loaded); '
                'occurrences that no edge or definition explains are listed (possible index misses).\n'))
    L.append(tr(f"未解释：{len(rc)} 处。\n", f"Unexplained: {len(rc)}.\n"))
    L += [f"- `{r['id']}` {r['at']}: `{r['code']}`" for r in rc[:300]]
    L.append('')
    L.append(tr('## 7. 抽查（随机 10 条硬边）\n', '## 7. Spot check (10 random hard edges)\n'))
    sample = random.Random(20261108 + len(edges)).sample(hard, min(10, len(hard)))
    ok = 0
    from .sources import LineCache
    cache = LineCache(src)
    for e in sample:
        site = e['sites'][0]
        tid = g['nodes'][e['t']]['id']
        ls = cache.lines(site.get('root', 'game'), site.get('file', ''))
        full = ' '.join(ls[site['line'] - 1:min(site.get('end', site['line']), site['line'] + 40)]) if site.get('file') else site['code']
        hit = tid in full or site.get('via') is not None
        ok += hit
        L.append(f"- {'✔' if hit else '✘'} `{e['s']}` → `{e['t']}` [{e['ctx']}] {site['at']}: `{site['code']}`")
    L.append(tr(f"\n自动比对：{ok}/{len(sample)} 行中出现目标 id（参数调用的行出现的是参数名）。\n",
                f"\nAutomatic match: the target id appears on {ok}/{len(sample)} lines (parameter calls show the parameter name instead).\n"))
    fs = findings(g, src, inc, languages)
    L.append(tr('## 8. 疑似问题（只列出）\n', '## 8. Suspected problems (listed only)\n'))
    L += [f"- [{kind}] `{k}` ({str(g['nodes'][k].get('name', ''))[:20]}): {m}" for kind, k, m in fs]
    out_path.write_text('\n'.join(L), 'utf-8')
    return {'in': len(inc), 'boundary': len(bnd), 'hard': len(hard), 'soft': len(soft), 'reverse_unexplained': len(rc),
            'spot_ok': ok, 'spot_n': len(sample), 'findings': len(fs)}


def unresolved_md(g, out_dir):
    L = [tr('# 全局未解析清单\n', '# Unresolved references\n'),
         tr(f"共 {len(g['unresolved'])} 条。动态引用不猜测目标。\n", f"{len(g['unresolved'])} entries. Dynamic references are not guessed.\n")]
    L += [f"- `{u['src']}` → `{u['target']}` ({u['rtype']}) {u['file']}:{u['line']} — {u['reason']}" for u in g['unresolved']]
    L.append(tr(f"\n## 目标未定义（{len(g['dangling'])}）\n", f"\n## Undefined targets ({len(g['dangling'])})\n"))
    L += [f"- `{d['edge_src']}` → `{d['target']}` {d['file']}:{d['line']}" for d in g['dangling']]
    L.append(tr(f"\n## 未识别键（{len(g['unknown_keys'])}）\n", f"\n## Unknown keys ({len(g['unknown_keys'])})\n"))
    L += [f"- `{k}`: {', '.join(v)}" for k, v in g['unknown_keys'].items()]
    (Path(out_dir) / 'index' / 'unresolved.md').write_text('\n'.join(L), 'utf-8')
