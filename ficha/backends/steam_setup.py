"""`ficha steam configurar <jogo>`: prepara a Steam pra um jogo usar os controles do ficha.

Mostra exatamente o que vai mudar, faz backup com data e hora, pede pra fechar a
Steam (ela regrava esses arquivos ao sair) e só grava com confirmação.

No jogo (localconfig.vdf da conta):
  UseSteamControllerConfig = 0       Steam Input desligado nesse jogo
  LaunchOptions = ficha-steam.sh     (Linux) filtro pros controles do ficha no Proton
Opcionais:
  --proton proton_9                  fixa a versão do Proton desse jogo (config.vdf)
  --steam-input-global off           desliga o Steam Input pra Xbox/PlayStation/Switch/genéricos
                                     em TODOS os jogos (senão a Steam ainda cria controles
                                     virtuais dela, que o Proton coloca na frente dos do ficha)
"""

import glob
import os
import shutil
import sys
import time

from .. import config
from ..i18n import t
from . import steam, vdf

LAUNCH_OPTIONS = "$HOME/ficha-steam.sh %command%"
GLOBAL_INPUT_KEYS = ("SteamController_XBoxSupport", "SteamController_PSSupport",
                     "SteamController_SwitchSupport", "SteamController_GenericGamepadSupport")


def localconfig_paths(root):
    """localconfig.vdf de cada conta, a mais usada por último primeiro."""
    paths = glob.glob(os.path.join(root, "userdata", "*", "config", "localconfig.vdf"))
    return sorted(paths, key=os.path.getmtime, reverse=True)


def plan(game, root, proton=None, global_input=False, platform=sys.platform):
    """Lista de mudanças: (arquivo, árvore, nó, chave, valor novo, valor atual).
    Não grava nada."""
    changes = []
    appid = str(game.backend["appid"])
    locals_ = localconfig_paths(root)
    if not locals_:
        raise FileNotFoundError(t("steam.no_localconfig", root=root))
    lc_path = locals_[0]
    lc = vdf.loads(open(lc_path, encoding="utf-8").read())
    store = vdf.path(lc, ["UserLocalConfigStore"], create=True)
    app = vdf.path(store, ["Software", "Valve", "Steam", "apps", appid], create=True)
    want = {"UseSteamControllerConfig": "0"}
    if platform != "win32":
        want["LaunchOptions"] = LAUNCH_OPTIONS
    for key, value in want.items():
        changes.append((lc_path, lc, app, key, value, vdf.get(app, key)))
    if global_input:
        for key in GLOBAL_INPUT_KEYS:
            changes.append((lc_path, lc, store, key, "0", vdf.get(store, key)))
    if proton:
        cfg_path = os.path.join(root, "config", "config.vdf")
        cfg = vdf.loads(open(cfg_path, encoding="utf-8").read())
        mapping = vdf.path(cfg, ["InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping", appid],
                           create=True)
        for key, value in (("name", proton), ("config", ""), ("priority", "250")):
            changes.append((cfg_path, cfg, mapping, key, value, vdf.get(mapping, key)))
    return [c for c in changes if c[5] != c[4]]


def apply(changes, stamp=None):
    """Faz backup de cada arquivo tocado e grava. Devolve os backups."""
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    trees, backups = {}, []
    for path, tree, node, key, value, _ in changes:
        vdf.set(node, key, value)
        trees[path] = tree
    for path, tree in trees.items():
        backup = "%s.ficha-%s" % (path, stamp)
        shutil.copy2(path, backup)
        backups.append(backup)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(vdf.dumps(tree))
        os.replace(tmp, path)
    return backups


def _ask(question):
    try:
        return input(question + " ").strip().lower() in ("s", "sim", "y", "yes")
    except EOFError:
        return False


def main(game, args):
    if game.backend_type != steam.NAME:
        sys.exit(t("steam.not_steam", game=game.short))
    st = config.steam()
    changes = plan(game, st.root, proton=args.proton, global_input=args.steam_input_global == "off")
    print(t("steam.header", game=game.title, root=st.root))
    if not changes:
        print(t("steam.nothing"))
    for path, _, _, key, value, old in changes:
        print("  %s\n    %s: %s → %s" % (os.path.relpath(path, st.root), key,
                                       '"%s"' % old if old is not None else t("steam.absent"), '"%s"' % value))
    if sys.platform != "win32":
        print("  " + t("steam.wrapper", path=steam.wrapper_path()))
    if args.steam_input_global == "off":
        print("\n" + t("steam.global_warning"))
    if args.simular:
        print("\n" + t("steam.dry_run"))
        return
    if not args.sim and not _ask("\n" + t("steam.confirm")):
        print(t("steam.cancelled"))
        return
    if steam.client_running():
        if not args.sim and not _ask(t("steam.close_steam")):
            print(t("steam.cancelled"))
            return
        steam.shutdown_client()
        for _ in range(60):
            time.sleep(1)
            if not steam.client_running():
                break
        else:
            sys.exit(t("steam.still_open"))
        # recalcula: a Steam regravou os arquivos ao fechar
        changes = plan(game, st.root, proton=args.proton, global_input=args.steam_input_global == "off")
    backups = apply(changes) if changes else []
    steam.install(game)
    print(t("steam.done"))
    for b in backups:
        print("  " + t("steam.backup", path=b))
