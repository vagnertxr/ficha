"""ficha — controles plug-and-play pra jogatina presencial.

  ficha                         sobe o hub e o painel (http://localhost:7373)
  ficha jogar [jogo]            idem, e já abre o jogo          (en: play)
  ficha treino [jogo]           idem, no modo treino            (en: training)
  ficha jogos                   lista os jogos                  (en: games)
  ficha instalar [jogo]         aplica a config que o jogo precisa   (en: install)
  ficha restaurar [jogo]        volta a config de antes do ficha     (en: restore)
  ficha steam configurar jogo   ajusta a Steam pro jogo, com confirmação (en: steam setup)
"""

import argparse
import json
import signal
import sys
import urllib.request
import webbrowser

from . import backends, config, i18n
from .games import DEFAULT_GAME, GAMES
from .i18n import t
from .profiles import ProfileStore

ALIASES = {"run": "rodar", "play": "jogar", "training": "treino", "games": "jogos",
           "install": "instalar", "restore": "restaurar", "setup": "configurar"}


def _post(url, action, body):
    req = urllib.request.Request("%s/api/%s" % (url, action), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=3).read()


def _already_running(url):
    try:
        return "slots" in json.loads(urllib.request.urlopen(url + "/state", timeout=1).read())
    except (OSError, ValueError):
        return False


def parse(argv):
    ap = argparse.ArgumentParser(prog="ficha", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", nargs="?", default="rodar")
    ap.add_argument("alvo", nargs="*", help="jogo (ou, em 'steam configurar', o jogo)")
    ap.add_argument("--jogo", "--game", dest="jogo", help="jogo (id do TOML)")
    ap.add_argument("--porta", "--port", dest="porta", type=int, default=config.CONFIG["porta"])
    ap.add_argument("--lan", action="store_true", default=config.CONFIG["lan"],
                    help="deixa abrir o painel pelo celular na rede local")
    ap.add_argument("--sem-navegador", "--no-browser", dest="sem_navegador", action="store_true",
                    help="não abre o painel sozinho")
    ap.add_argument("--lang", choices=i18n.LANGS, help="idioma (pt/en)")
    # steam configurar
    ap.add_argument("--proton", help="steam configurar: fixa a versão do Proton (ex.: proton_9)")
    ap.add_argument("--steam-input-global", choices=["off"], help="steam configurar: desliga o Steam Input pra todos os controles")
    ap.add_argument("--simular", "--dry-run", dest="simular", action="store_true", help="steam configurar: só mostra o que mudaria")
    ap.add_argument("--sim", "--yes", dest="sim", action="store_true", help="steam configurar: não pergunta")
    args = ap.parse_args(argv)
    args.comando = ALIASES.get(args.comando, args.comando)
    args.alvo = [ALIASES.get(a, a) for a in args.alvo]
    return args


def _game_arg(args, required=False):
    gid = args.jogo or (args.alvo[0] if args.alvo else None)
    if gid is None:
        if required:
            sys.exit(t("cli.need_game", games=", ".join(sorted(GAMES))))
        return None
    if gid not in GAMES:
        sys.exit(t("cli.unknown_game", game=gid, games=", ".join(sorted(GAMES))))
    return gid


def cmd_games():
    for g in GAMES.values():
        b = backends.get(g.backend_type)
        mark = "✓" if g.installed() else "·"
        print("%s %-12s %-40s %s" % (mark, g.id, g.title, b.label(g)))
    print("\n" + t("cli.games_hint", builtin="ficha/games/", user=config.config_dir() + "/games/"))


def main(argv=None):
    args = parse(sys.argv[1:] if argv is None else argv)
    store = ProfileStore()
    i18n.set_lang(args.lang or store.data.get("idioma") or config.CONFIG.get("idioma"))

    if args.comando == "jogos":
        return cmd_games()

    if args.comando == "steam":
        from .backends import steam_setup
        if not args.alvo or args.alvo[0] != "configurar":
            sys.exit(t("cli.steam_usage"))
        args.alvo = args.alvo[1:]
        return steam_setup.main(GAMES[_game_arg(args, required=True)], args)

    if args.comando == "restaurar":
        game = GAMES[_game_arg(args) or DEFAULT_GAME]
        b = backends.get(game.backend_type)
        if not hasattr(b, "restore") or not b.restore(game):
            sys.exit(t("cli.no_backup", game=game.short))
        print(t("cli.restored", game=game.short))
        return

    if args.comando == "instalar":
        gid = _game_arg(args)
        for game in ([GAMES[gid]] if gid else GAMES.values()):
            backends.get(game.backend_type).install(game)
            print(t("cli.installed", game=game.short))
        return

    if args.comando not in ("rodar", "jogar", "treino"):
        sys.exit(t("cli.unknown_command", command=args.comando) + "\n\n" + __doc__)
    gid = _game_arg(args)
    mode = "training" if args.comando == "treino" else "play"

    url = "http://localhost:%d" % args.porta
    if _already_running(url):
        # Atalho clicado de novo: só repassa o pedido pro ficha que já está de pé.
        if gid:
            _post(url, "game", {"game": gid})
        if args.comando == "rodar":
            webbrowser.open(url)
        else:
            _post(url, "launch", {"mode": mode})
        print(t("cli.forwarded"))
        return

    from .core import Hub
    from .web import Panel
    try:
        hub = Hub(store=store)
    except PermissionError:
        sys.exit(t("cli.no_uinput"))
    except ImportError as e:   # Windows sem as dependências opcionais
        sys.exit(t("cli.missing_deps", error=e))
    if gid:
        hub.set_game(gid)
    b = backends.get(hub.game.backend_type)
    if b.check(hub.game):
        if b.is_running(hub.game):
            print(t("cli.game_open_warning"))
        b.install(hub.game)
        print(t("cli.installed", game=hub.game.short))

    panel = Panel(hub)
    panel.serve("0.0.0.0" if args.lan else "127.0.0.1", args.porta)
    print(t("cli.running_lan" if args.lan else "cli.running", url=url))
    print(t("cli.ctrl_c"))

    def stop(*_):
        hub.running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    if args.comando in ("jogar", "treino"):
        panel.action("launch", {"mode": mode})
    elif not args.sem_navegador:
        webbrowser.open(url)

    try:
        hub.run()
    finally:
        hub.close()
        print("\n" + t("cli.stopped"))


if __name__ == "__main__":
    main()
