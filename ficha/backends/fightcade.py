"""O que é comum aos emuladores do Fightcade: rodar coisas lá dentro."""

import os
import subprocess
import sys

from .. import config
from .common import spawn

APP_ID = "com.fightcade.Fightcade"
FLATPAK_EMULATOR = "/app/fightcade/Fightcade/emulator"


def where():
    return config.fightcade()


def _running_instance():
    """(instância, env do frontend) se o Fightcade flatpak já estiver aberto."""
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


def run_flatpak(script, *args):
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
    return spawn(cmd)


def open_url(url):
    """Abre um fcade://… do jeito que o Fightcade faz (play/training)."""
    fc = where()
    if fc.kind == "flatpak":
        script = ('. /app/bin/get-wine-prefix; export WINEPREFIX WINEDEBUG=-all; '
                  'cd %s && exec ./fcade "$1"' % FLATPAK_EMULATOR)
        return run_flatpak(script, url)
    if fc.kind == "windows":   # não testado
        return spawn([os.path.join(fc.emulator, "fcade.exe"), url], cwd=fc.emulator)
    return spawn(["sh", os.path.join(fc.emulator, "fcade.sh"), url], cwd=fc.emulator)   # Linux nativo, não testado


def label():
    return "Fightcade" + ("" if where().kind == "flatpak" or sys.platform == "win32" else " (nativo)")
