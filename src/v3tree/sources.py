"""Layers (game + mods in load order), effective files, localisation, source lines.

Override rules (see docs/*/how-it-works.md for the evidence behind each):
- a file at the same relative path in a later layer replaces the earlier one;
- files of one folder are read in file-name order across all layers;
- localisation: later keys win; any layer's localization/<lang>/replace/ wins over normal files.
"""
from __future__ import annotations
import fnmatch, re
from dataclasses import dataclass
from pathlib import Path

from .config import game_dirs, mod_info


@dataclass
class Layer:
    id: str            # 'game', 'mod1', 'mod2', ...
    kind: str          # 'game' | 'mod'
    path: Path         # folder that holds common/, events/, localization/
    name: str

    def as_dict(self):
        return {'id': self.id, 'kind': self.kind, 'path': str(self.path), 'name': self.name}


def layers_from_config(cfg: dict) -> list[Layer]:
    out = []
    _, gdir = game_dirs((cfg.get('game') or {}).get('path'))
    if gdir:
        out.append(Layer('game', 'game', gdir, 'Victoria 3'))
    for i, m in enumerate(cfg.get('mods') or [], 1):
        p = Path(m['path'])
        if p.is_dir():
            out.append(Layer(f'mod{i}', 'mod', p, m.get('name') or mod_info(p)['name']))
    return out


def layers_from_dicts(ds) -> list[Layer]:
    return [Layer(d['id'], d['kind'], Path(d['path']), d['name']) for d in ds]


class Sources:
    def __init__(self, layers: list[Layer], ignore=()):
        self.layers = layers
        self.by_id = {l.id: l for l in layers}
        self.ignore = list(ignore)

    def _ignored(self, rel):
        return any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch('/' + rel, pat) for pat in self.ignore)

    def collect(self, rel_folder, glob='*.txt'):
        """Effective files of a folder as (layer_id, rel, path), and the overridden rel paths."""
        files, overridden = {}, []
        for layer in self.layers:
            folder = layer.path / rel_folder
            if not folder.exists():
                continue
            for p in sorted(folder.rglob(glob)):
                rel = p.relative_to(layer.path).as_posix()
                if self._ignored(rel):
                    continue
                key = rel.lower()
                if key in files:
                    overridden.append({'file': rel, 'by': layer.id, 'was': files[key][0]})
                files[key] = (layer.id, rel, p)
        return sorted(files.values(), key=lambda x: (Path(x[1]).name.lower(), x[1].lower())), overridden

    def path_of(self, layer_id, rel) -> Path | None:
        l = self.by_id.get(layer_id)
        return l.path / rel if l else None

    def mod_layers(self):
        return [l for l in self.layers if l.kind == 'mod']


LOC_RE = re.compile(r'^\s*([^\s:#"]+):\d*\s*"(.*)"\s*(?:#.*)?$')


def load_loc(src: Sources, languages):
    """Merged localisation for the first language, falling back to the next ones."""
    loc, where = {}, {}
    for lang in reversed(list(languages) or ['english']):   # earlier languages win
        files = {}
        for li, layer in enumerate(src.layers):
            base = layer.path / 'localization' / lang
            if not base.exists():
                continue
            for p in sorted(base.rglob('*.yml')):
                rel = p.relative_to(layer.path).as_posix()
                if src._ignored(rel):
                    continue
                replace = '/replace/' in rel.lower()
                files[rel.lower()] = (1 if replace else 0, li, rel, p, layer.id)
        for _, _, rel, p, lid in sorted(files.values(), key=lambda x: (x[0], x[1], x[2])):
            for n, line in enumerate(p.read_text('utf-8-sig', errors='replace').splitlines(), 1):
                m = LOC_RE.match(line)
                if m:
                    loc[m.group(1)] = m.group(2)
                    where[m.group(1)] = f'{rel}:{n}'
    return loc, where


def loc_resolve(loc, key, depth=0):
    v = loc.get(key)
    if v is None or depth > 2:
        return v
    return re.sub(r'\$([A-Za-z0-9_.]+)\$', lambda m: loc_resolve(loc, m.group(1), depth + 1) or m.group(0), v)


class LineCache:
    def __init__(self, src: Sources):
        self.src, self.cache = src, {}

    def lines(self, layer_id, rel):
        key = (layer_id, rel)
        if key not in self.cache:
            p = self.src.path_of(layer_id, rel)
            try:
                self.cache[key] = p.read_text('utf-8-sig', errors='replace').split('\n') if p else []
            except OSError:
                self.cache[key] = []
        return self.cache[key]
