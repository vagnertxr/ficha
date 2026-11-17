"""Hub: controles físicos -> teclado virtual com teclas fixas de P1/P2.

O FBNeo identifica joystick por índice, que muda com a ordem de plugar (e o
wine ainda lê DS4 por hidraw, então dá pra esconder nada dele). Traduzindo tudo
para teclas fixas, a config do jogo nunca muda e quem decide quem é P1/P2 é o hub.
"""

import collections
import errno
import os
import select
import threading
import time

from . import linux_input as li
from .games import DEFAULT_GAME, GAMES, VPAD_OUT
from .profiles import (ALL_KEYS, DEFAULT_DIRECTIONS, DIRECTION_SOURCES, KEYMAP, ProfileStore,
                       device_identity, layout_to_mapping, mapping_to_layout, model_key, positions)

COMBO_SWAP = (0.3, 1.5)   # START+COIN segurados por esse intervalo e soltos: troca de lado
COMBO_REMAP = 2.0         # START+COIN segurados por isso: entra no mapeamento
WIZARD_TIMEOUT = 45.0
SKIPPABLE = {"coin"}      # apertar START de novo pula

HAT_CODES = range(li.ABS_HAT0X, 0x18)

# Controles virtuais pro Flycast: layout de controle Xbox, ID próprio (pid.codes)
# pra dar pra esconder do Flycast todo o resto.
VPAD_NAMES = ("ficha P1", "ficha P2")
VPAD_BTNS = [0x130, 0x131, 0x133, 0x134, 0x136, 0x137, 0x13A, 0x13B, 0x13C, 0x13D, 0x13E]
VPAD_ABS = {li.ABS_X: (-32768, 32767), li.ABS_Y: (-32768, 32767), li.ABS_Z: (0, 255),
            li.ABS_RX: (-32768, 32767), li.ABS_RY: (-32768, 32767), li.ABS_RZ: (0, 255),
            li.ABS_HAT0X: (-1, 1), li.ABS_HAT0Y: (-1, 1)}
OWN_DEVICES = {"ficha teclado virtual"} | set(VPAD_NAMES)


def parse_source(src):
    parts = src.split(":")
    if parts[0] == "k":
        return ("k", int(parts[1]), 0)
    return ("a", int(parts[1]), 1 if parts[2] == "+" else -1)


class Pad:
    def __init__(self, dev, store):
        self.dev = dev
        self.key = os.path.basename(dev.path)
        self.pid, self.unique = device_identity(dev)
        self.model = model_key(dev)
        self.player = store.controller(self.pid).get("jogador", "")
        # Apelido: o nome que o driver dá nem sempre é o do aparelho (a Scoutbox
        # se apresenta como "Mad Catz Xbox 360 Controller").
        self.alias = store.controller(self.pid).get("apelido", "")
        self.mapping, self.kind = None, None   # o Hub resolve conforme jogo e jogador
        self.keys = dev.pressed_keys()
        self.abs = dev.current_abs()
        # Repouso de cada eixo = o valor no plug (ninguém pluga segurando nada).
        # Não dá pra supor pelo código: no DS4 via hid-playstation RX/RY são o
        # analógico direito (repouso no meio), mas em placas genéricas como a
        # Brook ("ZEROPLUS P4", hid-generic) RX/RY são L2/R2, com repouso em 0.
        self.rest = {}
        for code, info in dev.absinfo.items():
            self.rest[code] = 0 if code in HAT_CODES else info.value
        self.slot = None
        self.actions = set()
        self.wizard = None
        self.combo_since = None
        self.combo_fired = False
        self.resync = False
        self._compile()

    def _compile(self):
        self._sources = {a: [parse_source(s) for s in srcs] for a, srcs in (self.mapping or {}).items()}

    def set_mapping(self, mapping, kind):
        self.mapping, self.kind = mapping, kind
        self._compile()

    def active(self, kind, code, sign):
        if kind == "k":
            return code in self.keys
        info = self.dev.absinfo.get(code)
        if info is None or code not in self.abs:
            return False
        v = self.abs[code]
        if code in HAT_CODES:
            return v * sign > 0
        rest = self.rest[code]
        span = (info.max - rest) if sign > 0 else (rest - info.min)
        if span <= 0:
            return False
        return (v - rest) * sign > span * 0.5

    @property
    def name(self):
        return self.alias or self.dev.name

    def compute_actions(self):
        return {a for a, srcs in self._sources.items() if any(self.active(*s) for s in srcs)}

    def raw_buttons(self):
        """Fontes não-direcionais ativas agora (usado no mapeamento)."""
        out = ["k:%d" % c for c in sorted(self.keys) if "k:%d" % c not in DIRECTION_SOURCES]
        for code in self.dev.absinfo:
            if code in HAT_CODES or code in (li.ABS_X, li.ABS_Y):
                continue
            for sign, ch in ((1, "+"), (-1, "-")):
                if self.active("a", code, sign):
                    out.append("a:%d:%s" % (code, ch))
        return out


class Wizard:
    def __init__(self, game, wait_release):
        self.game = game
        # Opcionais vêm depois do START, que é o botão de pular.
        self.steps = ([b for b in game.button_ids if b not in game.optional] + ["start"]
                      + [b for b in game.button_ids if b in game.optional] + ["coin"])
        self.idx = 0
        self.captured = {}
        self.wait_release = wait_release   # aberto pelo combo: espera soltar START+COIN
        self.last_activity = time.monotonic()
        self.message = ""

    @property
    def step(self):
        return self.steps[self.idx]

    def feed(self, raw):
        """Retorna True quando terminou."""
        if self.wait_release:
            if not raw:
                self.wait_release = False
            return False
        if not raw:
            return False
        # DS4/sticks PS mandam L2/R2 como botão E eixo; o botão é mais confiável.
        src = raw[0]
        self.wait_release = True
        self.last_activity = time.monotonic()
        step = self.step
        if (step in SKIPPABLE or step in self.game.optional) and src == self.captured.get("start"):
            self.captured[step] = None
            self.message = "%s pulado" % self.game.label(step)
        elif src in self.captured.values():
            self.message = "Esse botão já é %s" % self.game.label(
                [a for a, s in self.captured.items() if s == src][0])
            return False
        else:
            self.captured[step] = src
            self.message = ""
        self.idx += 1
        return self.idx >= len(self.steps)

    def mapping(self):
        m = {d: list(s) for d, s in DEFAULT_DIRECTIONS.items()}
        for a, s in self.captured.items():
            m[a] = [s] if s else []
        return m


class Hub:
    def __init__(self, store=None, keyboard=True):
        self.store = store or ProfileStore()
        self.pads = {}
        self.slots = [None, None]
        self.held = [set(), set()]
        self.ignored = {}
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.version = 0
        self.events = collections.deque(maxlen=25)
        self.game = GAMES.get(self.store.data.get("ultimo_jogo")) or GAMES[DEFAULT_GAME]
        self.kb = li.UInput("ficha teclado virtual", ALL_KEYS) if keyboard else None
        # P1 criado antes do P2: eventN menor, então índice SDL 0 no Flycast.
        self.vpads = [li.UInput(n, VPAD_BTNS, VPAD_ABS, vendor=0x1209, product=0xF1C5)
                      for n in VPAD_NAMES] if keyboard else [None, None]
        self.running = False
        self._last_scan = 0
        # Só manda tecla/botão pro sistema com o jogo aberto: com ele fechado, o
        # teclado virtual digitaria na janela em foco. O painel liga/desliga.
        self.output_enabled = True

    # --- infraestrutura -------------------------------------------------------

    def log(self, msg):
        self.events.appendleft((time.strftime("%H:%M:%S"), msg))
        self.bump()

    def bump(self):
        with self.changed:
            self.version += 1
            self.changed.notify_all()

    def label(self, pad):
        return pad.player or pad.name

    def rename(self, pad, alias):
        with self.lock:
            pad.alias = " ".join(alias.split())[:40]
            self.store.controller(pad.pid)["apelido"] = pad.alias
            self.store.save()
            self.log("%s agora se chama %s" % (pad.dev.name, pad.name))

    def scan(self):
        try:
            names = [n for n in os.listdir("/dev/input") if n.startswith("event")]
        except OSError:
            return
        present = set()
        for n in names:
            path = "/dev/input/" + n
            present.add(path)
            if n in self.pads:
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            stamp = (st.st_ino, st.st_ctime_ns)
            if self.ignored.get(path) == stamp:
                continue
            try:
                dev = li.InputDevice(path)
            except OSError:
                # Sem permissão (teclado, mouse...) ou sumiu no meio. Joysticks
                # ganham ACL pelo uaccess do systemd; se aparecer depois, o stamp muda.
                self.ignored[path] = stamp
                continue
            # Ignora os próprios virtuais e o controle virtual do Steam Input
            # (28de:11ff), que espelha um controle físico que já estamos lendo.
            if not dev.is_gamepad or dev.name in OWN_DEVICES or (dev.vendor, dev.product) == (0x28DE, 0x11FF):
                dev.close()
                self.ignored[path] = stamp
                continue
            self.add_pad(dev)
        for path in list(self.ignored):
            if path not in present:
                del self.ignored[path]
        # Outro programa (a Steam, com o Steam Input) pode ter agarrado o
        # controle antes: aí os botões só vão pra ele. Tenta de novo até soltar.
        for pad in self.pads.values():
            if not pad.dev.grabbed:
                pad.dev.grab()
                if pad.dev.grabbed:
                    pad.keys, pad.abs = pad.dev.pressed_keys(), pad.dev.current_abs()
                    self.log("%s liberado: agora o ficha lê esse controle" % self.label(pad))

    def add_pad(self, dev):
        dev.grab()
        pad = Pad(dev, self.store)
        self.pads[pad.key] = pad
        ctrl = self.store.controller(pad.pid)
        ctrl["modelo"], ctrl["last_seen"] = dev.name, int(time.time())
        pad.set_mapping(*self.resolve(pad))
        if pad.player and self.store.player(pad.player) is None and pad.mapping:
            # Jogador sem perfil ainda (ex.: veio do perfis.json antigo): adota o layout atual.
            self._save_for_player(pad, pad.mapping)
            pad.kind = "player"
        self.store.save()
        who = self.label(pad)
        free = self.free_slot()
        if not dev.grabbed:
            self.log("%s: outro programa (a Steam?) está segurando esse controle" % who)
        if free is not None:
            self.assign(pad, free, quiet=True)
            self.log("%s conectou → P%d" % (who, free + 1))
        else:
            self.log("%s conectou (no banco: aperte START quando liberar)" % who)
        if pad.mapping is None:
            self.start_wizard(pad)
        return pad

    def remove_pad(self, pad):
        if pad.slot is not None:
            self._release_slot(pad.slot)
            self.slots[pad.slot] = None
        pad.dev.close()
        del self.pads[pad.key]
        self.log("%s desconectou" % self.label(pad))

    def free_slot(self):
        for i, s in enumerate(self.slots):
            if s is None:
                return i
        return None

    # --- saída ----------------------------------------------------------------

    def _emit(self, slot, desired):
        """Leva a saída do slot até 'desired': conjunto de alvos
        ("key", código) no teclado virtual, ou ("btn"/"axis"/"hat", ...) no controle virtual."""
        held = self.held[slot]
        if desired == held:
            return
        kb, pad = self.kb, self.vpads[slot]
        touched = set()
        for kind, code in sorted(held - desired) + sorted(desired - held):
            on = (kind, code) in desired
            if kind == "key" and kb:
                kb.emit(li.EV_KEY, code, int(on), syn=False)
                touched.add(kb)
            elif kind == "btn" and pad:
                pad.emit(li.EV_KEY, code, int(on), syn=False)
                touched.add(pad)
            elif kind == "axis" and pad:
                pad.emit(li.EV_ABS, code, 255 if on else 0, syn=False)
                touched.add(pad)
        if pad and any(k == "hat" for k, _ in held ^ desired):
            hx = (("hat", "right") in desired) - (("hat", "left") in desired)
            hy = (("hat", "down") in desired) - (("hat", "up") in desired)
            pad.emit(li.EV_ABS, li.ABS_HAT0X, hx, syn=False)
            pad.emit(li.EV_ABS, li.ABS_HAT0Y, hy, syn=False)
            touched.add(pad)
        for dev in touched:
            dev.emit(li.EV_SYN, li.SYN_REPORT, 0, syn=False)
        self.held[slot] = desired

    def _release_slot(self, slot):
        self._emit(slot, set())

    def _targets(self, slot, acts):
        game = self.game
        if game.emulator in ("flycast", "steam"):
            out = set()
            for a in acts:
                if a in ("up", "down", "left", "right"):
                    out.add(("hat", a))
                elif game.target(a, slot) in VPAD_OUT:
                    out.add(VPAD_OUT[game.target(a, slot)])
            return out
        km = KEYMAP[slot]
        slot_of = {b: "b%d" % (i + 1) for i, b in enumerate(game.button_ids)}
        return {("key", km[slot_of.get(a, a)][0]) for a in acts if slot_of.get(a, a) in km}

    def set_output(self, enabled):
        with self.lock:
            if enabled == self.output_enabled:
                return
            self.output_enabled = enabled
            for s in (0, 1):
                self._release_slot(s)
            for pad in self.pads.values():
                self._output(pad)

    def _output(self, pad):
        if pad.slot is None or pad.wizard is not None:
            return
        if not self.output_enabled:
            self._emit(pad.slot, set())
            return
        game = self.game
        acts = set()
        for a in pad.actions:
            acts.update(game.macros[a][1] if a in game.macros else (a,))
        # SOCD: esquerda+direita = neutro, cima+baixo = cima (padrão de torneio).
        if "left" in acts and "right" in acts:
            acts -= {"left", "right"}
        if "up" in acts and "down" in acts:
            acts.discard("down")
        self._emit(pad.slot, self._targets(pad.slot, acts))

    # --- ações (chamadas pelo loop e pelo painel) -----------------------------

    def assign(self, pad, slot, quiet=False):
        with self.lock:
            if pad.slot == slot:
                return
            if pad.slot is not None:
                self._release_slot(pad.slot)
                self.slots[pad.slot] = None
            if slot is not None:
                other = self.slots[slot]
                if other is not None:
                    self._release_slot(slot)
                    other_pad = self.pads[other]
                    other_pad.slot = None
                    # Trocando de lugar com alguém: o outro vai pro lado que ficou livre.
                    free = self.free_slot()
                    if free is not None and free != slot:
                        self.slots[free] = other_pad.key
                        other_pad.slot = free
                        self._output(other_pad)
                self.slots[slot] = pad.key
            pad.slot = slot
            self._output(pad)
            if not quiet:
                self.log("%s → %s" % (self.label(pad), "P%d" % (slot + 1) if slot is not None else "banco"))
            self.bump()

    def swap(self):
        with self.lock:
            for s in (0, 1):
                self._release_slot(s)
            self.slots.reverse()
            for s, key in enumerate(self.slots):
                if key is not None:
                    self.pads[key].slot = s
                    self._output(self.pads[key])
            names = ["%s=P%d" % (self.label(self.pads[k]), i + 1) for i, k in enumerate(self.slots) if k]
            self.log("Trocou de lado: " + (", ".join(names) or "ninguém"))

    def start_wizard(self, pad):
        with self.lock:
            if pad.slot is not None:
                self._release_slot(pad.slot)
            pad.wizard = Wizard(self.game, wait_release=bool(pad.raw_buttons()))
            self.log("Mapeando %s no %s: aperte %s" % (self.label(pad), self.game.short,
                                                       self.game.label(pad.wizard.step)))

    def cancel_wizard(self, pad):
        with self.lock:
            if pad.wizard is None:
                return
            pad.wizard = None
            self.log("Mapeamento de %s cancelado" % self.label(pad))

    # --- perfis: controle x pessoa x jogo --------------------------------------

    def resolve(self, pad):
        """Mapeamento pro jogo atual: layout da pessoa > do controle > padrão do jogo."""
        g = self.game
        if pad.player:
            pg = self.store.player_game(pad.player, g.id)
            if pg:
                if pg.get("layout"):
                    m = layout_to_mapping(pg["layout"], pad.dev)
                    if m:
                        return m, "player"
                if pg["modelos"].get(pad.model):
                    return pg["modelos"][pad.model], "player"
        saved = self.store.controller(pad.pid)["jogos"].get(g.id)
        if saved and saved.get("mapping"):
            return saved["mapping"], "custom"
        m = layout_to_mapping(g.layout, pad.dev)
        return m, ("default" if m else None)

    def _save_for_player(self, pad, mapping):
        """Guarda o mapeamento na pessoa: por posição (vale em qualquer controle
        posicional) e cru pro modelo (pra Pico em DInput e afins)."""
        pg = self.store.player_game(pad.player, self.game.id, create=True)
        layout = mapping_to_layout(mapping, pad.dev)
        if layout:
            pg["layout"] = layout
        pg["modelos"][pad.model] = mapping

    def _apply(self, pad):
        if pad.slot is not None:
            self._release_slot(pad.slot)
        pad.wizard = None
        pad.set_mapping(*self.resolve(pad))
        pad.actions = pad.compute_actions() if pad.mapping else set()
        if pad.mapping is None:
            self.start_wizard(pad)
        else:
            self._output(pad)

    def set_player(self, pad, name):
        with self.lock:
            name = " ".join(name.split())[:40]
            pad.player = name
            self.store.controller(pad.pid)["jogador"] = name
            if not name:
                self.log("%s sem jogador" % pad.name)
            else:
                pg = self.store.player_game(name, self.game.id)
                knows = pg and ((pg.get("layout") and positions(pad.dev) is not None)
                                or pg["modelos"].get(pad.model))
                if knows:
                    self._apply(pad)
                    self.log("%s pegou o %s: layout dele(a) no %s" % (name, pad.name, self.game.short))
                else:
                    # Pessoa nova (ou sem nada pra esse jogo): o layout atual vira o dela.
                    if pad.mapping:
                        self._save_for_player(pad, pad.mapping)
                        pad.kind = "player"
                    self.log("%s: layout salvo pro %s" % (name, self.game.short))
                self.store.touch_player(name)
            self.store.save()
            self.bump()

    def reset_mapping(self, pad):
        with self.lock:
            self.store.controller(pad.pid)["jogos"].pop(self.game.id, None)
            if pad.player:
                pg = self.store.player_game(pad.player, self.game.id, create=True)
                pg["layout"] = dict(self.game.layout)
                pg["modelos"].pop(pad.model, None)
            self.store.save()
            self._apply(pad)
            self.log("%s voltou pro layout padrão do %s" % (self.label(pad), self.game.short))

    def set_game(self, game_id):
        with self.lock:
            if game_id not in GAMES or game_id == self.game.id:
                return
            self.game = GAMES[game_id]
            self.store.data["ultimo_jogo"] = game_id
            self.store.save()
            for pad in self.pads.values():
                self._apply(pad)
            self.log("Jogo: %s" % self.game.title)

    # --- loop de input --------------------------------------------------------

    def _frame(self, pad, now):
        if pad.resync:
            pad.keys = pad.dev.pressed_keys()
            pad.abs = pad.dev.current_abs()
            pad.resync = False
        if pad.wizard is not None:
            w = pad.wizard
            before = w.idx
            if w.feed(pad.raw_buttons()):
                pad.wizard = None
                mapping = w.mapping()
                # O wizard não pergunta macros (3 socos...): herda do padrão do jogo se não colidir.
                used = {src for srcs in mapping.values() for src in srcs}
                for a, srcs in (layout_to_mapping(self.game.layout, pad.dev) or {}).items():
                    if a in self.game.macros and not used & set(srcs):
                        mapping[a] = srcs
                self.store.controller(pad.pid)["jogos"][self.game.id] = {"mapping": mapping}
                if pad.player:
                    self._save_for_player(pad, mapping)
                self.store.save()
                pad.set_mapping(mapping, "player" if pad.player else "custom")
                pad.actions = pad.compute_actions()
                self.log("%s mapeado!" % self.label(pad))
                self._output(pad)
            elif w.idx != before or w.message:
                self.bump()
            return
        prev = pad.actions
        pad.actions = pad.compute_actions()
        if pad.actions == prev:
            return
        combo = "start" in pad.actions and "coin" in pad.actions
        if combo and pad.combo_since is None:
            pad.combo_since, pad.combo_fired = now, False
        elif not combo and pad.combo_since is not None:
            held = now - pad.combo_since
            pad.combo_since = None
            if not pad.combo_fired and COMBO_SWAP[0] <= held < COMBO_SWAP[1] and pad.slot is not None:
                self.swap()
        if pad.slot is None and "start" in pad.actions and "start" not in prev:
            free = self.free_slot()
            if free is not None:
                self.assign(pad, free)
        self._output(pad)
        self.bump()

    def _tick(self, now):
        for pad in list(self.pads.values()):
            if pad.combo_since is not None and not pad.combo_fired and now - pad.combo_since >= COMBO_REMAP:
                pad.combo_fired = True
                self.start_wizard(pad)
            if pad.wizard is not None and now - pad.wizard.last_activity > WIZARD_TIMEOUT:
                self.cancel_wizard(pad)

    def step(self, timeout=0.5):
        """Uma iteração do loop. Separado de run() pra dar pra testar."""
        now = time.monotonic()
        if now - self._last_scan > 1.0:
            with self.lock:
                self.scan()
            self._last_scan = now
        fds = {p.dev.fd: p for p in self.pads.values()}
        busy = any(p.combo_since is not None or p.wizard is not None for p in self.pads.values())
        try:
            ready, _, _ = select.select(list(fds), [], [], min(timeout, 0.05) if busy else timeout)
        except (OSError, ValueError):
            ready = []
        with self.lock:
            now = time.monotonic()
            for fd in ready:
                pad = fds[fd]
                if pad.key not in self.pads:
                    continue
                try:
                    events = pad.dev.read()
                except OSError as e:
                    if e.errno in (errno.ENODEV, errno.EBADF, errno.EIO):
                        self.remove_pad(pad)
                        continue
                    raise
                for type_, code, value in events:
                    if type_ == li.EV_KEY:
                        if value:
                            pad.keys.add(code)
                        else:
                            pad.keys.discard(code)
                    elif type_ == li.EV_ABS:
                        pad.abs[code] = value
                    elif type_ == li.EV_SYN:
                        if code == li.SYN_DROPPED:
                            pad.resync = True
                        elif code == li.SYN_REPORT:
                            self._frame(pad, now)
            self._tick(now)

    def run(self):
        self.running = True
        while self.running:
            self.step()

    def close(self):
        self.running = False
        with self.lock:
            for s in (0, 1):
                self._release_slot(s)
            for pad in list(self.pads.values()):
                pad.dev.close()
            self.pads.clear()
            for dev in [self.kb] + self.vpads:
                if dev:
                    dev.close()
            self.kb, self.vpads = None, [None, None]

    # --- painel ---------------------------------------------------------------

    def snapshot(self):
        with self.lock:
            pads = []
            for pad in sorted(self.pads.values(), key=lambda p: (p.slot is None, p.slot or 0, p.key)):
                w = pad.wizard
                pads.append({
                    "key": pad.key, "name": pad.name, "model": pad.dev.name, "player": pad.player,
                    "unique": pad.unique, "kind": pad.kind, "slot": pad.slot, "grabbed": pad.dev.grabbed,
                    "driver": pad.dev.driver, "vidpid": "%04x:%04x" % (pad.dev.vendor, pad.dev.product),
                    "actions": sorted(pad.actions),
                    "wizard": None if w is None else {
                        "step": w.step, "label": w.game.label(w.step), "idx": w.idx,
                        "total": len(w.steps), "steps": w.steps, "message": w.message,
                        "skippable": w.step in SKIPPABLE or w.step in w.game.optional,
                    },
                })
            return {"slots": list(self.slots), "pads": pads, "players": self.store.players(),
                    "game": self.game.to_json(), "games": [g.to_json() for g in GAMES.values()],
                    "events": list(self.events), "version": self.version}
