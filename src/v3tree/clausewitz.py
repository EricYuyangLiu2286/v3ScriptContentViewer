"""Clausewitz (Paradox script) reader used by v3tree.

Source: the NESND development toolkit (scripts/pdx.py in the nesnd-victoria3 skill),
written for the Neo-Era Southern and Northern Dynasties mod and released with v3tree
under the MIT license by EricYuyangLiu2286. The parsing code below is unchanged.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re

LEX = re.compile(r'\s+|\#[^\r\n]*|"(?:\\.|[^"\\])*"|\?=|!=|>=|<=|[{}=<>]|[^\s{}=<>!?#"]+', re.S)
OPS = {'=', '?=', '!=', '>', '<', '>=', '<='}

@dataclass
class Node:
    key: str | None
    value: str | None = None
    children: list['Node'] | None = None
    op: str = '='
    start: int = 0
    end: int = 0
    vstart: int = 0
    vend: int = 0
    prefix: str = ''
    def all(self, key):
        return [n for n in self.children or [] if n.key == key]
    def get(self, key, default=None):
        ns = self.all(key)
        return ns[0] if ns else default
    def scalar(self, key, default=None):
        n = self.get(key)
        return unquote(n.value) if n is not None and n.value is not None else default
    def values(self):
        return [unquote(n.value) for n in self.children or [] if n.key is None and n.value is not None]
    def walk(self):
        yield self
        for n in self.children or []:
            yield from n.walk()

def unquote(s):
    if s is not None and len(s) >= 2 and s[0] == s[-1] == '"':
        return s[1:-1]
    return s

def parse(text: str) -> Node:
    tokens = []
    pos = 0
    for m in LEX.finditer(text.lstrip('\ufeff')):
        # UTF-8-sig file reader removes BOM; string callers should too.
        if m.start() != pos:
            raise ValueError(f'Unrecognized syntax at {pos}: {text[pos:pos+30]!r}')
        pos = m.end()
        s = m.group()
        if not s.isspace() and not s.startswith('#'):
            tokens.append((s, m.start(), m.end()))
    text = text.lstrip('\ufeff')
    if pos != len(text):
        raise ValueError(f'Unterminated token at {pos}')
    i = 0
    def body(nested=False):
        nonlocal i
        nodes = []
        while i < len(tokens):
            token, start, end = tokens[i]
            if token == '}':
                if not nested:
                    raise ValueError(f'Unexpected }} at {start}')
                i += 1
                return nodes, end
            if token == '{':
                i += 1
                children, end = body(True)
                nodes.append(Node(None, None, children, start=start, end=end, vstart=start, vend=end))
                continue
            if token in OPS:
                raise ValueError(f'Unexpected {token} at {start}')
            i += 1
            key, op = None, '='
            value, vs, ve = token, start, end
            if i < len(tokens) and tokens[i][0] in OPS:
                key, op = unquote(token), tokens[i][0]
                i += 1
                if i == len(tokens):
                    raise ValueError(f'Missing value for {key}')
                value, vs, ve = tokens[i]
                i += 1
            prefix = ''
            if key is not None and value != '{' and i < len(tokens) and tokens[i][0] == '{':
                prefix = value
                value = '{'
                i += 1
            if value == '{':
                children, end = body(True)
                nodes.append(Node(key, None, children, op, start, end, vs, end, prefix))
            elif value in OPS or value == '}':
                raise ValueError(f'Missing value for {key} at {vs}')
            else:
                nodes.append(Node(key, value, None, op, start, ve, vs, ve))
        if nested:
            raise ValueError('Unclosed block')
        return nodes, len(text)
    children, end = body()
    return Node(None, None, children, start=0, end=end)

def read(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    return text, parse(text)

def emit(node: Node, indent=0):
    pad = '\t' * indent
    left = f'{node.key} {node.op} ' if node.key is not None else ''
    if node.children is None:
        return pad + left + str(node.value)
    prefix = (node.prefix + ' ') if node.prefix else ''
    if node.children and all(n.key is None and n.children is None for n in node.children):
        return pad + left + prefix + '{ ' + ' '.join(n.value for n in node.children) + ' }'
    return pad + left + prefix + '{\n' + '\n'.join(emit(n, indent+1) for n in node.children) + '\n' + pad + '}'

def replace_spans(text, edits):
    """edits=(start,end,new_text); refuse overlapping mutations."""
    ordered = sorted(edits)
    for a,b in zip(ordered, ordered[1:]):
        if a[1] > b[0]:
            raise ValueError('Overlapping edits')
    for start,end,new in reversed(ordered):
        text = text[:start] + new + text[end:]
    return text

def effective_files(roots, relative, glob='*.txt'):
    files = {}
    for root in roots:
        folder = Path(root) / relative
        if folder.exists():
            for path in sorted(folder.rglob(glob)):
                files[str(path.relative_to(root)).replace('\\','/').lower()] = path
    return list(files.values())

def basekey(key):
    if key and ':' in key and key.split(':',1)[0] in {'REPLACE','TRY_REPLACE','REPLACE_OR_CREATE','INJECT','TRY_INJECT'}:
        return key.split(':',1)[1]
    return key
