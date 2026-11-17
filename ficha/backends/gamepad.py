"""Genérico: qualquer jogo/emulador que lê controle (SDL, XInput, evdev).

O ficha sai pelos dois controles virtuais "ficha P1/P2" (layout Xbox). Se o
jogo usa SDL, o ficha o abre com um filtro que esconde os controles físicos,
então P1 e P2 são sempre os do ficha, na ordem certa.

[backend]
type = "gamepad"
command = ["retroarch", "-L", "core.so", "jogo.zip"]   # opcional: sem isso, o ficha não abre o jogo
process = "retroarch"                                  # opcional: pra saber se está aberto e fechar
files = ["/caminho/jogo.zip"]                          # opcional: pra saber se está instalado
sdl_filter = true                                      # padrão true

Alvos dos botões: a b x y lb rb lt rt back start guide l3 r3.
"""

import os
import shlex

from .. import platform as platform_mod
from .common import kill, pids, sdl_filter_env, spawn, vpad_targets

NAME = "gamepad"
OUTPUT = "vpad"


def label(game):
    return game.backend.get("label", "Controle virtual")


def installed(game):
    files = game.backend.get("files")
    return not files or any(os.path.exists(os.path.expanduser(f)) for f in files)


def check(game):
    return []


def install(game):
    pass


def _process(game):
    return game.backend.get("process")


def is_running(game=None):
    return bool(game and _process(game) and pids(_process(game)))


def launch(game, mode="play"):
    cmd = game.backend.get("command")
    if not cmd:
        return None
    cmd = shlex.split(cmd) if isinstance(cmd, str) else [os.path.expanduser(c) for c in cmd]
    env = sdl_filter_env(platform_mod.vpad_id()) if game.backend.get("sdl_filter", True) else None
    return spawn(cmd, env=env)


def stop(game=None):
    if game and _process(game):
        kill(_process(game))


targets = vpad_targets
