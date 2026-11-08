"""Local web interface. Listens on 127.0.0.1 only; every request needs the random token.

Reads the game and mod folders, writes only the configuration file and the output folder.
"""
from __future__ import annotations
import json, os, secrets, shutil, socket, subprocess, sys, threading, traceback, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

from . import config as C, judge as J, search as S, ops, i18n, __version__

WEB = Path(__file__).resolve().parent / 'web'


class App:
    def __init__(self, cfg_path):
        self.cfg_path = Path(cfg_path) if cfg_path else C.default_config_path()
        self.cfg = C.load(self.cfg_path)
        self.token = secrets.token_urlsafe(18)
        self.g = None
        self.lock = threading.Lock()
        self.progress = {'running': False, 'done': 0, 'total': 0, 'folder': '', 'error': None}

    def index(self):
        if self.g is None:
            st = ops.index_status(self.cfg)
            if st.get('exists'):
                self.g = J.load_index(ops.out_dir(self.cfg))
        return self.g

    def build(self):
        def run():
            try:
                def prog(i, n, f):
                    self.progress.update(done=i, total=n, folder=f)
                ops.build_index(self.cfg, progress=prog, verbose=False)
                self.g = None
                self.index()
                self.progress.update(done=self.progress['total'], folder='')
            except BaseException as e:  # noqa: BLE001
                self.progress['error'] = str(e)
            finally:
                self.progress['running'] = False
        if self.progress['running']:
            return
        self.progress = {'running': True, 'done': 0, 'total': 1, 'folder': '', 'error': None}
        threading.Thread(target=run, daemon=True).start()


def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        # ---------------- helpers
        def _send(self, code, body, ctype='application/json; charset=utf-8'):
            data = body if isinstance(body, bytes) else body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False, default=str))

        def _host_ok(self):
            host = (self.headers.get('Host') or '').split(':')[0]
            return host in ('127.0.0.1', 'localhost')

        def _token_ok(self, q):
            return secrets.compare_digest(self.headers.get('X-Token') or (q.get('t') or [''])[0], app.token)

        def _body(self):
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n).decode('utf-8')) if n else {}

        # ---------------- routes
        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if not self._host_ok() or not self._token_ok(q):
                return self._send(403, 'forbidden', 'text/plain')
            try:
                if u.path == '/':
                    return self._send(200, self.page(), 'text/html; charset=utf-8')
                if u.path.startswith('/view/'):
                    name = unquote(u.path[len('/view/'):]).split('/')[0]
                    p = J.case_dir(ops.out_dir(app.cfg), name) / 'map.html'
                    if p.exists() and p.resolve().is_relative_to(Path(ops.out_dir(app.cfg)).resolve()):
                        return self._send(200, p.read_bytes(), 'text/html; charset=utf-8')
                    return self._send(404, 'not found', 'text/plain')
                if u.path == '/api/state':
                    return self._json(self.state())
                if u.path == '/api/index_progress':
                    return self._json({**app.progress, 'status': ops.index_status(app.cfg)})
                if u.path == '/api/suggest':
                    g = app.index()
                    return self._json(J.suggest(g, (q.get('q') or [''])[0]) if g else [])
                if u.path == '/api/session':
                    return self._json(self.payload((q.get('name') or [''])[0]))
                return self._send(404, 'not found', 'text/plain')
            except Exception as e:  # noqa: BLE001
                return self._json({'error': str(e), 'trace': traceback.format_exc()[-1500:]}, 500)

        def do_POST(self):
            u = urlparse(self.path)
            if not self._host_ok() or not self._token_ok(parse_qs(u.query)):
                return self._send(403, 'forbidden', 'text/plain')
            try:
                b = self._body()
                with app.lock:
                    return self.post(u.path, b)
            except Exception as e:  # noqa: BLE001
                return self._json({'error': str(e), 'trace': traceback.format_exc()[-1500:]}, 500)

        def post(self, path, b):
            cfg = app.cfg
            if path == '/api/config':
                new = {**cfg, **b.get('config', {})}
                if not (new.get('game') or {}).get('path') and not new.get('mods'):
                    return self._json({'error': C.msg('need_path')}, 400)
                code, lines = C.doctor(new)
                if code < 2:
                    i18n.set_lang(new.get('ui_language', 'en'))
                    if b.get('move_output'):
                        lines = lines + [list(x) for x in ops.move_output(ops.out_dir(cfg), ops.out_dir(new))]
                    app.cfg = new
                    C.save(new, app.cfg_path)
                    app.g = None
                return self._json({'code': code, 'lines': lines, 'saved': code < 2, 'state': self.state()})
            if path == '/api/doctor':
                code, lines = C.doctor({**cfg, **b.get('config', {})}, write_detected=False)
                return self._json({'code': code, 'lines': lines})
            if path == '/api/find_game':
                p = C.find_game()
                return self._json({'path': str(p) if p else ''})
            if path == '/api/import_launcher':
                tmp = {**cfg, 'mods': b.get('mods', cfg.get('mods', []))}
                paths = C.import_launcher_order(tmp)
                return self._json({'mods': tmp['mods'] if paths else None})
            if path == '/api/mod_info':
                return self._json(C.mod_info(b['path']))
            if path == '/api/index':
                app.build()
                return self._json({'started': True})
            g = app.index()
            if g is None:
                return self._json({'error': i18n.T('ui.need_index')}, 400)
            name = b.get('name', '')
            if path == '/api/session_new':
                roots = J.resolve_roots(g, b.get('root', '').strip())
                if not roots:
                    return self._json({'error': i18n.T('ui.not_found')}, 400)
                name = ops.safe_name(b.get('name') or b['root'])
                cp = J.new_case(ops.out_dir(cfg), name, roots, b.get('theme', ''), lang=i18n.LANG, mode='ui',
                                vanilla_rule=J.has_mod_layers(g))
                case = J.load_case(cp)
                S.search(case, g, b.get('steps', 3), b.get('stop'))
                return self._json(self.payload(name))
            case = J.load_case(ops.case_path(cfg, name))
            if path == '/api/search':
                S.search(case, g, b.get('steps', 3), b.get('stop'))
            elif path == '/api/judge':
                for k in b.get('keys', []):
                    case = J.load_case(ops.case_path(cfg, name))
                    S.judge_node(case, g, k, b['verdict'], i18n.LANG, b.get('system', ''))
            elif path == '/api/undo':
                S.undo(case)
            elif path == '/api/signoff':
                S.finalize(case, g, i18n.LANG)
                res = ops.render_case(cfg, name, g)
                return self._json({'done': True, **res})
            elif path == '/api/render':
                return self._json({'done': True, **ops.render_case(cfg, name, g)})
            elif path == '/api/delete':
                d = J.case_dir(ops.out_dir(cfg), name)
                if d.exists() and d.resolve().is_relative_to(Path(ops.out_dir(cfg)).resolve()):
                    ops.remove_tree(d)
                return self._json({'deleted': True, 'cases': ops.list_cases(cfg)})
            elif path == '/api/open_folder':
                d = J.case_dir(ops.out_dir(cfg), name)
                if sys.platform == 'win32':
                    os.startfile(str(d))  # noqa: S606
                else:
                    subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(d)])
                return self._json({'opened': str(d)})
            else:
                return self._send(404, 'not found', 'text/plain')
            return self._json(self.payload(name))

        # ---------------- content
        def state(self):
            cfg = app.cfg
            return {'config': cfg, 'index': ops.index_status(cfg), 'cases': ops.list_cases(cfg),
                    'config_path': str(app.cfg_path), 'version': __version__,
                    'default_output': str(C.home() / 'output'), 'output_now': str(ops.out_dir(cfg)),
                    'launcher_found': bool(C.launcher_mods(C.user_data_dir(cfg)))}

        def payload(self, name):
            g = app.index()
            return ops.session_payload(app.cfg, name, g)

        def page(self):
            html = (WEB / 'app.html').read_text('utf-8')
            return (html.replace('/*__CSS__*/', (WEB / 'viewer.css').read_text('utf-8'))
                    .replace('/*__VIEWER__*/', (WEB / 'viewer.js').read_text('utf-8'))
                    .replace('/*__L__*/null', json.dumps(i18n.table(), ensure_ascii=False).replace('</', '<\\/'))
                    .replace('__TOKEN__', app.token).replace('__LANG__', 'zh-CN' if i18n.LANG == 'zh' else 'en'))
    return H


def free_port(preferred=8765):
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(('127.0.0.1', port))
                return s.getsockname()[1]
            except OSError:
                continue
    return 0


def serve(cfg_path=None, port=0, open_browser=True):
    app = App(cfg_path)
    i18n.set_lang(app.cfg.get('ui_language', 'en'))
    port = port or free_port()
    httpd = ThreadingHTTPServer(('127.0.0.1', port), make_handler(app))
    url = f'http://127.0.0.1:{port}/?t={app.token}'
    print(f'v3tree {__version__}: {url}\n(Ctrl+C to stop)', flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
