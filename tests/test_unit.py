"""Testes sem dispositivos de verdade: rodam em qualquer sistema (CI Linux e Windows).

    python -m unittest tests/test_unit.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ficha import backends, codes as ev, games, i18n, profiles  # noqa: E402
from ficha.backends import fbneo_fightcade, steam_setup, vdf  # noqa: E402
from ficha.codes import AbsInfo  # noqa: E402
from ficha.fileio import read_bytes, read_text  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


# --- dublês -------------------------------------------------------------------

class FakeDevice:
    """Imita a interface de platform.linux.InputDevice."""

    def __init__(self, key, name="Fake Pad", driver="playstation", keys=None, absinfo=None,
                 vendor=0x054C, product=0x09CC, uniq="", serial=""):
        self.key, self.path, self.name, self.driver = key, "/fake/" + key, name, driver
        self.vendor, self.product, self.uniq, self.serial = vendor, product, uniq, serial
        self._keys = set(keys if keys is not None else range(0x130, 0x13F))
        self.absinfo = absinfo if absinfo is not None else {
            ev.ABS_X: AbsInfo(128, 0, 255), ev.ABS_Y: AbsInfo(128, 0, 255),
            ev.ABS_HAT0X: AbsInfo(0, -1, 1), ev.ABS_HAT0Y: AbsInfo(0, -1, 1)}
        self.queue, self.grabbed, self.closed = [], False, False

    def has_key(self, code):
        return code in self._keys

    def pressed_keys(self):
        return set()

    def current_abs(self):
        return {c: i.value for c, i in self.absinfo.items()}

    def grab(self):
        self.grabbed = True

    def press(self, code, value=1):
        self.queue += [(ev.EV_KEY, code, value), (ev.EV_SYN, ev.SYN_REPORT, 0)]

    def axis(self, code, value):
        self.queue += [(ev.EV_ABS, code, value), (ev.EV_SYN, ev.SYN_REPORT, 0)]

    def read(self):
        out, self.queue = self.queue, []
        return out

    def close(self):
        self.closed = True


class FakeOut:
    def __init__(self):
        self.down, self.abs = set(), {}

    def emit(self, type_, code, value, syn=True):
        if type_ == ev.EV_KEY:
            (self.down.add if value else self.down.discard)(code)
        elif type_ == ev.EV_ABS:
            self.abs[code] = value

    def close(self):
        pass


class FakePlatform:
    name, trigger_max = "fake", 255

    def __init__(self):
        self.new = []

    def make_keyboard(self, keys):
        return FakeOut()

    def make_vpads(self):
        return [FakeOut(), FakeOut()]

    def discover(self, known):
        out, self.new = self.new, []
        return out

    def wait(self, devices, timeout):
        return [d for d in devices if d.queue]


def make_hub(tmp):
    from ficha.core import Hub
    store = profiles.ProfileStore(os.path.join(tmp, "perfis.json"))
    plat = FakePlatform()
    hub = Hub(store=store, plat=plat)
    hub.set_game("sfiii3nr1")
    return hub, plat


# --- testes -------------------------------------------------------------------

class TestGames(unittest.TestCase):
    def test_builtin_games_load(self):
        self.assertIn("sfiii3nr1", games.GAMES)
        for g in games.GAMES.values():
            self.assertTrue(g.buttons)
            backends.get(g.backend_type)
            for row in g.grid:
                self.assertTrue(set(row) <= set(g.button_ids))

    def test_doc_examples_are_valid(self):
        import glob, tomllib
        examples = glob.glob(os.path.join(os.path.dirname(__file__), "..", "docs", "examples", "*.toml"))
        self.assertTrue(examples)
        for path in examples:
            with open(path, "rb") as f:
                g = games.Game(tomllib.load(f), path)
            backends.get(g.backend_type)

    def test_key_after_buttons_is_an_error(self):
        data = {"id": "x", "title": "X", "backend": {"type": "gamepad"},
                "buttons": [{"id": "a", "target": "a", "grid": [["a"]]}]}
        with self.assertRaises(games.GameError):
            games.Game(data, "teste.toml")

    def test_bad_layout_position(self):
        data = {"id": "x", "title": "X", "backend": {"type": "gamepad"},
                "buttons": [{"id": "a", "target": "a"}], "layout": {"a": "lado"}}
        with self.assertRaises(games.GameError):
            games.Game(data, "teste.toml")

    def test_bilingual_names(self):
        g = games.GAMES["sfiii3nr1"]
        i18n.set_lang("en")
        self.assertEqual(g.label("lp"), "Light Punch")
        i18n.set_lang("pt")
        self.assertEqual(g.label("lp"), "Soco fraco")


class TestI18n(unittest.TestCase):
    def test_same_keys(self):
        self.assertEqual(set(i18n.table("pt")), set(i18n.table("en")))

    def test_format_and_fallback(self):
        i18n.set_lang("pt")
        self.assertEqual(i18n.t("log.mapped", pad="X"), "X mapeado!")
        self.assertEqual(i18n.t("chave.inexistente"), "chave.inexistente")


class TestProfiles(unittest.TestCase):
    def test_xpad_vs_playstation_positions(self):
        xbox = FakeDevice("e1", driver="xpad")
        ds4 = FakeDevice("e2", driver="playstation")
        self.assertEqual(profiles.positions(xbox)["west"], "k:%d" % ev.BTN_NORTH)   # X do Xbox
        self.assertEqual(profiles.positions(ds4)["west"], "k:%d" % ev.BTN_WEST)     # quadrado

    def test_generic_has_no_positions(self):
        self.assertIsNone(profiles.positions(FakeDevice("e3", driver="hid-generic")))

    def test_layout_roundtrip(self):
        dev = FakeDevice("e4", driver="playstation")
        layout = games.GAMES["sfiii3nr1"].layout
        mapping = profiles.layout_to_mapping(layout, dev)
        self.assertEqual(profiles.mapping_to_layout(mapping, dev), layout)


class TestFBNeoIni(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        games_dir = os.path.join(self.tmp, "games")
        os.makedirs(games_dir)
        shutil.copy(os.path.join(FIX, "sfiii3nr1.ini"), games_dir)
        where = mock.Mock(fbneo_games=games_dir)
        self.patch = mock.patch.object(fbneo_fightcade.fightcade, "where", return_value=where)
        self.patch.start()
        self.game = games.GAMES["sfiii3nr1"]
        self.path = os.path.join(games_dir, "sfiii3nr1.ini")

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp)

    def test_install_keeps_crlf_and_is_idempotent(self):
        self.assertTrue(fbneo_fightcade.check(self.game))
        fbneo_fightcade.install(self.game)
        self.assertEqual(fbneo_fightcade.check(self.game), [])
        raw = read_bytes(self.path)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))      # só \r\n
        self.assertIn(b'"P1 Weak Punch"    switch 0x16', raw)   # U
        self.assertIn(b'"Reset"            switch 0x3D', raw)   # o resto intacto
        self.assertTrue(os.path.exists(self.path + ".antes-do-ficha"))
        fbneo_fightcade.install(self.game)
        self.assertEqual(read_bytes(self.path), raw)

    def test_restore(self):
        original = read_bytes(self.path)
        fbneo_fightcade.install(self.game)
        self.assertTrue(fbneo_fightcade.restore(self.game))
        self.assertEqual(read_bytes(self.path), original)


class TestVDF(unittest.TestCase):
    def test_roundtrip_and_escapes(self):
        for name in ("localconfig.vdf", "config.vdf"):
            text = read_text(os.path.join(FIX, name))
            self.assertEqual(vdf.dumps(vdf.loads(text)), text)
        tree = vdf.loads(read_text(os.path.join(FIX, "config.vdf")))
        steam = vdf.path(tree, ["InstallConfigStore", "Software", "Valve", "Steam"])
        self.assertEqual(vdf.get(steam, 'Name "com aspas"'), "C:\\caminho")

    def test_path_create_and_set(self):
        tree = []
        node = vdf.path(tree, ["a", "b"], create=True)
        self.assertIsNone(vdf.set(node, "k", "1"))
        self.assertEqual(vdf.set(node, "K", "2"), "1")   # sem diferenciar maiúsculas
        self.assertEqual(vdf.loads(vdf.dumps(tree)), tree)


class TestSteamSetup(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "userdata", "123", "config"))
        os.makedirs(os.path.join(self.root, "config"))
        shutil.copy(os.path.join(FIX, "localconfig.vdf"), os.path.join(self.root, "userdata", "123", "config"))
        shutil.copy(os.path.join(FIX, "config.vdf"), os.path.join(self.root, "config"))
        self.game = games.GAMES["ggxxacpr"]

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_plan_apply_and_nothing_left(self):
        changes = steam_setup.plan(self.game, self.root, proton="proton_9", global_input=True, platform="linux")
        keys = {c[3] for c in changes}
        self.assertTrue({"UseSteamControllerConfig", "LaunchOptions", "name",
                         "SteamController_PSSupport", "SteamController_XBoxSupport"} <= keys)
        backups = steam_setup.apply(changes, stamp="teste")
        self.assertEqual(len(backups), 2)
        self.assertEqual(steam_setup.plan(self.game, self.root, proton="proton_9", global_input=True, platform="linux"), [])
        lc = vdf.loads(read_text(os.path.join(self.root, "userdata", "123", "config", "localconfig.vdf")))
        app = vdf.path(lc, ["UserLocalConfigStore", "Software", "Valve", "Steam", "apps", "348550"])
        self.assertEqual(vdf.get(app, "LastPlayed"), "1700000000")   # o resto intacto

    def test_windows_has_no_launch_options(self):
        changes = steam_setup.plan(self.game, self.root, platform="win32")
        self.assertNotIn("LaunchOptions", {c[3] for c in changes})


class TestTargets(unittest.TestCase):
    def test_fbneo_keys(self):
        g = games.GAMES["sfiii3nr1"]
        self.assertEqual(backends.get(g.backend_type).targets(g, 0, {"lp", "left"}),
                         {("key", 22), ("key", 30)})   # U, A

    def test_vpad(self):
        g = games.GAMES["mvc2"]
        self.assertEqual(backends.get(g.backend_type).targets(g, 1, {"a1", "up"}),
                         {("axis", ev.ABS_Z), ("hat", "up")})

    def test_keyboard_generic(self):
        data = {"id": "kb", "title": "KB", "backend": {"type": "keyboard"},
                "buttons": [{"id": "a", "target": ["KEY_J", "KEY_NUMERIC_1"]}],
                "system": {"start": ["KEY_1", "KEY_2"]}}
        g = games.Game(data, "kb.toml")
        out = backends.get("keyboard").targets(g, 0, {"a", "start", "up"})
        self.assertEqual(out, {("key", ev.KEYS["KEY_J"]), ("key", ev.KEYS["KEY_1"]), ("key", ev.KEYS["KEY_W"])})


class TestHub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.hub, self.plat = make_hub(self.tmp)

    def tearDown(self):
        self.hub.close()
        shutil.rmtree(self.tmp)

    def plug(self, dev):
        self.plat.new.append(dev)
        self.hub._last_scan = 0
        self.hub.step(timeout=0)
        return self.hub.pads[dev.key]

    def test_ds4_plays_with_default_layout(self):
        pad = self.plug(FakeDevice("e1", driver="playstation"))
        self.assertEqual(pad.slot, 0)
        self.assertEqual(pad.kind, "default")
        pad.dev.press(ev.BTN_WEST)          # quadrado = soco fraco = U no P1
        self.hub.step(timeout=0)
        self.assertEqual(self.hub.kb.down, {22})
        self.hub.set_output(False)          # jogo fechado: não digita nada
        self.assertEqual(self.hub.kb.down, set())

    def test_generic_pad_runs_wizard(self):
        pad = self.plug(FakeDevice("e2", driver="hid-generic"))
        self.assertIsNotNone(pad.wizard)
        for code in (0x130, 0x131, 0x132, 0x133, 0x134, 0x135, 0x13B, 0x13A):
            pad.dev.press(code)
            self.hub.step(timeout=0)
            pad.dev.press(code, 0)
            self.hub.step(timeout=0)
        self.assertIsNone(pad.wizard)
        self.assertEqual(pad.kind, "custom")
        self.assertEqual(pad.mapping["lp"], ["k:%d" % 0x130])

    def test_second_pad_is_p2_and_swap(self):
        a = self.plug(FakeDevice("e1", driver="playstation"))
        b = self.plug(FakeDevice("e2", driver="xpad", vendor=0x045E, product=0x028E))
        self.assertEqual((a.slot, b.slot), (0, 1))
        self.hub.swap()
        self.assertEqual((a.slot, b.slot), (1, 0))

    def test_unplug_frees_slot(self):
        pad = self.plug(FakeDevice("e1"))
        self.hub.remove_pad(pad)
        self.assertEqual(self.hub.slots, [None, None])
        self.assertTrue(pad.dev.closed)


class TestWindowsTranslation(unittest.TestCase):
    """As tabelas do Windows são funções puras: dá pra testar em qualquer sistema."""

    def test_scancodes(self):
        from ficha.platform import windows_maps as wm
        self.assertEqual(wm.scancode(ev.KEYS["KEY_W"]), (0x11, False))
        self.assertEqual(wm.scancode(103), (0x48, True))   # seta pra cima: estendida

    def test_sdl_buttons_are_positional(self):
        from ficha.platform import windows_maps as wm
        self.assertEqual(wm.SDL_BUTTON_TO_CODE[2], ev.BTN_WEST)    # SDL X = oeste
        self.assertEqual(wm.SDL_BUTTON_TO_CODE[3], ev.BTN_NORTH)   # SDL Y = norte


if __name__ == "__main__":
    unittest.main()
