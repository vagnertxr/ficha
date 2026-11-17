"""ficha — controles plug-and-play pro Fightcade (FBNeo) em jogatina presencial.

  python -m ficha              sobe o hub e o painel (http://localhost:7373)
  python -m ficha jogar        idem, e já abre o 3rd Strike
  python -m ficha treino       idem, no modo treino
  python -m ficha instalar     só aponta a config do jogo pro teclado virtual
  python -m ficha restaurar    volta a config que existia antes do ficha
"""

import argparse
import json
import os
import shutil
import signal
import sys
import urllib.request
import webbrowser

from . import fbneo
from .web import EMULATORS
from .core import Hub
from .games import DEFAULT_GAME, GAMES
from .web import Panel


def _post(url, action, body):
    req = urllib.request.Request("%s/api/%s" % (url, action), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=3).read()


def _already_running(url):
    try:
        return "slots" in json.loads(urllib.request.urlopen(url + "/state", timeout=1).read())
    except (OSError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser(prog="ficha", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", nargs="?", default="rodar", choices=["rodar", "jogar", "treino", "instalar", "restaurar"])
    ap.add_argument("--jogo", choices=sorted(GAMES), help="jogo (padrão: o último usado, ou 3rd Strike)")
    ap.add_argument("--porta", type=int, default=7373)
    ap.add_argument("--lan", action="store_true", help="deixa abrir o painel pelo celular na rede local")
    ap.add_argument("--sem-navegador", action="store_true", help="não abre o painel sozinho")
    args = ap.parse_args()

    if args.comando == "restaurar":
        args.jogo = args.jogo or DEFAULT_GAME
        path = fbneo.ini_path(args.jogo)
        backup = path + ".antes-do-ficha"
        if not os.path.exists(backup):
            sys.exit("Não achei backup em %s" % backup)
        shutil.copy2(backup, path)
        print("Config original do %s restaurada." % args.jogo)
        return

    url = "http://localhost:%d" % args.porta
    if args.comando in ("rodar", "jogar", "treino") and _already_running(url):
        # Atalho clicado de novo: só repassa o pedido pro ficha que já está de pé.
        if args.jogo:
            _post(url, "game", {"game": args.jogo})
        if args.comando == "rodar":
            webbrowser.open(url)
        else:
            _post(url, "launch", {"mode": "training" if args.comando == "treino" else "play"})
        print("ficha já estava rodando; pedido repassado.")
        return

    if args.comando == "instalar":
        for gid in ([args.jogo] if args.jogo else sorted(GAMES)):
            EMULATORS[GAMES[gid].emulator].install_ini(gid)
            print("Config de controles do %s apontada pro ficha" % gid)
        return

    try:
        hub = Hub()
    except PermissionError:
        sys.exit("Sem acesso a /dev/uinput. Rode num login local (o systemd dá a permissão pro usuário da sessão).")
    if args.jogo:
        hub.set_game(args.jogo)
    if hub.game.emulator == "fbneo" and fbneo.check_ini(hub.game.id):
        if fbneo.is_running():
            print("Aviso: o jogo está aberto; o FBNeo regrava a config ao fechar.")
        fbneo.install_ini(hub.game.id)
        print("Config de controles do %s apontada pro ficha (backup: %s.antes-do-ficha)"
              % (hub.game.id, fbneo.ini_path(hub.game.id)))

    panel = Panel(hub)
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    panel.serve(host, args.porta)
    print("ficha rodando — painel em %s%s" % (url, " (e na rede local)" if args.lan else ""))
    print("Ctrl+C pra sair.")

    def stop(*_):
        hub.running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    if args.comando in ("jogar", "treino"):
        panel.action("launch", {"mode": "training" if args.comando == "treino" else "play"})
    elif not args.sem_navegador:
        webbrowser.open(url)

    try:
        hub.run()
    finally:
        hub.close()
        print("\nficha encerrado, teclas soltas.")


if __name__ == "__main__":
    main()
