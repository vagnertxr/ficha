"""Jogos da Steam (flatpak) rodando no Proton.

A Steam embrulha todo controle (inclusive os virtuais do ficha) em controles
virtuais dela, e o Proton pega esses por fora dos hints do SDL. Por isso o jogo
precisa estar com o Steam Input desligado e com a opção de inicialização
"$HOME/ficha-steam.sh %command%": com o ficha aberto, o script deixa o jogo
enxergar só os dois controles virtuais (P1 = 1º, P2 = 2º).
"""

import os
import subprocess

from .games import GAMES

STEAM_HOME = os.path.expanduser("~/.var/app/com.valvesoftware.Steam")
WRAPPER = os.path.join(STEAM_HOME, "ficha-steam.sh")
WRAPPER_SH = """#!/bin/bash
# ficha: opção de inicialização dos jogos da Steam:
#   "$HOME/ficha-steam.sh [--tela-cheia LARGURAxALTURA] %command%"
# Com o ficha aberto (painel em 127.0.0.1:7373), o jogo só enxerga os dois
# controles virtuais dele (1209:f1c5); com o ficha fechado, roda normal.
# --tela-cheia LxA: aceito e ignorado. A ideia era rodar o jogo no gamescope,
# mas o GG travou ("não respondendo") lá também, como em toda tela cheia que
# testamos aqui (30/10/2026). Só a janela funciona.
if [ "$1" = "--tela-cheia" ]; then
    shift 2
fi
if (exec 3<>/dev/tcp/127.0.0.1/7373) 2>/dev/null; then
    export PROTON_PREFER_SDL=1
    export SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT=0x1209/0xf1c5
    export SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD=0
fi
# Diagnóstico: com o arquivo ~/ficha-debug (dentro da Steam), liga o log do Proton
# em ~/steam-<appid>.log.
if [ -f "$HOME/ficha-debug" ]; then
    export PROTON_LOG=1
fi
exec "$@"
"""


def check_ini(game):
    try:
        return [] if open(WRAPPER).read() == WRAPPER_SH else ["ficha-steam.sh desatualizado"]
    except OSError:
        return ["ficha-steam.sh não existe"]


def install_ini(game):
    with open(WRAPPER, "w") as f:
        f.write(WRAPPER_SH)
    os.chmod(WRAPPER, 0o755)


def _game_pids():
    """PIDs do executável do jogo, pelo nome do processo (comm, 15 caracteres).
    Casar pela linha de comando pegaria também o reaper e o runtime da Steam,
    que carregam o caminho do .exe nos argumentos; matar esses derruba a Steam."""
    names = {g.process[:15] for g in GAMES.values() if g.emulator == "steam"}
    pids = []
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                if open("/proc/%s/comm" % pid).read().strip() in names:
                    pids.append(int(pid))
            except OSError:
                pass
    return pids


def is_running():
    return bool(_game_pids())


COMPAT = os.path.join(STEAM_HOME, ".local/share/Steam/steamapps/compatdata")
# Tela cheia do GG: modo 1 (tela cheia) em 1920x1080, que o Proton escala pra tela.
# Funciona no Proton 9. No Proton Experimental (11, out/2026) o GG travava em
# qualquer modo, e foi isso que pareceu ser problema de tela cheia.
DISPLAY = {
    "ggxxacpr": ("348550/pfx/drive_c/users/steamuser/Documents/ARC SYSTEM WORKS/GGXXAC/Config/DisplaySetting.cfg",
                 {":FullScreen": "1", ":FullscreenResolutionWidth": "1920", ":FullscreenResolutionHeight": "1080"}),
}


def _screen_size():
    out = subprocess.run(["xprop", "-root", "_NET_DESKTOP_GEOMETRY"], capture_output=True, text=True).stdout
    nums = [int(n) for n in out.split("=")[-1].replace(",", " ").split() if n.isdigit()]
    return (nums[0], nums[1]) if len(nums) == 2 else None


def ensure_fullscreen(game):
    """Põe o jogo em tela cheia. Só com o jogo fechado: ele regrava o arquivo
    quando muda a config."""
    if game not in DISPLAY:
        return
    rel, wanted = DISPLAY[game]
    size = _screen_size()
    if size is None:
        return
    wanted = {k: v.format(w=size[0], h=size[1]) for k, v in wanted.items()}
    path = os.path.join(COMPAT, rel)
    try:
        text = open(path, newline="").read()
    except OSError:
        return
    lines = text.split("\r\n")
    changed = False
    for key, value in wanted.items():
        if key not in lines:
            continue
        i = lines.index(key) + 1
        while i < len(lines) and lines[i].startswith("#"):
            i += 1
        if i < len(lines) and lines[i] != value:
            lines[i], changed = value, True
    if not changed:
        return
    backup = path + ".antes-do-ficha"
    if not os.path.exists(backup):
        with open(backup, "w", newline="") as f:
            f.write(text)
    with open(path + ".tmp", "w", newline="") as f:
        f.write("\r\n".join(lines))
    os.replace(path + ".tmp", path)


def launch(game, mode="play"):
    if not is_running():
        ensure_fullscreen(game)
    # Com a Steam aberta, isso só repassa o pedido pra ela.
    return subprocess.Popen(["flatpak", "run", "com.valvesoftware.Steam", "steam://rungameid/%d" % GAMES[game].steam_appid],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def stop():
    # SIGTERM só no .exe: o Proton e a Steam encerram o resto sozinhos.
    for pid in _game_pids():
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def client_running():
    """A Steam (cliente) está aberta? Pelo nome do processo, dentro do flatpak dela."""
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                if open("/proc/%s/comm" % pid).read().strip() == "steam" and \
                        "com.valvesoftware.Steam" in os.readlink("/proc/%s/exe" % pid):
                    return True
            except OSError:
                pass
    return False


def shutdown_client():
    subprocess.Popen(["flatpak", "run", "com.valvesoftware.Steam", "-shutdown"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
