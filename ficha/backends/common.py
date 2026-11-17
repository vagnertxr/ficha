"""Peças comuns aos backends: saída pelos controles virtuais e processos."""

import os
import signal
import subprocess
import sys

# Botão do controle virtual (layout Xbox) -> (tipo, código evdev).
VPAD_OUT = {"a": ("btn", 0x130), "b": ("btn", 0x131), "x": ("btn", 0x133), "y": ("btn", 0x134),
            "lb": ("btn", 0x136), "rb": ("btn", 0x137), "back": ("btn", 0x13A), "start": ("btn", 0x13B),
            "guide": ("btn", 0x13C), "l3": ("btn", 0x13D), "r3": ("btn", 0x13E),
            "lt": ("axis", 0x02), "rt": ("axis", 0x05)}
DIRECTIONS = ("up", "down", "left", "right")


def vpad_targets(game, slot, acts):
    out = set()
    for a in acts:
        if a in DIRECTIONS:
            out.add(("hat", a))
        else:
            t = game.target(a, slot)
            if t in VPAD_OUT:
                out.add(VPAD_OUT[t])
    return out


def _pids_linux(names):
    names = {n[:15] for n in names}   # /proc/<pid>/comm guarda só 15 caracteres
    pids = []
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                with open("/proc/%s/comm" % pid) as f:
                    if f.read().strip() in names:
                        pids.append(int(pid))
            except OSError:
                pass
    return pids


def _pids_windows(names):
    pids = []
    for name in names:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq %s" % name, "/FO", "CSV", "/NH"],
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) > 1 and parts[0].lower() == name.lower():
                pids.append(int(parts[1]))
    return pids


def pids(*names):
    """PIDs pelo NOME do processo, nunca pela linha de comando inteira: casar a
    linha de comando pega também lançadores (o reaper da Steam, scripts) que
    carregam o nome do jogo nos argumentos, e matar esses derruba a Steam."""
    return _pids_windows(names) if sys.platform == "win32" else _pids_linux(names)


def kill(*names):
    for pid in pids(*names):
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def spawn(cmd, env=None, cwd=None):
    """Roda sem esperar e sem amarrar ao terminal do ficha."""
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "env": env, "cwd": cwd}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def sdl_filter_env(vpad_id, base=None):
    """Ambiente em que o SDL do jogo só enxerga os controles virtuais do ficha."""
    env = dict(os.environ if base is None else base)
    env["SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT"] = "0x%04x/0x%04x" % vpad_id
    return env
