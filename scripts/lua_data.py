"""Minimal parser for the Lua data-table literals used by the Warframe wiki's Module:*/data pages.

Handles `return { ... }` with nested tables, ["key"] = / key = / [1] = entries, strings, numbers,
booleans, nil and comments. Tables with only positional entries become lists, otherwise dicts.
"""

import re

_TOKEN = re.compile(r"""
    (?P<ws>\s+|--\[\[.*?\]\]|--[^\n]*)
  | (?P<lstr>\[\[.*?\]\])
  | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<num>-?(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+))
  | (?P<name>[A-Za-z_][A-Za-z0-9_.]*)
  | (?P<op>[{}\[\]=,;])
  | (?P<other>.)
""", re.S | re.X)

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "\n": "\n"}


def _unescape(body: str) -> str:
    def repl(m):
        c = m.group(1)
        if c.isdigit():
            return chr(int(c))
        return _ESCAPES.get(c, c)
    return re.sub(r"\\(\d{1,3}|.)", repl, body, flags=re.S)


def _tokens(text: str):
    out = []
    for m in _TOKEN.finditer(text):
        kind = m.lastgroup
        if kind == "ws":
            continue
        value = m.group(kind)
        if kind == "str":
            out.append(("str", _unescape(value[1:-1])))
        elif kind == "lstr":
            out.append(("str", value[2:-2]))
        elif kind == "num":
            if value.lower().startswith(("0x", "-0x")):
                out.append(("num", int(value, 16)))
            else:
                number = float(value)
                out.append(("num", int(number) if number.is_integer() and "." not in value and "e" not in value.lower() else number))
        else:
            out.append((kind, value))
    return out


class _Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self, offset=0):
        j = self.i + offset
        return self.t[j] if j < len(self.t) else ("eof", None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def value(self):
        kind, val = self.take()
        if kind in ("str", "num"):
            return val
        if kind == "name":
            if val == "true":
                return True
            if val == "false":
                return False
            if val == "nil":
                return None
            # function calls / identifiers: skip a balanced (...) if present, keep the name
            return val
        if kind == "op" and val == "{":
            return self.table()
        raise ValueError(f"unexpected token {kind} {val!r} at {self.i}")

    def table(self):
        keyed, positional = {}, []
        while True:
            kind, val = self.peek()
            if kind == "op" and val == "}":
                self.take()
                break
            if kind == "op" and val in ",;":
                self.take()
                continue
            if kind == "op" and val == "[":
                self.take()
                key = self.value()
                assert self.take() == ("op", "]")
                assert self.take() == ("op", "=")
                keyed[key] = self.value()
            elif kind == "name" and self.peek(1) == ("op", "="):
                self.take()
                self.take()
                keyed[val] = self.value()
            else:
                positional.append(self.value())
        if keyed and positional:
            for n, item in enumerate(positional, 1):
                keyed.setdefault(n, item)
            return keyed
        if keyed:
            if all(isinstance(k, int) for k in keyed) and sorted(keyed) == list(range(1, len(keyed) + 1)):
                return [keyed[k] for k in sorted(keyed)]
            return keyed
        return positional


def parse(text: str):
    """Parse the table following the last top-level `return` of a data module."""
    text = re.sub(r"</?nowiki>", "", text)
    start = text.rfind("\nreturn {")
    if start < 0:
        start = text.find("return {")
    if start < 0:
        raise ValueError("no `return {` found")
    tokens = _tokens(text[text.index("{", start):])
    parser = _Parser(tokens)
    assert parser.take() == ("op", "{")
    return parser.table()
