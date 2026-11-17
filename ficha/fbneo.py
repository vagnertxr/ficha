"""Config de inputs do FBNeo do Fightcade (flatpak) e lançamento do jogo."""

import os
import re
import shutil

from . import fightcade
from .games import DEFAULT_GAME, GAMES
from .profiles import KEYMAP

GAMES_DIR = os.path.join(fightcade.DATA, "config/fcadefbneo/games")

SYSTEM_INPUTS = {"Up": "up", "Down": "down", "Left": "left", "Right": "right",
                 "Start": "start", "Coin": "coin"}


def _input_names(game):
    """Nome do input no .ini -> tecla do KEYMAP (b1..b6 na ordem dos botões do jogo)."""
    names = dict(SYSTEM_INPUTS)
    for i, (_, _, _, ini_name) in enumerate(GAMES[game].buttons):
        names[ini_name] = "b%d" % (i + 1)
    return names


INPUT_RE = re.compile(r'^input\s+"(P([12]) ([^"]+))"\s+(.*)$')

MINIMAL_INI = """// Gerado pelo ficha

version 0x029744

// --- Inputs -----------------------------------------------------------------

"""


def ini_path(game=DEFAULT_GAME):
    return os.path.join(GAMES_DIR, game + ".ini")


def _wanted(game, slot, name):
    key = _input_names(game).get(name)
    if key is None:
        return None
    return "switch 0x%02X" % KEYMAP[slot][key][1]


def _line(full, value):
    return 'input  %s %s' % (('"%s"' % full).ljust(18), value)


def check_ini(game=DEFAULT_GAME):
    """Lista de inputs que não batem com o teclado virtual (vazia = instalado)."""
    try:
        lines = open(ini_path(game)).read().splitlines()
    except OSError:
        return ["(arquivo não existe)"]
    seen, bad = set(), []
    for line in lines:
        m = INPUT_RE.match(line)
        if not m:
            continue
        full, slot, name, value = m.group(1), int(m.group(2)) - 1, m.group(3), m.group(4).strip()
        want = _wanted(game, slot, name)
        if want is None:
            continue
        seen.add(full)
        if value != want:
            bad.append(full)
    for slot in (0, 1):
        for name in _input_names(game):
            full = "P%d %s" % (slot + 1, name)
            if full not in seen:
                bad.append(full)
    return bad


def install_ini(game=DEFAULT_GAME):
    """Aponta P1/P2 do jogo para as teclas do teclado virtual. Faz backup uma vez."""
    path = ini_path(game)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        backup = path + ".antes-do-ficha"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        raw = open(path, newline="").read()
        lines = raw.splitlines()
    else:
        raw, lines = "", MINIMAL_INI.splitlines()
    eol = "\r\n" if "\r\n" in raw or not raw else "\n"   # o FBNeo grava \r\n

    done, out = set(), []
    for line in lines:
        m = INPUT_RE.match(line)
        if m:
            full, slot, name = m.group(1), int(m.group(2)) - 1, m.group(3)
            want = _wanted(game, slot, name)
            if want is not None:
                out.append(_line(full, want))
                done.add(full)
                continue
        out.append(line)

    missing = [("P%d %s" % (s + 1, n), _wanted(game, s, n)) for s in (0, 1) for n in _input_names(game)
               if "P%d %s" % (s + 1, n) not in done]
    if missing:
        at = max((i for i, l in enumerate(out) if INPUT_RE.match(l)), default=len(out) - 1) + 1
        out[at:at] = [_line(full, want) for full, want in missing]

    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        f.write(eol.join(out) + eol)
    os.replace(tmp, path)


def is_running():
    return fightcade.is_running("fcadefbneo.exe")


MAIN_INI = os.path.join(fightcade.DATA, "config/fcadefbneo/fcadefbneo.ini")


def ensure_fullscreen():
    """bVidAutoSwitchFull 1: o FBNeo vai pra tela cheia assim que o jogo carrega.
    Vale também pro Fightcade online (é o .ini geral do emulador)."""
    try:
        text = open(MAIN_INI, newline="").read()   # o .ini é \r\n: preservar
    except OSError:
        return
    new = re.sub(r"^bVidAutoSwitchFull[ \t]+\d+", "bVidAutoSwitchFull 1", text, flags=re.M)
    if new != text:
        backup = MAIN_INI + ".antes-do-ficha"
        if not os.path.exists(backup):
            shutil.copy2(MAIN_INI, backup)
        with open(MAIN_INI + ".tmp", "w", newline="") as f:
            f.write(new)
        os.replace(MAIN_INI + ".tmp", MAIN_INI)


def launch(game=DEFAULT_GAME, mode="play"):
    """Abre o jogo offline (mode='play') ou o modo treino (mode='training').

    Chama o wrapper 'fcade' do próprio Fightcade, com o mesmo WINEPREFIX que o
    frontend usa, em vez de reimplementar a linha de comando do wine.
    """
    if not is_running():   # com o FBNeo aberto ele regravaria o .ini ao fechar
        ensure_fullscreen()
    script = ('. /app/bin/get-wine-prefix; export WINEPREFIX WINEDEBUG=-all; '
              'cd %s && exec ./fcade "$1"' % fightcade.EMULATOR)
    return fightcade.run(script, "fcade://%s/fbneo/%s" % (mode, game))


def stop():
    fightcade.stop("fcadefbneo.exe")
