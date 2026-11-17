"""Perfis: identidade dos controles, posições físicas e persistência.

Uma "fonte" é uma entrada física crua, serializada como string:
  "k:<código>"          botão (EV_KEY)
  "a:<código>:+" / "-"  eixo passando de 50% pra um lado (gatilho, analógico, hat)

O layout de uma pessoa é guardado por posição física ("soco fraco no botão da
esquerda"), que vale em qualquer controle com driver posicional. Para controles
sem posição confiável (Pico em DInput, encoders genéricos) guarda o mapeamento
cru daquela pessoa por modelo.
"""

import json
import os
import tempfile
import time

from . import linux_input as li

DIRECTIONS = ["up", "down", "left", "right"]

# Direcional sempre aceito, venha de onde vier: hat (D-pad do xpad/DS4/GP2040),
# analógico esquerdo, ou D-pad reportado como botões.
DEFAULT_DIRECTIONS = {
    "up": ["a:%d:-" % li.ABS_HAT0Y, "a:%d:-" % li.ABS_Y, "k:%d" % li.BTN_DPAD_UP],
    "down": ["a:%d:+" % li.ABS_HAT0Y, "a:%d:+" % li.ABS_Y, "k:%d" % li.BTN_DPAD_DOWN],
    "left": ["a:%d:-" % li.ABS_HAT0X, "a:%d:-" % li.ABS_X, "k:%d" % li.BTN_DPAD_LEFT],
    "right": ["a:%d:+" % li.ABS_HAT0X, "a:%d:+" % li.ABS_X, "k:%d" % li.BTN_DPAD_RIGHT],
}
DIRECTION_SOURCES = {s for v in DEFAULT_DIRECTIONS.values() for s in v}

# Drivers em que BTN_SOUTH/EAST/... têm significado posicional confiável.
# O xpad é a exceção histórica: reporta o X do Xbox (posição oeste) como BTN_X,
# que tem o mesmo valor de BTN_NORTH. A família PlayStation segue a norma.
XPAD_DRIVERS = {"xpad", "xone"}
POSITIONAL_DRIVERS = XPAD_DRIVERS | {"playstation", "sony", "xpadneo", "hid-microsoft", "microsoft"}
SYSTEM_LAYOUT = {"start": "start", "coin": "select"}

# Teclado virtual: P1 e P2 em blocos que não colidem com atalhos do FBNeo (F1-F12,
# Esc, Tab, Enter). Para letras/números o código do Linux é igual ao DIK do DirectInput.
# b1..b6 são os botões do jogo na ordem em que o jogo os define.
KEYMAP = [
    {"up": (17, 0x11), "down": (31, 0x1F), "left": (30, 0x1E), "right": (32, 0x20),      # W S A D
     "b1": (22, 0x16), "b2": (23, 0x17), "b3": (24, 0x18),                                # U I O
     "b4": (36, 0x24), "b5": (37, 0x25), "b6": (38, 0x26),                                # J K L
     "start": (2, 0x02), "coin": (6, 0x06)},                                              # 1 5
    {"up": (103, 0xC8), "down": (108, 0xD0), "left": (105, 0xCB), "right": (106, 0xCD),  # setas
     "b1": (44, 0x2C), "b2": (45, 0x2D), "b3": (46, 0x2E),                                # Z X C
     "b4": (47, 0x2F), "b5": (48, 0x30), "b6": (49, 0x31),                                # V B N
     "start": (3, 0x03), "coin": (7, 0x07)},                                              # 2 6
]
ALL_KEYS = sorted({k for slot in KEYMAP for k, _ in slot.values()})


def device_identity(dev):
    """Chave estável para lembrar do controle.

    DS4 expõe o MAC em uniq; muitos controles USB têm número de série. Sem
    nenhum dos dois só dá para reconhecer o modelo.
    """
    if dev.uniq:
        return "uniq:%s" % dev.uniq.lower(), True
    if dev.serial:
        return "serial:%04x:%04x:%s" % (dev.vendor, dev.product, dev.serial), True
    return "model:" + model_key(dev), False


def model_key(dev):
    return "%04x:%04x:%s" % (dev.vendor, dev.product, dev.name)


def positions(dev):
    """Posição física -> fonte crua, ou None se o driver não for confiável."""
    if dev.driver not in POSITIONAL_DRIVERS or not (dev.has_key(li.BTN_SOUTH) and dev.has_key(li.BTN_EAST)):
        return None
    if dev.driver in XPAD_DRIVERS:
        west, north = li.BTN_NORTH, li.BTN_WEST
    else:
        west, north = li.BTN_WEST, li.BTN_NORTH

    def trigger(btn, axis):
        if dev.has_key(btn):
            return "k:%d" % btn
        if axis in dev.absinfo:
            return "a:%d:+" % axis
        return None

    pos = {"west": "k:%d" % west, "north": "k:%d" % north, "south": "k:%d" % li.BTN_SOUTH,
           "east": "k:%d" % li.BTN_EAST, "r1": "k:%d" % li.BTN_TR, "l1": "k:%d" % li.BTN_TL,
           "r2": trigger(li.BTN_TR2, li.ABS_RZ), "l2": trigger(li.BTN_TL2, li.ABS_Z),
           "start": "k:%d" % li.BTN_START, "select": "k:%d" % li.BTN_SELECT,
           "l3": "k:%d" % li.BTN_THUMBL, "r3": "k:%d" % li.BTN_THUMBR}
    return {p: s for p, s in pos.items() if s and (s[0] == "a" or dev.has_key(int(s.split(":")[1])))}


def layout_to_mapping(layout, dev):
    pos = positions(dev)
    if pos is None:
        return None
    m = {d: list(s) for d, s in DEFAULT_DIRECTIONS.items()}
    for action, p in dict(SYSTEM_LAYOUT, **layout).items():
        m[action] = [pos[p]] if p in pos else []
    return m


def mapping_to_layout(mapping, dev):
    """Inverso: só dá certo se todos os botões caírem em posições conhecidas."""
    pos = positions(dev)
    if pos is None:
        return None
    where = {s: p for p, s in pos.items()}
    layout = {}
    for action, srcs in mapping.items():
        if action in DIRECTIONS or action in SYSTEM_LAYOUT or not srcs:
            continue
        if srcs[0] not in where:
            return None
        layout[action] = where[srcs[0]]
    return layout


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "ficha")


class ProfileStore:
    """perfis.json:
      controles: {id: {modelo, jogador, jogos: {jogo: {mapping}}}}
      jogadores: {nome: {jogos: {jogo: {layout, modelos: {modelo: mapping}}}}}
    """

    def __init__(self, path=None):
        self.path = path or os.path.join(config_dir(), "perfis.json")
        try:
            with open(self.path) as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        if "controles" not in data:
            data = self._migrate_v1(data)
        self.data = data

    @staticmethod
    def _migrate_v1(old):
        """v1 era {id: {owner, model, mapping}}, só 3rd Strike."""
        data = {"versao": 2, "controles": {}, "jogadores": {}, "ultimo_jogo": None}
        for pid, e in old.items():
            c = {"modelo": e.get("model", ""), "jogador": e.get("owner", ""), "jogos": {}}
            if e.get("mapping"):
                c["jogos"]["sfiii3nr1"] = {"mapping": e["mapping"]}
            data["controles"][pid] = c
        return data

    def controller(self, pid):
        return self.data["controles"].setdefault(pid, {"modelo": "", "jogador": "", "jogos": {}})

    def player(self, name):
        return self.data["jogadores"].get(name)

    def player_game(self, name, game, create=False):
        if create:
            p = self.data["jogadores"].setdefault(name, {"jogos": {}})
            return p["jogos"].setdefault(game, {"layout": None, "modelos": {}})
        p = self.data["jogadores"].get(name)
        return p["jogos"].get(game) if p else None

    def players(self):
        return sorted(self.data["jogadores"], key=str.lower)

    def touch_player(self, name):
        self.data["jogadores"].setdefault(name, {"jogos": {}})["last_seen"] = int(time.time())

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
