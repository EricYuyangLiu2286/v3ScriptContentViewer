"""Configuration: read/write, path detection, and the startup check (doctor)."""
from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path

from .i18n import T, set_lang

SCHEMA = 1
APP_ID = '529340'   # Victoria 3 on Steam


# ---------------------------------------------------------------- locations
def home() -> Path:
    """Install location: the repository root when run from source, else ~/.v3tree."""
    env = os.environ.get('V3TREE_HOME')
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / 'pyproject.toml').exists() and (p / 'src' / 'v3tree').exists():
            return p
    return Path.home() / '.v3tree'


def default_config_path() -> Path:
    return home() / 'config' / 'local.json'


def empty() -> dict:
    return {'schema': SCHEMA, 'game': {'path': ''}, 'mods': [], 'load_order_source': 'manual',
            'languages': ['english'], 'ui_language': 'en', 'output_dir': str(home() / 'output'),
            'script_docs_dir': None, 'ignore': [], 'extra_folders': {}, 'detected': {}}


def load(path: Path | None = None) -> dict:
    path = Path(path or default_config_path())
    if not path.exists():
        return empty()
    cfg = {**empty(), **json.loads(path.read_text('utf-8-sig'))}
    set_lang(cfg.get('ui_language', 'en'))
    return cfg


def save(cfg: dict, path: Path | None = None) -> Path:
    path = Path(path or default_config_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')
    return path


# ---------------------------------------------------------------- game
def game_dirs(p: str | Path | None):
    """Accept the install root or its game/ folder. Returns (install_root, game_dir) or (None, None)."""
    if not p:
        return None, None
    p = Path(p)
    if (p / 'game' / 'common').is_dir():
        return p, p / 'game'
    if p.name.lower() == 'game' and (p / 'common').is_dir():
        return p.parent, p
    return None, None


def steam_libraries() -> list[Path]:
    roots = []
    if sys.platform == 'win32':
        try:
            import winreg
            for hive, sub in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                              (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam')):
                try:
                    with winreg.OpenKey(hive, sub) as k:
                        for name in ('SteamPath', 'InstallPath'):
                            try:
                                roots.append(Path(winreg.QueryValueEx(k, name)[0]))
                            except OSError:
                                pass
                except OSError:
                    pass
        except ImportError:
            pass
        for d in 'CDEFG':
            roots.append(Path(f'{d}:/Program Files (x86)/Steam'))
            roots.append(Path(f'{d}:/Steam'))
            roots.append(Path(f'{d}:/SteamLibrary'))
    else:
        roots += [Path.home() / '.steam/steam', Path.home() / '.local/share/Steam',
                  Path.home() / 'Library/Application Support/Steam']
    libs = []
    for r in roots:
        vdf = r / 'steamapps' / 'libraryfolders.vdf'
        if vdf.exists():
            libs.append(r)
            for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text('utf-8', errors='replace')):
                libs.append(Path(m.group(1).replace('\\\\', '/')))
        elif (r / 'steamapps').is_dir():
            libs.append(r)
    out = []
    for l in libs:
        if l not in out:
            out.append(l)
    return out


def find_game() -> Path | None:
    for lib in steam_libraries():
        cand = lib / 'steamapps' / 'common' / 'Victoria 3'
        if game_dirs(cand)[0]:
            return cand
    return None


def game_version(install: Path | None) -> dict:
    out = {}
    if not install:
        return out
    ls = install / 'launcher' / 'launcher-settings.json'
    if ls.exists():
        try:
            d = json.loads(ls.read_text('utf-8-sig'))
            out['game_version'] = d.get('rawVersion') or d.get('version')
            out['_gameDataPath'] = d.get('gameDataPath')
        except ValueError:
            pass
    acf = install.parent.parent / f'appmanifest_{APP_ID}.acf'
    if acf.exists():
        m = re.search(r'"buildid"\s+"(\d+)"', acf.read_text('utf-8', errors='replace'))
        if m:
            out['steam_build'] = m.group(1)
    return out


# ---------------------------------------------------------------- user data folder (documents)
def documents_dirs() -> list[Path]:
    c = []
    if sys.platform == 'win32':
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:   # CSIDL_PERSONAL
                c.append(Path(buf.value))
        except Exception:  # noqa: BLE001
            pass
        up = os.environ.get('USERPROFILE')
        if up:
            c += [Path(up) / 'Documents', Path(up) / 'OneDrive' / 'Documents']
    else:
        c += [Path.home() / '.local/share', Path.home() / 'Documents']
    return c


def user_data_dir(cfg: dict | None = None) -> Path | None:
    for d in documents_dirs():
        p = d / 'Paradox Interactive' / 'Victoria 3'
        if p.is_dir():
            return p
    # a mod inside <userdata>/mod/<name> tells us where the user folder is
    for m in (cfg or {}).get('mods', []):
        p = Path(m['path'])
        if p.parent.name.lower() == 'mod' and (p.parent.parent / 'mod').is_dir():
            return p.parent.parent
    return None


def launcher_mods(userdir: Path | None) -> list[str] | None:
    """Enabled mods of the active playset, in the launcher's order (content_load.json)."""
    if not userdir:
        return None
    f = userdir / 'content_load.json'
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text('utf-8-sig'))
    except ValueError:
        return None
    return [m.get('path') for m in d.get('enabledMods', []) if m.get('path')]


def mod_info(path: str | Path) -> dict:
    p = Path(path)
    info = {'path': str(p), 'name': p.name}
    meta = p / '.metadata' / 'metadata.json'
    if meta.exists():
        try:
            d = json.loads(meta.read_text('utf-8-sig'))
            info['name'] = d.get('name') or p.name
            if d.get('supported_game_version'):
                info['supported_game_version'] = d['supported_game_version']
            if d.get('id'):
                info['id'] = d['id']
        except ValueError:
            info['metadata_error'] = True
    info['looks_like_mod'] = meta.exists() or any((p / x).is_dir() for x in ('common', 'events', 'localization'))
    return info


def script_docs_dir(cfg: dict) -> Path | None:
    if cfg.get('script_docs_dir'):
        p = Path(cfg['script_docs_dir'])
        return p if (p / 'effects.log').exists() else None
    ud = user_data_dir(cfg)
    if ud and (ud / 'docs' / 'effects.log').exists():
        return ud / 'docs'
    return None


# ---------------------------------------------------------------- doctor
MSG = {
    'need_path': ('请至少填写游戏安装路径或一个 MOD 路径。',
                  'Give at least the game install folder or one mod folder.'),
    'game_bad': ('在 {p} 下没有找到 game/common。请填游戏安装目录，例如 …/steamapps/common/Victoria 3。',
                 'No game/common under {p}. Give the install folder, e.g. …/steamapps/common/Victoria 3.'),
    'game_ok': ('游戏：{p}（版本 {v}）', 'Game: {p} (version {v})'),
    'game_nover': ('无法识别游戏版本，索引仍可建立。', 'Could not read the game version; indexing still works.'),
    'no_game': ('没有游戏路径：引用原版的内容会显示为“未定义”。', 'No game folder: references to vanilla content will show as undefined.'),
    'mod_missing': ('MOD 路径不存在：{p}', 'Mod folder does not exist: {p}'),
    'mod_bad': ('{p} 不像 MOD 目录（没有 .metadata、common、events 或 localization）。',
                '{p} does not look like a mod (no .metadata, common, events or localization).'),
    'mod_ok': ('MOD {i}：{n}', 'Mod {i}: {n}'),
    'mod_ver': ('MOD “{n}” 声明支持 {s}，游戏是 {v}。', 'Mod "{n}" declares {s}; the game is {v}.'),
    'order_launcher': ('加载顺序取自启动器（content_load.json）。请确认：先加载的在前，后加载的覆盖先加载的。',
                       'Load order taken from the launcher (content_load.json). Please confirm: earlier loads first, later overrides earlier.'),
    'order_manual': ('加载顺序为手工排序。', 'Load order is set by hand.'),
    'order_unknown': ('没有读到启动器的游戏集，加载顺序按你填写的顺序。', 'No launcher playset found; using the order you gave.'),
    'docs_ok': ('接口清单：{p}', 'Script docs: {p}'),
    'docs_missing': ('未找到 effects.log 等接口清单，“未识别键”检查将跳过。在游戏控制台输入 script_docs 可以生成。',
                     'No effects.log etc. found; the "unknown key" check will be skipped. Run script_docs in the game console to create them.'),
    'lang_missing': ('所有目录下都没有 localization/{l}，改用 english。', 'No localization/{l} in any folder; falling back to english.'),
    'out_bad': ('输出目录不可写：{p}', 'Output folder is not writable: {p}'),
    'out_ok': ('输出目录：{p}', 'Output folder: {p}'),
    'parse_count': ('可读取的脚本文件：{n} 个', 'Script files found: {n}'),
}


def msg(key, **kw):
    from . import i18n
    zh, en = MSG[key]
    return (zh if i18n.LANG == 'zh' else en).format(**kw)


def doctor(cfg: dict, write_detected=True) -> tuple[int, list[tuple[str, str]]]:
    """Return (exit code, [(level, text)]). 0 = all good, 1 = notes only, 2 = errors."""
    out = []
    err = note = False
    gpath = (cfg.get('game') or {}).get('path')
    mods = cfg.get('mods') or []
    if not gpath and not mods:
        return 2, [('error', msg('need_path'))]
    install, gdir = game_dirs(gpath)
    det = {}
    if gpath and not install:
        out.append(('error', msg('game_bad', p=gpath))); err = True
    elif install:
        det = game_version(install)
        if det.get('game_version'):
            out.append(('ok', msg('game_ok', p=install, v=det['game_version'])))
        else:
            out.append(('note', msg('game_nover'))); note = True
    else:
        out.append(('note', msg('no_game'))); note = True
    for i, m in enumerate(mods, 1):
        p = Path(m['path'])
        if not p.is_dir():
            out.append(('error', msg('mod_missing', p=p))); err = True
            continue
        info = mod_info(p)
        if not info['looks_like_mod']:
            out.append(('error', msg('mod_bad', p=p))); err = True
            continue
        out.append(('ok', msg('mod_ok', i=i, n=info['name'])))
        sv, gv = info.get('supported_game_version'), det.get('game_version')
        if sv and gv and not gv.startswith(sv.rstrip('.*')) and not sv.startswith(gv):
            out.append(('note', msg('mod_ver', n=info['name'], s=sv, v=gv))); note = True
    if len(mods) > 1:
        src = cfg.get('load_order_source')
        out.append(('note', msg('order_launcher' if src == 'launcher' else 'order_manual'))); note = True
    sd = script_docs_dir(cfg)
    if sd:
        out.append(('ok', msg('docs_ok', p=sd)))
    else:
        out.append(('note', msg('docs_missing'))); note = True
    roots = ([gdir] if gdir else []) + [Path(m['path']) for m in mods if Path(m['path']).is_dir()]
    for lang in cfg.get('languages') or ['english']:
        if not any((r / 'localization' / lang).is_dir() for r in roots):
            out.append(('note', msg('lang_missing', l=lang))); note = True
    od = Path(cfg.get('output_dir') or home() / 'output')
    try:
        od.mkdir(parents=True, exist_ok=True)
        probe = od / '.write_test'
        probe.write_text('x', 'utf-8'); probe.unlink()
        out.append(('ok', msg('out_ok', p=od)))
    except OSError:
        out.append(('error', msg('out_bad', p=od))); err = True
    n = 0
    for r in roots:
        for sub in ('common', 'events'):
            if (r / sub).is_dir():
                n += sum(1 for _ in (r / sub).rglob('*.txt'))
    out.append(('ok', msg('parse_count', n=n)))
    if write_detected:
        cfg['detected'] = {k: v for k, v in det.items() if not k.startswith('_')} | {'checked': time.strftime('%Y-%m-%dT%H:%M')}
    return (2 if err else 1 if note else 0), out


def import_launcher_order(cfg: dict) -> list[str] | None:
    """Replace cfg['mods'] with the launcher playset (keeps names). Returns the paths or None."""
    paths = launcher_mods(user_data_dir(cfg))
    if not paths:
        return None
    cfg['mods'] = [{'path': p, 'name': mod_info(p)['name']} for p in paths]
    cfg['load_order_source'] = 'launcher'
    return paths
