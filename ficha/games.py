"""Jogos: um arquivo TOML por jogo, em ficha/games/ (embutidos) e em
<config>/games/ (do usuário; com o mesmo id, o do usuário vence).

Formato: veja docs/adding-a-game.md. Posições físicas usadas em [layout]
(valem igual em DS4, Xbox, arcade PS4/PS5 e Pico em XInput):
  west north r1 l1   (fileira de cima num arcade: □ △ R1 L1 / X Y RB LB)
  south east r2 l2   (fileira de baixo:           × ○ R2 L2 / A B RT LT)
  start select l3 r3
"""

import glob
import os
import sys
import tomllib

from . import config, i18n

BUILTIN_DIR = os.path.join(os.path.dirname(__file__), "games")
POSITIONS = {"west", "north", "south", "east", "r1", "l1", "r2", "l2", "start", "select", "l3", "r3"}
SYSTEM_LABELS = {"start": "START", "coin": "COIN / SELECT"}


class GameError(ValueError):
    pass


class Game:
    def __init__(self, data, source):
        self.source = source
        try:
            self.id = data["id"]
            self.title = data["title"]
            self.backend = dict(data["backend"])
            self.backend_type = self.backend["type"]
            raw_buttons = data["buttons"]
        except KeyError as e:
            raise GameError("%s: falta o campo %s" % (source, e))
        self.short = data.get("short", self.title)
        self.year = data.get("year")
        self.accent = data.get("accent", "#ffd34d")
        self.grid = data.get("grid") or [[b["id"] for b in raw_buttons]]
        self.layout = dict(data.get("layout", {}))
        self.macros = {k: (v.get("name", k), list(v["buttons"])) for k, v in data.get("macros", {}).items()}
        self.optional = set(data.get("optional", []))
        self.system = dict(data.get("system", {"start": "start"}))
        self.training = bool(data.get("training", False))
        self._names = {}
        self.buttons = []
        for b in raw_buttons:
            target = b.get("target")
            if isinstance(target, list):
                target = tuple(target)   # um alvo por lado: [P1, P2]
            self.buttons.append((b["id"], b.get("short", b["id"].upper()), b.get("name", b["id"]), target))
        self._validate()

    def _validate(self):
        ids = self.button_ids
        if len(set(ids)) != len(ids):
            raise GameError("%s: id de botão repetido" % self.source)
        known = set(ids) | set(self.macros)
        for action, pos in self.layout.items():
            if action not in known:
                raise GameError("%s: [layout] cita '%s', que não é botão nem macro" % (self.source, action))
            if pos not in POSITIONS:
                raise GameError("%s: posição '%s' desconhecida (use %s)" % (self.source, pos, ", ".join(sorted(POSITIONS))))
        for row in self.grid:
            for b in row:
                if b not in ids:
                    raise GameError("%s: grid cita '%s', que não é botão" % (self.source, b))
        for m, (_, parts) in self.macros.items():
            if set(parts) - set(ids):
                raise GameError("%s: macro '%s' usa botão inexistente" % (self.source, m))

    @property
    def button_ids(self):
        return [b[0] for b in self.buttons]

    @property
    def emulator(self):   # nome antigo, usado em alguns lugares
        return self.backend_type

    def label(self, action):
        for bid, _, name, _ in self.buttons:
            if bid == action:
                return i18n.pick(name)
        if action in self.macros:
            return i18n.pick(self.macros[action][0])
        if action in SYSTEM_LABELS:
            return SYSTEM_LABELS[action]
        return i18n.t("dir." + action) if action in ("up", "down", "left", "right") else action

    def target(self, action, slot=0):
        if action in self.system:
            t = self.system[action]
            return t[slot] if isinstance(t, list) else t
        for bid, _, _, target in self.buttons:
            if bid == action:
                return target[slot] if isinstance(target, tuple) else target
        return None

    def installed(self):
        from . import backends
        return backends.get(self.backend_type).installed(self)

    def art(self, suffix=""):
        name = "%s%s.jpg" % (self.id, suffix)
        return "/art/" + name if os.path.exists(os.path.join(config.config_dir(), "art", name)) else None

    def to_json(self):
        from . import backends
        return {"id": self.id, "title": self.title, "short": self.short, "installed": self.installed(),
                "training": self.training, "accent": self.accent, "year": self.year,
                "emulator": backends.get(self.backend_type).label(self),
                "art": self.art(), "backdrop": self.art("-bg") or self.art(),
                "buttons": [{"id": b[0], "short": b[1]} for b in self.buttons],
                "grid": self.grid, "macros": {k: v[1] for k, v in self.macros.items()}}


def load_all():
    from . import backends
    games = {}
    for folder in (BUILTIN_DIR, os.path.join(config.config_dir(), "games")):
        for path in sorted(glob.glob(os.path.join(folder, "*.toml"))):
            try:
                with open(path, "rb") as f:
                    game = Game(tomllib.load(f), path)
                backends.get(game.backend_type)   # backend existe?
            except (OSError, tomllib.TOMLDecodeError, GameError, KeyError) as e:
                print("ficha: ignorando jogo %s: %s" % (path, e), file=sys.stderr)
                continue
            games[game.id] = game
    return games


GAMES = load_all()
DEFAULT_GAME = "sfiii3nr1" if "sfiii3nr1" in GAMES else next(iter(GAMES), None)
