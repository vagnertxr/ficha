"""Configuração do usuário e onde ficam as coisas (Fightcade, Steam, artes, jogos).

config.toml (em ~/.config/ficha/ ou %APPDATA%\\ficha\\), tudo opcional:

    idioma = "pt"              # "pt" ou "en"; sem isso, segue o idioma do sistema
    porta = 7373
    lan = false                # painel acessível pela rede local
    [caminhos]
    fightcade = "/caminho/do/Fightcade"   # pasta de instalação (nativo) ou de dados (flatpak)
    steam = "/caminho/da/Steam"           # a pasta que tem steamapps/
"""

import os
import sys
import tomllib

DEFAULTS = {"idioma": None, "porta": 7373, "lan": False, "caminhos": {}}


def config_dir():
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ficha")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "ficha")


def load():
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    path = os.path.join(config_dir(), "config.toml")
    try:
        with open(path, "rb") as f:
            user = tomllib.load(f)
    except FileNotFoundError:
        return cfg
    except (OSError, tomllib.TOMLDecodeError) as e:
        print("ficha: ignorando %s (%s)" % (path, e), file=sys.stderr)
        return cfg
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


CONFIG = load()
HOME = os.path.expanduser("~")


# --- Fightcade -----------------------------------------------------------------

class Fightcade:
    """Onde o Fightcade guarda configs e ROMs, e como abrir um jogo.

    kind = "flatpak"  (com.fightcade.Fightcade; o caminho testado)
           "linux"    (instalação nativa com wine; não testado)
           "windows"  (não testado)
    """

    def __init__(self, kind, root):
        self.kind, self.root = kind, root
        if kind == "flatpak":
            self.fbneo_config = os.path.join(root, "config", "fcadefbneo")
            self.roms = {"fbneo": os.path.join(root, "ROMs", "fbneo"),
                         "flycast": os.path.join(root, "ROMs", "flycast")}
        else:
            emu = os.path.join(root, "emulator")
            self.fbneo_config = os.path.join(emu, "fbneo", "config")
            self.roms = {"fbneo": os.path.join(root, "ROMs", "FBNeo ROMs"),
                         "flycast": os.path.join(root, "ROMs", "Flycast ROMs")}
            self.emulator = emu

    @property
    def fbneo_games(self):
        return os.path.join(self.fbneo_config, "games")

    @property
    def fbneo_main_ini(self):
        name = "fcadefbneo.ini"
        return os.path.join(self.fbneo_config, name)


def fightcade():
    override = CONFIG["caminhos"].get("fightcade")
    flatpak = os.path.join(HOME, ".var", "app", "com.fightcade.Fightcade", "data")
    if override:
        kind = "flatpak" if override.rstrip("/").endswith("com.fightcade.Fightcade/data") else \
            ("windows" if sys.platform == "win32" else "linux")
        return Fightcade(kind, os.path.expanduser(override))
    if sys.platform == "win32":
        for c in (os.path.join(HOME, "Fightcade"), r"C:\Fightcade", r"C:\Program Files\Fightcade"):
            if os.path.isdir(c):
                return Fightcade("windows", c)
        return Fightcade("windows", os.path.join(HOME, "Fightcade"))
    if os.path.isdir(flatpak):
        return Fightcade("flatpak", flatpak)
    return Fightcade("linux", os.path.join(HOME, "Fightcade"))


# --- Steam ---------------------------------------------------------------------

class Steam:
    """kind = "flatpak" (com.valvesoftware.Steam; o caminho testado), "linux" ou "windows"."""

    def __init__(self, kind, root):
        self.kind, self.root = kind, root

    @property
    def common(self):
        return os.path.join(self.root, "steamapps", "common")

    @property
    def compatdata(self):
        return os.path.join(self.root, "steamapps", "compatdata")

    @property
    def home(self):
        """O $HOME que a Steam enxerga (no flatpak é a pasta do app)."""
        if self.kind == "flatpak":
            return os.path.join(HOME, ".var", "app", "com.valvesoftware.Steam")
        return HOME


def _windows_steam():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return winreg.QueryValueEx(k, "SteamPath")[0]
    except (ImportError, OSError):
        return r"C:\Program Files (x86)\Steam"


def steam():
    override = CONFIG["caminhos"].get("steam")
    flatpak = os.path.join(HOME, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam")
    if override:
        kind = "windows" if sys.platform == "win32" else ("flatpak" if "com.valvesoftware.Steam" in override else "linux")
        return Steam(kind, os.path.expanduser(override))
    if sys.platform == "win32":
        return Steam("windows", _windows_steam())
    if os.path.isdir(os.path.join(flatpak, "steamapps")):
        return Steam("flatpak", flatpak)
    for c in (os.path.join(HOME, ".local", "share", "Steam"), os.path.join(HOME, ".steam", "steam")):
        if os.path.isdir(os.path.join(c, "steamapps")):
            return Steam("linux", c)
    return Steam("linux", os.path.join(HOME, ".local", "share", "Steam"))
