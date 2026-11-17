"""Flycast (Dreamcast/Naomi) do Fightcade.

O Flycast liga controle a porta pelo índice SDL e põe o teclado inteiro numa
porta só, então aqui o ficha sai por dois controles virtuais ("ficha P1/P2").
O SDL embutido nele (2.26) respeita SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT
também pra joystick cru: com isso o Flycast só enxerga os virtuais, que viram
os índices 0 e 1 (P1 é criado antes, então tem eventN menor). Nada é gravado
no emu.cfg: as portas vão por -config, que não persiste.
"""

import os

from . import fightcade
from .games import GAMES

ROMS_DIR = os.path.join(fightcade.DATA, "ROMs/flycast")
VPAD_VENDOR, VPAD_PRODUCT = 0x1209, 0xF1C5


def check_ini(game):
    return []


def install_ini(game):
    pass


def is_running():
    return fightcade.is_running("flycast.elf")


def launch(game, mode="play"):
    rom = next(z for z in GAMES[game].zips if os.path.exists(os.path.join(ROMS_DIR, z)))
    script = ('cd %s/flycast && SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT=0x%04x/0x%04x '
              'exec ./flycast.elf -config input:maple_sdl_joystick_0=0,input:maple_sdl_joystick_1=1,window:fullscreen=yes "ROMs/$1"'
              % (fightcade.EMULATOR, VPAD_VENDOR, VPAD_PRODUCT))
    return fightcade.run(script, rom)


def stop():
    fightcade.stop("flycast.elf")
