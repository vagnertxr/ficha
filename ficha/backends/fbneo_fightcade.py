"""FBNeo do Fightcade: P1/P2 pelo teclado virtual.

O FBNeo identifica joystick por índice, que muda com a ordem de plugar (e o
wine lê DS4 por hidraw, então não dá pra esconder nada dele). Então o ficha
aponta o .ini do jogo pras teclas fixas do teclado virtual (profiles.KEYMAP),
uma vez só e com backup, e manda as teclas certas pra cada lado.
"""

import os
import re
import shutil

from .. import i18n
from ..profiles import KEYMAP
from . import fightcade
from .common import kill, pids
from ..fileio import read_text

NAME = "fbneo-fightcade"
OUTPUT = "keyboard"
PROCESS = "fcadefbneo.exe"
SYSTEM_INPUTS = {"Up": "up", "Down": "down", "Left": "left", "Right": "right",
                 "Start": "start", "Coin": "coin"}
INPUT_RE = re.compile(r'^input\s+"(P([12]) ([^"]+))"\s+(.*)$')
MINIMAL_INI = """// Gerado pelo ficha

version 0x029744

// --- Inputs -----------------------------------------------------------------

"""


def label(game):
    return fightcade.label() + " · FBNeo"


def ini_path(game):
    return os.path.join(fightcade.where().fbneo_games, game.backend.get("rom", game.id) + ".ini")


def installed(game):
    roms = fightcade.where().roms["fbneo"]
    return any(os.path.exists(os.path.join(roms, f)) for f in game.backend.get("files", []))


def _input_names(game):
    """Nome do input no .ini -> tecla do KEYMAP (b1..b6 na ordem dos botões do jogo)."""
    names = dict(SYSTEM_INPUTS)
    for i, (_, _, _, ini_name) in enumerate(game.buttons):
        names[ini_name] = "b%d" % (i + 1)
    return names


def _wanted(game, slot, name):
    key = _input_names(game).get(name)
    if key is None:
        return None
    return "switch 0x%02X" % KEYMAP[slot][key][1]


def _line(full, value):
    return 'input  %s %s' % (('"%s"' % full).ljust(18), value)


def check(game):
    """Inputs que não batem com o teclado virtual (vazio = tudo certo)."""
    try:
        lines = read_text(ini_path(game), newline="").splitlines()
    except OSError:
        return ["(.ini não existe)"]
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


def install(game):
    """Aponta P1/P2 do jogo pras teclas do teclado virtual. Faz backup uma vez."""
    path = ini_path(game)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        backup = path + ".antes-do-ficha"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        raw = read_text(path, newline="")
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


def restore(game):
    path = ini_path(game)
    backup = path + ".antes-do-ficha"
    if not os.path.exists(backup):
        return False
    shutil.copy2(backup, path)
    return True


def ensure_fullscreen():
    """bVidAutoSwitchFull 1: o FBNeo vai pra tela cheia assim que o jogo carrega.
    Vale também pro Fightcade online (é o .ini geral do emulador)."""
    main = fightcade.where().fbneo_main_ini
    try:
        text = read_text(main, newline="")   # o .ini é \r\n: preservar
    except OSError:
        return
    new = re.sub(r"^bVidAutoSwitchFull[ \t]+\d+", "bVidAutoSwitchFull 1", text, flags=re.M)
    if new != text:
        backup = main + ".antes-do-ficha"
        if not os.path.exists(backup):
            shutil.copy2(main, backup)
        with open(main + ".tmp", "w", newline="") as f:
            f.write(new)
        os.replace(main + ".tmp", main)


def is_running(game=None):
    return bool(pids(PROCESS))


def launch(game, mode="play"):
    if not is_running():   # com o FBNeo aberto ele regravaria o .ini ao fechar
        ensure_fullscreen()
    return fightcade.open_url("fcade://%s/fbneo/%s" % (mode, game.backend.get("rom", game.id)))


def stop(game=None):
    kill(PROCESS)


def targets(game, slot, acts):
    km = KEYMAP[slot]
    slot_of = {b: "b%d" % (i + 1) for i, b in enumerate(game.button_ids)}
    return {("key", km[slot_of.get(a, a)][0]) for a in acts if slot_of.get(a, a) in km}
