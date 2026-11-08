"""v3tree command line.

  v3tree init                         interactive first-time setup, then doctor
  v3tree doctor                       check the configuration (exit 0 ok / 1 notes / 2 errors)
  v3tree index                        build the global index
  v3tree roots SPEC                   show how an id or TAG resolves to roots
  v3tree new NAME SPEC "THEME"        new case for judging (AI or by hand), with a decisions file
  v3tree expand NAME                  list what still needs a judgment
  v3tree render NAME                  map.html + report.md + subgraph.json
  v3tree search SPEC --steps N        automatic: step search with stop rules, sign off, render
  v3tree serve                        local web interface
  v3tree cases                        list cases / sessions

Every command takes --config PATH (default: <install>/config/local.json).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from . import config as C, judge as J, ops, i18n, __version__


def _p(*a):
    print(*a, flush=True)


def ask(prompt, default=''):
    try:
        v = input(f'{prompt} [{default}]: ' if default else f'{prompt}: ').strip()
    except EOFError:
        v = ''
    return v or default


def cmd_init(args):
    if any(getattr(args, a) is not None for a in ('game', 'mod', 'languages', 'ui', 'output')) or args.playset:
        return init_flags(args)
    cfg = C.load(args.config)
    zh = ask('Interface language / 界面语言 (en / zh)', cfg.get('ui_language') or 'en').lower().startswith('zh')
    cfg['ui_language'] = 'zh' if zh else 'en'
    i18n.set_lang(cfg['ui_language'])
    q = (lambda a, b: a) if zh else (lambda a, b: b)
    found = C.find_game()
    g = ask(q('游戏安装路径（留空表示不用原版）', 'Game install folder (empty = no vanilla)'),
            (cfg['game'].get('path') or (str(found) if found else '')))
    cfg['game'] = {'path': g}
    launcher = C.launcher_mods(C.user_data_dir(cfg))
    if launcher and ask(q(f'从启动器导入当前游戏集的 {len(launcher)} 个 MOD？(y/n)', f'Import the {len(launcher)} mods of the launcher playset? (y/n)'), 'n').lower().startswith('y'):
        C.import_launcher_order(cfg)
        for i, m in enumerate(cfg['mods'], 1):
            _p(f'  {i}. {m["name"]}  {m["path"]}')
        _p(q('上面是加载顺序：先加载的在前，后加载的覆盖先加载的。如果不对，可在 config/local.json 里调整，或在网页的“设置”里拖动。',
             'This is the load order: earlier loads first, later overrides earlier. Fix it in config/local.json or in the web settings if wrong.'))
    else:
        mods = []
        _p(q('逐个输入 MOD 路径，按加载顺序（先加载的先输入）；直接回车结束。', 'Enter mod folders one per line in load order (first loaded first); empty line to finish.'))
        while True:
            m = ask('  MOD')
            if not m:
                break
            mods.append({'path': m, 'name': C.mod_info(m)['name']})
        if mods:
            cfg['mods'], cfg['load_order_source'] = mods, 'manual'
    langs = ask(q('本地化语言，逗号分隔，靠前的优先', 'Localisation languages, comma separated, first wins'),
                ','.join(cfg.get('languages') or (['simp_chinese', 'english'] if zh else ['english'])))
    cfg['languages'] = [x.strip() for x in langs.split(',') if x.strip()]
    cfg['output_dir'] = ask(q('输出目录', 'Output folder'), cfg.get('output_dir'))
    return _finish_init(cfg, args)


def init_flags(args):
    """Non-interactive init (for scripts and AI agents)."""
    cfg = C.load(args.config)
    if args.ui:
        cfg['ui_language'] = 'zh' if args.ui.lower().startswith('zh') else 'en'
    i18n.set_lang(cfg.get('ui_language', 'en'))
    if args.game is not None:
        cfg['game'] = {'path': args.game}
    if args.playset:
        if not C.import_launcher_order(cfg):
            _p('[ERR]  launcher playset (content_load.json) not found')
            return 2
    elif args.mod is not None:
        cfg['mods'] = [{'path': m, 'name': C.mod_info(m)['name']} for m in args.mod]
        cfg['load_order_source'] = 'manual'
    if args.languages:
        cfg['languages'] = [x.strip() for x in args.languages.split(',') if x.strip()]
    if args.output:
        cfg['output_dir'] = args.output
    return _finish_init(cfg, args)


def _finish_init(cfg, args):
    zh = i18n.LANG == 'zh'
    if not (cfg.get('game') or {}).get('path') and not cfg.get('mods'):
        _p(C.msg('need_path'))
        return 2
    for i, m in enumerate(cfg.get('mods') or [], 1):
        _p(f'  {i}. {m.get("name")}  {m["path"]}')
    code = _doctor(cfg)
    if code >= 2:
        _p('配置有错误，未保存。请改正上面标 [ERR] 的项后重试。' if zh else
           'Not saved: fix the items marked [ERR] above and run init again.')
        return code
    path = C.save(cfg, args.config)
    _p(f'配置已保存：{path}' if zh else f'Configuration saved: {path}')
    _p('下一步：python run.py index' if zh else 'Next: python run.py index')
    return code


def _doctor(cfg):
    code, lines = C.doctor(cfg)
    mark = {'ok': '[ok]  ', 'note': '[note]', 'error': '[ERR] '}
    for lvl, text in lines:
        _p(f'{mark[lvl]} {text}')
    return code


def cmd_doctor(args):
    cfg = C.load(args.config)
    code = _doctor(cfg)
    C.save(cfg, args.config)
    return code


def need_cfg(args):
    cfg = C.load(args.config)
    if not (cfg.get('game') or {}).get('path') and not cfg.get('mods'):
        raise SystemExit(C.msg('need_path') + ' (v3tree init)')
    return cfg


def cmd_index(args):
    cfg = need_cfg(args)
    st = ops.build_index(cfg, progress=lambda i, n, f: None)
    _p(json.dumps({k: v for k, v in st.items() if k != 'nodes_by_type'}, ensure_ascii=False))
    return 0


def cmd_roots(args):
    cfg = need_cfg(args)
    g = J.load_index(ops.out_dir(cfg))
    _p(json.dumps(J.resolve_roots(g, args.spec), ensure_ascii=False, indent=1))
    return 0


def cmd_new(args):
    cfg = need_cfg(args)
    g = J.load_index(ops.out_dir(cfg))
    roots = J.resolve_roots(g, args.spec)
    if not roots:
        raise SystemExit(f'root not found: {args.spec}')
    cp = J.new_case(ops.out_dir(cfg), args.name, roots, args.theme, lang=i18n.LANG, vanilla_rule=J.has_mod_layers(g))
    _p(f'roots: {roots}\ncase: {cp}\ndecisions: {cp.parent / "decisions.txt"}')
    return 0


def cmd_expand(args):
    cfg = need_cfg(args)
    J.run_expand(ops.out_dir(cfg), ops.case_path(cfg, args.name))
    return 0


def cmd_render(args):
    cfg = need_cfg(args)
    res = ops.render_case(cfg, args.name)
    _p(json.dumps(res, ensure_ascii=False, indent=1))
    if res.get('pending'):
        _p(f"WARNING: {res['pending']} neighbours are still undecided; they are listed in the side panel as "
           f"'not judged'. Run expand and judge them for a complete map.")
    return 0


def cmd_search(args):
    cfg = need_cfg(args)
    stop = {}
    if args.hub is not None:
        stop['hub'] = args.hub
    if args.no_vanilla_stop:
        stop['vanilla'] = False
    _p(json.dumps(ops.auto_search(cfg, args.spec, args.steps, args.name, args.theme or '', stop or None,
                                  accept=not args.no_accept), ensure_ascii=False, indent=1))
    return 0


def cmd_cases(args):
    cfg = need_cfg(args)
    for c in ops.list_cases(cfg):
        _p(f"{c['name']:30s} {c['mode']:3s} {'accepted' if c['accepted'] else '':9s} {', '.join(c['roots'] or [])}")
    return 0


def cmd_serve(args):
    from . import server
    return server.serve(args.config, args.port, not args.no_browser)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):        # names and labels may be Chinese; keep pipes readable
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog='v3tree', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--config', default=None, help='configuration file')
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='cmd')
    a = sub.add_parser('init', help='first-time setup; interactive, or non-interactive when any flag is given',
                       description='Interactive without flags (asks: interface language, game folder, import the launcher '
                                   'playset y/n, mod folders, localisation languages, output folder). With any flag it asks '
                                   'nothing. A configuration that fails the check is not saved.')
    a.add_argument('--game', help='game install folder ("" = no game)')
    a.add_argument('--mod', action='append', help='a mod folder; repeat in load order (earlier first)')
    a.add_argument('--playset', action='store_true', help='take the mods and their order from the launcher playset')
    a.add_argument('--languages', help='localisation languages, comma separated, first wins, e.g. simp_chinese,english')
    a.add_argument('--ui', help='interface language: en or zh')
    a.add_argument('--output', help='output folder (default: <repository>/output)')
    sub.add_parser('doctor'); sub.add_parser('index'); sub.add_parser('cases')
    a = sub.add_parser('roots'); a.add_argument('spec')
    a = sub.add_parser('new'); a.add_argument('name'); a.add_argument('spec'); a.add_argument('theme', nargs='?', default='')
    a = sub.add_parser('expand'); a.add_argument('name')
    a = sub.add_parser('render'); a.add_argument('name')
    a = sub.add_parser('search'); a.add_argument('spec'); a.add_argument('--steps', type=int, default=3)
    a.add_argument('--name'); a.add_argument('--theme'); a.add_argument('--hub', type=int)
    a.add_argument('--no-vanilla-stop', action='store_true'); a.add_argument('--no-accept', action='store_true')
    a = sub.add_parser('serve'); a.add_argument('--port', type=int, default=0); a.add_argument('--no-browser', action='store_true')
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--config' in argv[1:]:                     # accept --config after the subcommand too
        i = argv.index('--config')
        argv = argv[i:i + 2] + argv[:i] + argv[i + 2:]
    args = p.parse_args(argv)
    if args.config:
        args.config = Path(args.config)
    i18n.set_lang(C.load(args.config).get('ui_language', 'en'))
    fn = {'init': cmd_init, 'doctor': cmd_doctor, 'index': cmd_index, 'roots': cmd_roots, 'new': cmd_new,
          'expand': cmd_expand, 'render': cmd_render, 'search': cmd_search, 'serve': cmd_serve, 'cases': cmd_cases}.get(args.cmd)
    if not fn:
        p.print_help()
        return 0
    return fn(args) or 0


if __name__ == '__main__':
    sys.exit(main())
