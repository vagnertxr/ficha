"""Flycast (Dreamcast/Naomi) do Fightcade: P1/P2 pelos dois controles virtuais.

O Flycast liga controle a porta pelo índice SDL e põe o teclado inteiro numa
porta só. O SDL embutido nele respeita SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT
também pra joystick cru: com isso ele só enxerga os controles virtuais do ficha,
que viram os índices 0 e 1. Nada é gravado no emu.cfg: as portas e a tela cheia
vão por -config, que não persiste.
"""

import os
import sys

from .. import platform as platform_mod
from . import fightcade
from .common import kill, pids, sdl_filter_env, spawn, vpad_targets

NAME = "flycast-fightcade"
OUTPUT = "vpad"
PROCESSES = ("flycast.elf", "flycast.exe")
CONFIG_ARGS = "input:maple_sdl_joystick_0=0,input:maple_sdl_joystick_1=1,window:fullscreen=yes"


def label(game):
    return fightcade.label() + " · Flycast"


def _rom(game):
    roms = fightcade.where().roms["flycast"]
    return next((f for f in game.backend.get("files", []) if os.path.exists(os.path.join(roms, f))), None)


def installed(game):
    return _rom(game) is not None


def check(game):
    return []


def install(game):
    pass


def is_running(game=None):
    return bool(pids(*PROCESSES))


def launch(game, mode="play"):
    rom = _rom(game)
    if rom is None:
        return None
    vpad_id = platform_mod.vpad_id()
    fc = fightcade.where()
    if fc.kind == "flatpak":
        script = ('cd %s/flycast && SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT=0x%04x/0x%04x '
                  'exec ./flycast.elf -config %s "ROMs/$1"' % (fightcade.FLATPAK_EMULATOR, vpad_id[0], vpad_id[1], CONFIG_ARGS))
        return fightcade.run_flatpak(script, rom)
    exe = os.path.join(fc.emulator, "flycast", "flycast.exe" if sys.platform == "win32" else "flycast.elf")
    return spawn([exe, "-config", CONFIG_ARGS, os.path.join(fc.roms["flycast"], rom)],   # não testado
                 env=sdl_filter_env(vpad_id), cwd=os.path.dirname(exe))


def stop(game=None):
    kill(*PROCESSES)


targets = vpad_targets
