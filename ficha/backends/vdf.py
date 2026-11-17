"""KeyValues em texto da Valve (localconfig.vdf, config.vdf): ler, mexer, gravar.

Um nó é uma lista ordenada de [chave, valor], onde valor é str ou outro nó.
A gravação segue o formato da própria Steam (tabs, aspas, chaves).
"""

import re

_TOKEN = re.compile(r'\s*(?:"((?:[^"\\]|\\.)*)"|(\{)|(\})|//[^\n]*)', re.S)


class VDFError(ValueError):
    pass


def _unescape(s):
    return s.replace('\\"', '"').replace("\\\\", "\\")


def _escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def loads(text):
    tokens, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            if text[pos:].strip():
                raise VDFError("formato inesperado perto de: %r" % text[pos:pos + 40])
            break
        pos = m.end()
        if m.group(1) is not None:
            tokens.append(("s", _unescape(m.group(1))))
        elif m.group(2):
            tokens.append(("{", None))
        elif m.group(3):
            tokens.append(("}", None))
    root, stack, i = [], [], 0
    node = root
    while i < len(tokens):
        kind, val = tokens[i]
        if kind == "}":
            if not stack:
                raise VDFError("} sobrando")
            node = stack.pop()
            i += 1
            continue
        if kind != "s" or i + 1 >= len(tokens):
            raise VDFError("esperava uma chave")
        nkind, nval = tokens[i + 1]
        if nkind == "s":
            node.append([val, nval])
            i += 2
        elif nkind == "{":
            child = []
            node.append([val, child])
            stack.append(node)
            node = child
            i += 2
        else:
            raise VDFError("chave sem valor: %s" % val)
    if stack:
        raise VDFError("{ sem fechar")
    return root


def dumps(node, depth=0):
    out = []
    tab = "\t" * depth
    for key, val in node:
        if isinstance(val, list):
            out.append('%s"%s"\n%s{\n%s%s}\n' % (tab, _escape(key), tab, dumps(val, depth + 1), tab))
        else:
            out.append('%s"%s"\t\t"%s"\n' % (tab, _escape(key), _escape(val)))
    return "".join(out)


def find(node, key):
    """O par [chave, valor] (chave sem diferenciar maiúsculas, como a Steam)."""
    for pair in node:
        if pair[0].lower() == key.lower():
            return pair
    return None


def path(node, keys, create=False):
    """Desce por 'keys' devolvendo o nó final (ou None; com create, cria o que faltar)."""
    for key in keys:
        pair = find(node, key)
        if pair is None or not isinstance(pair[1], list):
            if not create:
                return None
            if pair is None:
                pair = [key, []]
                node.append(pair)
            else:
                pair[1] = []
        node = pair[1]
    return node


def get(node, key, default=None):
    pair = find(node, key)
    return pair[1] if pair else default


def set(node, key, value):
    """Grava e devolve o valor anterior (None se não existia)."""
    pair = find(node, key)
    if pair is None:
        node.append([key, value])
        return None
    old, pair[1] = pair[1], value
    return old
