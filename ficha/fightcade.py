"""O que é comum aos emuladores: caminhos do flatpak e como rodar coisas lá dentro."""

import os
import subprocess

APP_ID = "com.fightcade.Fightcade"
DATA = os.path.expanduser("~/.var/app/%s/data" % APP_ID)
EMULATOR = "/app/fightcade/Fightcade/emulator"


def _running_instance():
    """(instância, env do frontend) se o Fightcade já estiver aberto."""
    out = subprocess.run(["flatpak", "ps", "--columns=instance,application"],
                         capture_output=True, text=True).stdout
    inst = next((l.split()[0] for l in out.splitlines() if APP_ID in l), None)
    if inst is None:
        return None, None
    pid = subprocess.run(["pgrep", "-o", "-f", "^/bin/sh /app/bin/fightcade"],
                         capture_output=True, text=True).stdout.split()
    env = []
    if pid:
        try:
            env = [e for e in open("/proc/%s/environ" % pid[0], "rb").read().decode().split("\0") if "=" in e]
        except OSError:
            pass
    return inst, env


def run(script, *args):
    """Roda um script sh dentro do flatpak, sem esperar.

    Se o Fightcade já está aberto, entra na mesma instância com o ambiente do
    frontend: duas instâncias teriam /tmp separados e subiriam dois wineservers
    no mesmo prefixo.
    """
    inst, env = _running_instance()
    if inst and env:
        cmd = ["flatpak", "enter", inst, "env", "-i"] + env + ["sh", "-c", script, "sh"] + list(args)
    else:
        cmd = ["flatpak", "run", "--command=sh", APP_ID, "-c", script, "sh"] + list(args)
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def is_running(pattern):
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def stop(pattern):
    subprocess.run(["pkill", "-f", pattern], capture_output=True)
