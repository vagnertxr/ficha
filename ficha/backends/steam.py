"""Jogos da Steam (no Linux, rodando no Proton).

A Steam embrulha todo controle (inclusive os virtuais do ficha) em controles
virtuais dela, e no Linux o Proton pega esses por fora dos hints do SDL. Por
isso o jogo precisa estar com o Steam Input desligado e, no Linux, com a opção
de inicialização "$HOME/ficha-steam.sh %command%": com o ficha aberto, o script
deixa o jogo enxergar só os dois controles virtuais (P1 = 1º, P2 = 2º).
`ficha steam configurar <jogo>` faz esses ajustes (veja steam_setup.py).

[backend]
type = "steam"
appid = 348550
process = "Jogo.exe"                       # nome do executável (pra saber se está aberto)
files = ["Pasta do Jogo/Jogo.exe"]         # relativo a steamapps/common
[backend.display]                          # opcional: tela cheia no formato da Arc System Works
file = "ARC SYSTEM WORKS/.../DisplaySetting.cfg"   # relativo a Documentos (do prefixo, no Proton)
values = { ":FullScreen" = "1" }
"""

import os
import subprocess
import sys

from .. import config
from .. import platform as platform_mod
from .common import kill, pids, spawn, vpad_targets

NAME = "steam"
OUTPUT = "vpad"
WRAPPER_NAME = "ficha-steam.sh"


def where():
    return config.steam()


def label(game):
    return "Steam · Proton" if sys.platform != "win32" else "Steam"


def wrapper_path():
    return os.path.join(where().home, WRAPPER_NAME)


def wrapper_text():
    vid, pid = platform_mod.vpad_id()
    return """#!/bin/bash
# ficha: opção de inicialização dos jogos da Steam:
#   "$HOME/ficha-steam.sh %%command%%"
# Com o ficha aberto (painel em 127.0.0.1:%(port)d), o jogo só enxerga os dois
# controles virtuais dele (%(vid)04x:%(pid)04x); com o ficha fechado, roda normal.
# Aceita e ignora um "--tela-cheia LxA" antigo, de versões anteriores.
if [ "$1" = "--tela-cheia" ]; then
    shift 2
fi
if (exec 3<>/dev/tcp/127.0.0.1/%(port)d) 2>/dev/null; then
    export PROTON_PREFER_SDL=1
    export SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT=0x%(vid)04x/0x%(pid)04x
    export SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD=0
fi
# Diagnóstico: com o arquivo ~/ficha-debug (no $HOME que a Steam enxerga),
# liga o log do Proton em ~/steam-<appid>.log.
if [ -f "$HOME/ficha-debug" ]; then
    export PROTON_LOG=1
fi
exec "$@"
""" % {"port": config.CONFIG["porta"], "vid": vid, "pid": pid}


def installed(game):
    return any(os.path.exists(os.path.join(where().common, f)) for f in game.backend.get("files", []))


def check(game):
    if sys.platform == "win32":
        return []
    try:
        return [] if open(wrapper_path()).read() == wrapper_text() else ["ficha-steam.sh desatualizado"]
    except OSError:
        return ["ficha-steam.sh não existe"]


def install(game):
    if sys.platform == "win32":
        return
    with open(wrapper_path(), "w") as f:
        f.write(wrapper_text())
    os.chmod(wrapper_path(), 0o755)


def _process_names(game=None):
    from ..games import GAMES
    games = [game] if game else [g for g in GAMES.values() if g.backend_type == NAME]
    return [g.backend["process"] for g in games if g.backend.get("process")]


def is_running(game=None):
    names = _process_names(game)
    return bool(names and pids(*names))


def stop(game=None):
    # Só o executável do jogo: o Proton e a Steam encerram o resto sozinhos.
    names = _process_names(game)
    if names:
        kill(*names)


# --- tela cheia ----------------------------------------------------------------

def documents_dir(game):
    if sys.platform == "win32":
        return os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(where().compatdata, str(game.backend["appid"]), "pfx", "drive_c", "users", "steamuser", "Documents")


def ensure_display(game):
    """Formato da Arc System Works: linha ":Chave", comentários "#", linha do valor.
    Só com o jogo fechado: ele regrava o arquivo quando muda a config."""
    spec = game.backend.get("display")
    if not spec:
        return
    path = os.path.join(documents_dir(game), spec["file"])
    try:
        text = open(path, newline="").read()
    except OSError:
        return
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    changed = False
    for key, value in spec.get("values", {}).items():
        if key not in lines:
            continue
        i = lines.index(key) + 1
        while i < len(lines) and lines[i].startswith("#"):
            i += 1
        if i < len(lines) and lines[i] != str(value):
            lines[i], changed = str(value), True
    if not changed:
        return
    backup = path + ".antes-do-ficha"
    if not os.path.exists(backup):
        with open(backup, "w", newline="") as f:
            f.write(text)
    with open(path + ".tmp", "w", newline="") as f:
        f.write(eol.join(lines))
    os.replace(path + ".tmp", path)


# --- abrir e cliente -----------------------------------------------------------

def _open_url(url):
    st = where()
    if sys.platform == "win32":
        os.startfile(url)   # noqa: não testado
        return None
    if st.kind == "flatpak":
        return spawn(["flatpak", "run", "com.valvesoftware.Steam", url])
    return spawn(["steam", url])


def launch(game, mode="play"):
    if not is_running(game):
        ensure_display(game)
    # Com a Steam aberta, isso só repassa o pedido pra ela.
    return _open_url("steam://rungameid/%d" % game.backend["appid"])


def client_running():
    """A Steam (cliente) está aberta?"""
    if sys.platform == "win32":
        return bool(pids("steam.exe"))
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                if open("/proc/%s/comm" % pid).read().strip() == "steam" and \
                        os.path.realpath("/proc/%s/exe" % pid).startswith(os.path.realpath(where().root)):
                    return True
            except OSError:
                pass
    return False


def shutdown_client():
    if sys.platform == "win32":
        os.startfile("steam://exit")   # noqa: não testado
    elif where().kind == "flatpak":
        spawn(["flatpak", "run", "com.valvesoftware.Steam", "-shutdown"])
    else:
        spawn(["steam", "-shutdown"])


targets = vpad_targets
