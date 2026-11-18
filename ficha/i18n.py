"""Idiomas: pt (português do Brasil) e en.

Os textos ficam em ficha/locales/<idioma>.json. t("chave", nome=...) devolve o
texto no idioma atual; chave sem tradução cai pro português e, por fim, pra própria chave.
"""

import importlib.resources
import json
import locale
import os

LANGS = ("pt", "en")
_cache = {}
_lang = None


def _detect():
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v:
            return "pt" if v.lower().startswith("pt") else "en"
    try:
        v = locale.getlocale()[0] or ""
    except ValueError:
        v = ""
    return "pt" if v.lower().startswith("pt") else "en"


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGS else _detect()


def lang():
    if _lang is None:
        set_lang(None)
    return _lang


def table(code=None):
    code = code or lang()
    if code not in _cache:
        res = importlib.resources.files("ficha").joinpath("locales", code + ".json")
        _cache[code] = json.loads(res.read_text(encoding="utf-8"))
    return _cache[code]


def t(key, **args):
    text = table().get(key) or table("pt").get(key) or key
    return text.format(**args) if args else text


def pick(value):
    """Texto bilíngue de um TOML: {pt = "...", en = "..."} ou uma string só."""
    if isinstance(value, dict):
        return value.get(lang()) or value.get("pt") or value.get("en") or next(iter(value.values()), "")
    return value
