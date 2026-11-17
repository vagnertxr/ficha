"""Backends: como cada tipo de jogo é aberto e como os botões viram saída.

Cada módulo expõe:
  NAME, OUTPUT ("keyboard" ou "vpad")
  label(game)              texto curto ("Fightcade · FBNeo")
  installed(game)          o jogo está no disco?
  check(game) / install(game)   config que o ficha precisa (vazio = ok) / aplicar
  is_running(game) / launch(game, mode) / stop(game)
  targets(game, slot, ações)    conjunto de saídas ("key", código) / ("btn"|"axis"|"hat", ...)
"""

from . import fbneo_fightcade, flycast_fightcade, gamepad, keyboard, steam

REGISTRY = {m.NAME: m for m in (fbneo_fightcade, flycast_fightcade, steam, gamepad, keyboard)}


def get(name):
    try:
        return REGISTRY[name]
    except KeyError:
        raise KeyError("backend desconhecido: %s (existem: %s)" % (name, ", ".join(sorted(REGISTRY))))


def any_running(games):
    return any(get(g.backend_type).is_running(g) for g in games)
