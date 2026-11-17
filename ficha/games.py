"""Jogos suportados. Cada um tem seus botões, seus nomes no .ini do FBNeo e seu
layout padrão — nada genérico: jogo novo entra aqui, definido à mão.

Posições físicas (valem igual em DS4, Xbox, arcade PS4/PS5 e Pico em XInput):
  west north r1 l1   (fileira de cima num arcade: □ △ R1 L1 / X Y RB LB)
  south east r2 l2   (fileira de baixo:           × ○ R2 L2 / A B RT LT)
  start select l3 r3
"""

import os

ART_DIR = os.path.join(os.path.dirname(__file__), "art")
EMULATOR_LABEL = {"fbneo": "Fightcade · FBNeo", "flycast": "Fightcade · Flycast", "steam": "Steam · Proton"}
ROMS = os.path.expanduser("~/.var/app/com.fightcade.Fightcade/data/ROMs")
STEAM_COMMON = os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common")

# Saídas do controle virtual (Flycast): botão Xbox -> (tipo, código). O Flycast
# trata o virtual como controle Xbox: X->X, Y->Y, A->A, B->B, LT->L, RT->R
# (conferido no MvC2 com captura de tela).
VPAD_OUT = {"a": ("btn", 0x130), "b": ("btn", 0x131), "x": ("btn", 0x133), "y": ("btn", 0x134),
            "lb": ("btn", 0x136), "rb": ("btn", 0x137), "back": ("btn", 0x13A), "start": ("btn", 0x13B),
            "lt": ("axis", 0x02), "rt": ("axis", 0x05)}


class Game:
    def __init__(self, id, title, short, emulator, zips, buttons, grid, layout, macros=None, training=True,
                 optional=(), system=None, steam_appid=None, process=None, accent="#ffd34d", year=None):
        self.id = id
        self.title = title
        self.short = short
        self.emulator = emulator    # "fbneo" (teclado virtual) ou "flycast" (controles virtuais)
        self.zips = zips            # arquivos em ROMs/<emulador>; qualquer um presente = instalado
        # [(id, sigla, nome em pt, alvo)]: alvo é o nome do input no .ini (FBNeo)
        # ou o botão do controle virtual (Flycast/Steam, ver VPAD_OUT). Pode ser
        # um par (alvo no P1, alvo no P2) quando o jogo configura cada lado diferente.
        self.buttons = buttons
        self.grid = grid            # fileiras de ids, como aparecem no painel
        self.layout = layout        # id -> posição física
        self.macros = macros or {}  # id -> (nome, [ids])
        self.training = training
        self.optional = set(optional)          # botões que o mapeamento deixa pular
        self.system = system or {"start": "start"}   # start/coin -> botão do controle virtual
        self.steam_appid = steam_appid
        self.process = process
        self.accent = accent        # cor de destaque no painel
        self.year = year

    @property
    def button_ids(self):
        return [b[0] for b in self.buttons]

    def label(self, action):
        for bid, _, name, _ in self.buttons:
            if bid == action:
                return name
        if action in self.macros:
            return self.macros[action][0]
        return {"start": "START", "coin": "COIN / SELECT", "up": "Cima", "down": "Baixo",
                "left": "Esquerda", "right": "Direita"}.get(action, action)

    def target(self, action, slot=0):
        if action in self.system:
            return self.system[action]
        for bid, _, _, target in self.buttons:
            if bid == action:
                return target[slot] if isinstance(target, tuple) else target
        return None

    def installed(self):
        base = STEAM_COMMON if self.emulator == "steam" else os.path.join(ROMS, self.emulator)
        return any(os.path.exists(os.path.join(base, z)) for z in self.zips)

    def art(self, suffix=""):
        name = "%s%s.jpg" % (self.id, suffix)
        return "/art/" + name if os.path.exists(os.path.join(ART_DIR, name)) else None

    def to_json(self):
        return {"id": self.id, "title": self.title, "short": self.short, "installed": self.installed(),
                "training": self.training, "accent": self.accent, "year": self.year,
                "emulator": EMULATOR_LABEL.get(self.emulator, self.emulator),
                "art": self.art(), "backdrop": self.art("-bg") or self.art(),
                "buttons": [{"id": b[0], "short": b[1]} for b in self.buttons],
                "grid": self.grid, "macros": {k: v[1] for k, v in self.macros.items()}}


GAMES = {g.id: g for g in [
    Game(
        "sfiii3nr1", "Street Fighter III: 3rd Strike", "3rd Strike", "fbneo", accent="#ff9f1a", year=1999,
        zips=["sfiii3nr1.zip", "sfiii3.zip"],
        buttons=[
            ("lp", "LP", "Soco fraco", "Weak Punch"),
            ("mp", "MP", "Soco médio", "Medium Punch"),
            ("hp", "HP", "Soco forte", "Strong Punch"),
            ("lk", "LK", "Chute fraco", "Weak Kick"),
            ("mk", "MK", "Chute médio", "Medium Kick"),
            ("hk", "HK", "Chute forte", "Strong Kick"),
        ],
        grid=[["lp", "mp", "hp"], ["lk", "mk", "hk"]],
        layout={"lp": "west", "mp": "north", "hp": "r1", "lk": "south", "mk": "east", "hk": "r2",
                "3p": "l1", "3k": "l2"},
        macros={"3p": ("3 socos", ["lp", "mp", "hp"]), "3k": ("3 chutes", ["lk", "mk", "hk"])},
    ),
    # Versão Dreamcast (o .cdi do Vagner). Layout do gabinete: LP HP A1 em cima, LK HK A2 embaixo.
    Game(
        "mvc2", "Marvel vs. Capcom 2", "MvC2", "flycast", accent="#a274ff", year=2000,
        zips=["Marvel vs. Capcom 2.cdi", "Marvel vs. Capcom 2 (USA).chd"],
        buttons=[
            ("lp", "LP", "Soco fraco", "x"),
            ("hp", "HP", "Soco forte", "y"),
            ("a1", "A1", "Parceiro A", "lt"),
            ("lk", "LK", "Chute fraco", "a"),
            ("hk", "HK", "Chute forte", "b"),
            ("a2", "A2", "Parceiro B", "rt"),
        ],
        grid=[["lp", "hp", "a1"], ["lk", "hk", "a2"]],
        layout={"lp": "west", "hp": "north", "a1": "r1", "lk": "south", "hk": "east", "a2": "r2"},
        training=False,
    ),
    # Steam + Proton. Os alvos seguem o "Controller Settings" do jogo, em MODE
    # CONTROLLER nos dois lados (conferido na tela em 30/10/2026). Se alguém
    # mudar a config dentro do jogo, atualizar aqui.
    # Layout de gabinete: P S HS em cima, K D embaixo.
    Game(
        "ggxxacpr", "Guilty Gear XX Accent Core Plus R", "GG +R", "steam", accent="#ff3d4a", year=2012,
        zips=["Guilty Gear XX Accent Core Plus R/GGXXACPR_Win.exe"],
        buttons=[
            ("p", "P", "Punch", "x"),
            ("s", "S", "Slash", "y"),
            ("hs", "HS", "Heavy Slash", "b"),
            ("k", "K", "Kick", "a"),
            ("d", "D", "Dust", "rb"),
            ("respect", "R", "Respect (provocação)", "rt"),
        ],
        grid=[["p", "s", "hs"], ["k", "d", "respect"]],
        layout={"p": "west", "s": "north", "hs": "r1", "k": "south", "d": "east", "respect": "l1",
                "rc": "r2", "fd": "l2"},
        macros={"rc": ("Roman Cancel", ["p", "k", "s"]), "fd": ("Faultless Defense", ["p", "k"])},
        optional=["respect"],
        system={"start": "start", "coin": "back"},   # BACK = Reset no treino
        training=False, steam_appid=348550, process="GGXXACPR_Win.exe",
    ),
]}

DEFAULT_GAME = "sfiii3nr1"
