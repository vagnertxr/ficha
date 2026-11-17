"""Genérico: qualquer jogo configurável por teclado.

O ficha aperta teclas num teclado virtual. Cada botão diz a tecla de cada lado:
target = ["KEY_U", "KEY_Z"]   (P1, P2). Direções e START/SELECT também por lado:

[backend]
type = "keyboard"
command = ["meu-jogo"]       # opcional
process = "meu-jogo"         # opcional
directions = [["KEY_W", "KEY_S", "KEY_A", "KEY_D"], ["KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT"]]

[system]
start = ["KEY_1", "KEY_2"]
coin = ["KEY_5", "KEY_6"]

Nomes de tecla: veja ficha/codes.py (KEYS). Cuidado: as teclas vão pra janela
em foco, então o ficha só manda tecla com o jogo aberto (precisa de 'process').
"""

from ..codes import KEYS
from . import gamepad
from .gamepad import check, install, installed, is_running, stop  # noqa: F401 (mesma lógica)

NAME = "keyboard"
OUTPUT = "keyboard"
DEFAULT_DIRECTIONS = [["KEY_W", "KEY_S", "KEY_A", "KEY_D"], ["KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT"]]


def label(game):
    return game.backend.get("label", "Teclado virtual")


def targets(game, slot, acts):
    dirs = dict(zip(("up", "down", "left", "right"), game.backend.get("directions", DEFAULT_DIRECTIONS)[slot]))
    out = set()
    for a in acts:
        name = dirs.get(a) or game.target(a, slot)
        if name in KEYS:
            out.add(("key", KEYS[name]))
    return out


def launch(game, mode="play"):
    if "sdl_filter" not in game.backend:   # jogo de teclado: não esconde controles por padrão
        game.backend["sdl_filter"] = False
    return gamepad.launch(game, mode)
