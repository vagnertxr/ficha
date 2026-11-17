"""Simula controles com uinput e confere o hub de ponta a ponta (sem tocar no jogo).

Usa teclado falso: um teclado virtual de verdade digitaria na janela em foco.
"""
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ficha import linux_input as li
from ficha.core import Hub
from ficha.games import GAMES
from ficha.profiles import KEYMAP, ProfileStore

G = GAMES["sfiii3nr1"]


class FakeKB:
    def __init__(self): self.down, self.abs = set(), {}
    def emit(self, t, code, value, syn=True):
        if t == li.EV_KEY: (self.down.add if value else self.down.discard)(code)
        if t == li.EV_ABS: self.abs[code] = value
    def close(self): pass


def make_hub():
    store = ProfileStore(os.path.join(tempfile.mkdtemp(), "perfis.json"))
    hub = Hub(store=store, keyboard=False)
    hub.kb = FakeKB()
    hub.vpads = [FakeKB(), FakeKB()]
    return hub


def pump(hub, t=0.15):
    end = time.monotonic() + t
    while time.monotonic() < end:
        hub.step(timeout=0.02)


def keys_for(slot, *actions):
    slot_of = {b: "b%d" % (i + 1) for i, b in enumerate(G.button_ids)}
    return {KEYMAP[slot][slot_of.get(a, a)][0] for a in actions}


# Controle genérico estilo Pico/GP2040 em DInput: 12 botões BTN_GAMEPAD + hat.
GENERIC_BTNS = list(range(0x130, 0x13E))
GENERIC_ABS = {li.ABS_X: (0, 255), li.ABS_Y: (0, 255), li.ABS_HAT0X: (-1, 1), li.ABS_HAT0Y: (-1, 1)}
# "Xbox": gatilhos analógicos em Z/RZ (como o xpad)
XBOX_BTNS = [0x130, 0x131, 0x133, 0x134, 0x136, 0x137, 0x13A, 0x13B, 0x13C, 0x13D, 0x13E]
# "DS4": hid-playstation manda L2/R2 como botão E eixo
DS4_BTNS = [0x130, 0x131, 0x133, 0x134, 0x136, 0x137, 0x138, 0x139, 0x13A, 0x13B, 0x13C, 0x13D, 0x13E]
DS4_ABS = {li.ABS_X: (0, 255), li.ABS_Y: (0, 255), li.ABS_Z: (0, 255), li.ABS_RZ: (0, 255),
           li.ABS_HAT0X: (-1, 1), li.ABS_HAT0Y: (-1, 1)}
XBOX_ABS = {li.ABS_X: (-32768, 32767), li.ABS_Y: (-32768, 32767), li.ABS_Z: (0, 255),
            li.ABS_RZ: (0, 255), li.ABS_HAT0X: (-1, 1), li.ABS_HAT0Y: (-1, 1)}


def mine(hub, kind):
    return [p for p in hub.pads.values() if p.dev.name.startswith("ficha-teste " + kind)]


def press(u, code, hub):
    u.emit(li.EV_KEY, code, 1); pump(hub, 0.05)
    u.emit(li.EV_KEY, code, 0); pump(hub, 0.05)


def test_all():
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:7373/state", timeout=1)
        sys.exit("Desliga o ficha antes: ele agarraria os controles virtuais do teste.")
    except OSError:
        pass
    hub = make_hub()
    pump(hub, 1.2)
    real = set(hub.pads)  # controles físicos plugados de verdade: vão pro banco
    for k in real:
        hub.assign(hub.pads[k], None)

    a = li.UInput("ficha-teste generico", GENERIC_BTNS, GENERIC_ABS, vendor=0x1209, product=0x0001)
    pump(hub, 1.5)
    assert mine(hub, "generico"), "hub não achou o controle virtual (ACL do uaccess?)"
    pa = mine(hub, "generico")[0]
    assert pa.slot == 0 and pa.mapping is None and pa.wizard is not None, "genérico devia ir pro P1 em modo wizard"
    print("ok: genérico conectado no P1, wizard aberto")

    # Wizard: LP MP HP LK MK HK START, e START de novo pula o COIN
    order = [0x133, 0x134, 0x137, 0x130, 0x131, 0x139, 0x13B]
    for c in order:
        press(a, c, hub)
    press(a, 0x13B, hub)
    assert pa.wizard is None and pa.kind == "custom", "wizard não terminou: %r" % (pa.wizard and pa.wizard.step)
    assert pa.mapping["coin"] == [] and pa.mapping["lp"] == ["k:%d" % 0x133]
    print("ok: wizard mapeou 6 botões + START, COIN pulado")

    a.emit(li.EV_KEY, 0x133, 1, syn=False); a.emit(li.EV_ABS, li.ABS_HAT0X, -1); pump(hub, 0.1)
    assert hub.kb.down == keys_for(0, "lp", "left"), hub.kb.down
    a.emit(li.EV_KEY, 0x133, 0, syn=False); a.emit(li.EV_ABS, li.ABS_HAT0X, 0); pump(hub, 0.1)
    assert hub.kb.down == set(), hub.kb.down
    # analógico também anda
    a.emit(li.EV_ABS, li.ABS_X, 255); pump(hub, 0.1)
    assert hub.kb.down == keys_for(0, "right"), hub.kb.down
    a.emit(li.EV_ABS, li.ABS_X, 128); pump(hub, 0.1)
    print("ok: LP+trás vira U+A no teclado do P1; analógico também")

    b = li.UInput("ficha-teste xbox", XBOX_BTNS, XBOX_ABS, vendor=0x045e, product=0x028e)
    pump(hub, 1.5)
    pb = mine(hub, "xbox")[0]
    assert pb.slot == 1, "segundo controle devia ser P2"
    # Simula o driver xpad (uinput não tem driver no sysfs) e resolve de novo
    pb.dev.driver = "xpad"
    hub._apply(pb)
    assert pb.kind == "default" and pb.wizard is None
    assert pb.mapping["lp"] == ["k:%d" % 0x133] and pb.mapping["hk"] == ["a:%d:+" % li.ABS_RZ]
    b.emit(li.EV_ABS, li.ABS_RZ, 200); pump(hub, 0.1)
    assert hub.kb.down == keys_for(1, "hk"), hub.kb.down
    b.emit(li.EV_ABS, li.ABS_RZ, 0); b.emit(li.EV_KEY, 0x136, 1); pump(hub, 0.1)
    assert hub.kb.down == keys_for(1, "lp", "mp", "hp"), "LB devia ser 3 socos: %s" % hub.kb.down
    b.emit(li.EV_KEY, 0x136, 0); pump(hub, 0.1)
    print("ok: xbox no P2, RT analógico = HK, LB = 3 socos")

    # SOCD: esquerda + direita = neutro
    b.emit(li.EV_ABS, li.ABS_HAT0X, -1, syn=False); b.emit(li.EV_ABS, li.ABS_X, 32767); pump(hub, 0.1)
    assert hub.kb.down == set(), hub.kb.down
    b.emit(li.EV_ABS, li.ABS_HAT0X, 0, syn=False); b.emit(li.EV_ABS, li.ABS_X, 0); pump(hub, 0.1)
    print("ok: SOCD esquerda+direita = neutro")

    # Combo rápido START+SELECT no xbox: troca de lado
    b.emit(li.EV_KEY, 0x13A, 1, syn=False); b.emit(li.EV_KEY, 0x13B, 1); pump(hub, 0.5)
    b.emit(li.EV_KEY, 0x13A, 0, syn=False); b.emit(li.EV_KEY, 0x13B, 0); pump(hub, 0.1)
    assert pb.slot == 0 and pa.slot == 1, (pa.slot, pb.slot)
    a.emit(li.EV_KEY, 0x133, 1); pump(hub, 0.1)
    assert hub.kb.down == keys_for(1, "lp"), "depois da troca o genérico devia sair como P2"
    a.emit(li.EV_KEY, 0x133, 0); pump(hub, 0.1)
    print("ok: START+SELECT rápido troca os lados")

    # Segurar START+SELECT 2s: abre o wizard
    b.emit(li.EV_KEY, 0x13A, 1, syn=False); b.emit(li.EV_KEY, 0x13B, 1); pump(hub, 2.3)
    assert pb.wizard is not None, "segurar 2s devia abrir o wizard"
    b.emit(li.EV_KEY, 0x13A, 0, syn=False); b.emit(li.EV_KEY, 0x13B, 0); pump(hub, 0.1)
    assert hub.kb.down == set(), "no wizard o controle não manda nada pro jogo: %s" % hub.kb.down
    hub.cancel_wizard(pb)
    print("ok: segurar START+SELECT abre o mapeamento")

    # Brook em modo PS4 ("ZEROPLUS P4", hid-generic): L2/R2 em RX/RY com repouso 0.
    # Antes o ficha achava que RX/RY eram analógico (repouso no meio) e o wizard
    # travava esperando "soltar" os gatilhos.
    brook = li.UInput("ficha-teste brook", list(range(0x130, 0x13E)),
                      {li.ABS_X: (0, 255), li.ABS_Y: (0, 255), li.ABS_Z: (0, 255), li.ABS_RZ: (0, 255),
                       li.ABS_RX: (0, 255), li.ABS_RY: (0, 255), li.ABS_HAT0X: (-1, 1), li.ABS_HAT0Y: (-1, 1)},
                      vendor=0x0C12, product=0x0EF7)
    # o UInput de teste põe repouso no meio pra RX/RY; a Brook de verdade fica em 0
    brook.emit(li.EV_ABS, li.ABS_RX, 0, syn=False); brook.emit(li.EV_ABS, li.ABS_RY, 0)
    pump(hub, 1.5)
    pbk = mine(hub, "brook")[0]
    hub.remove_pad(pbk); pump(hub, 1.5)        # replug: agora o plug vê RX/RY em 0
    pbk = mine(hub, "brook")[0]
    hub.assign(pbk, 0); hub.start_wizard(pbk)
    for code in (0x130, 0x133, 0x135, 0x131, 0x132, 0x137, 0x139, 0x138):
        press(brook, code, hub)
    assert pbk.wizard is None and pbk.kind == "custom", (pbk.wizard and pbk.wizard.step, pbk.raw_buttons())
    brook.emit(li.EV_ABS, li.ABS_RY, 255); pump(hub, 0.1)   # R2 analógico apertado não vira botão fantasma
    brook.emit(li.EV_ABS, li.ABS_RY, 0); pump(hub, 0.1)
    assert not pbk.raw_buttons(), pbk.raw_buttons()
    hub.remove_pad(pbk); brook.close(); pump(hub, 0.3)
    hub.assign(pb, 0)
    print("ok: Brook (gatilhos em RX/RY parados em 0) mapeia sem travar")

    # Pessoa + perfil lembrado ao replugar
    hub.set_player(pa, "Ryu da Silva")
    assert pa.kind == "player"
    pid = pa.pid
    a.close(); pump(hub, 0.3)
    assert pa.key not in hub.pads and hub.slots[1] is None
    a = li.UInput("ficha-teste generico", GENERIC_BTNS, GENERIC_ABS, vendor=0x1209, product=0x0001)
    pump(hub, 1.5)
    pa2 = mine(hub, "generico")[0]
    assert pa2.pid == pid
    assert pa2.player == "Ryu da Silva" and pa2.kind == "player" and pa2.wizard is None
    assert pa2.slot == 1
    print("ok: replugou e voltou com jogador + mapeamento, sem wizard")

    # Ken mapeia no Xbox um layout invertido (chutes em cima)...
    hub.set_player(pb, "Ken")
    hub.start_wizard(pb)
    for c in (0x130, 0x131):           # LP=A(sul) MP=B(leste)
        press(b, c, hub)
    press(b, 0x137, hub)               # HP=RB
    for c in (0x133, 0x134):           # LK=X(oeste no xpad) MK=Y(norte)
        press(b, c, hub)
    b.emit(li.EV_ABS, li.ABS_RZ, 255); pump(hub, 0.05); b.emit(li.EV_ABS, li.ABS_RZ, 0); pump(hub, 0.05)  # HK=RT
    press(b, 0x13B, hub); press(b, 0x13A, hub)  # START, COIN
    assert pb.wizard is None and pb.kind == "player"
    ken = hub.store.player_game("Ken", "sfiii3nr1")
    assert ken["layout"] == {"lp": "south", "mp": "east", "hp": "r1", "lk": "west", "mk": "north",
                             "hk": "r2", "3p": "l1", "3k": "l2"}, ken["layout"]
    print("ok: layout do Ken salvo por posição física")

    # ...e depois pega um DS4: o layout dele vem junto, traduzido.
    c = li.UInput("ficha-teste ds4", DS4_BTNS, DS4_ABS, vendor=0x054c, product=0x09cc)
    pump(hub, 1.5)
    pc = mine(hub, "ds4")[0]
    pc.dev.driver = "playstation"
    hub._apply(pc)
    assert pc.kind == "default" and pc.slot is None  # P1 e P2 ocupados: banco
    hub.set_player(pc, "Ken")
    assert pc.kind == "player"
    hub.assign(pc, 0)
    c.emit(li.EV_KEY, 0x134, 1); pump(hub, 0.1)      # quadrado = oeste no DS4
    assert hub.kb.down == keys_for(0, "lk"), "□ devia ser LK pro Ken: %s" % hub.kb.down
    c.emit(li.EV_KEY, 0x134, 0); c.emit(li.EV_KEY, 0x139, 1); pump(hub, 0.1)  # R2 digital
    assert hub.kb.down == keys_for(0, "hk"), hub.kb.down
    c.emit(li.EV_KEY, 0x139, 0); pump(hub, 0.1)
    print("ok: Ken pegou um DS4 e o layout dele veio traduzido (□ = LK, R2 = HK)")

    hub.reset_mapping(pc)
    assert pc.mapping["lp"] == ["k:%d" % 0x134], "voltar ao padrão: LP no □"
    print("ok: voltar ao padrão")

    # MvC2 (Flycast): sai pelos controles virtuais, com o layout do jogo
    hub.assign(pb, 1)
    hub.set_game("mvc2")
    assert hub.game.id == "mvc2" and pc.kind == "default", pc.kind   # Ken não tem MvC2: padrão do jogo
    vp = hub.vpads[0]
    c.emit(li.EV_KEY, 0x134, 1, syn=False); c.emit(li.EV_ABS, li.ABS_HAT0X, 1); pump(hub, 0.1)  # □ + frente
    assert 0x133 in vp.down and vp.abs.get(li.ABS_HAT0X) == 1, (vp.down, vp.abs)   # LP -> X do virtual
    assert hub.kb.down == set(), "no MvC2 nada sai pelo teclado"
    c.emit(li.EV_KEY, 0x134, 0, syn=False); c.emit(li.EV_ABS, li.ABS_HAT0X, 0); pump(hub, 0.1)
    assert not vp.down and vp.abs.get(li.ABS_HAT0X) == 0
    c.emit(li.EV_KEY, 0x137, 1); pump(hub, 0.1)          # R1 = A1 -> LT do virtual
    assert vp.abs.get(li.ABS_Z) == 255, vp.abs
    c.emit(li.EV_KEY, 0x137, 0); pump(hub, 0.1)
    assert vp.abs.get(li.ABS_Z) == 0
    print("ok: MvC2 sai pelo controle virtual (□ = LP = X, R1 = A1 = LT)")
    # GG (Steam): sai pelos controles virtuais com o Controller Settings do jogo
    hub.set_game("ggxxacpr")
    assert pc.kind == "default" and pc.slot == 0
    c.emit(li.EV_KEY, 0x134, 1); pump(hub, 0.1)          # □ = P -> X
    assert hub.vpads[0].down == {0x133}, hub.vpads[0].down
    c.emit(li.EV_KEY, 0x134, 0); c.emit(li.EV_KEY, 0x131, 1); pump(hub, 0.1)   # ○ = D -> RB
    assert hub.vpads[0].down == {0x137}, hub.vpads[0].down
    c.emit(li.EV_KEY, 0x131, 0); pump(hub, 0.1)
    hub.swap()
    c.emit(li.EV_KEY, 0x130, 1); pump(hub, 0.1)          # × = K -> A, agora pelo P2
    assert hub.vpads[1].down == {0x130} and not hub.vpads[0].down, (hub.vpads[0].down, hub.vpads[1].down)
    c.emit(li.EV_KEY, 0x130, 0); c.emit(li.EV_KEY, 0x13A, 1); pump(hub, 0.1)   # SELECT = Reset (BACK)
    assert hub.vpads[1].down == {0x13A}, hub.vpads[1].down
    c.emit(li.EV_KEY, 0x13A, 0); pump(hub, 0.1)
    hub.swap()
    print("ok: GG sai pelo controle virtual (□ = P = X, ○ = D = RB, SELECT = Reset)")

    # Wizard do GG: Respect é opcional e vem depois do START
    hub.start_wizard(pa2)
    assert pa2.wizard.steps == ["p", "s", "hs", "k", "d", "start", "respect", "coin"], pa2.wizard.steps
    for code in (0x130, 0x131, 0x132, 0x133, 0x134, 0x13B):
        press(a, code, hub)
    press(a, 0x13B, hub)          # pula Respect
    press(a, 0x13A, hub)          # COIN
    assert pa2.wizard is None and pa2.mapping["respect"] == [], pa2.mapping.get("respect")
    print("ok: mapeamento do GG pula o Respect com START")
    hub.set_game("sfiii3nr1")

    snap = hub.snapshot()
    assert len([p for p in snap["pads"] if p["model"].startswith("ficha-teste")]) == 3
    assert snap["players"] == ["Ken", "Ryu da Silva"]
    assert snap["game"]["id"] == "sfiii3nr1"
    a.close(); b.close(); c.close(); pump(hub, 0.3)
    assert not mine(hub, "")
    hub.close()
    print("TUDO OK")


if __name__ == "__main__":
    test_all()
