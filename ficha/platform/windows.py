"""Plataforma Windows (EXPERIMENTAL: escrita sem teste em PC Windows de verdade).

Entrada:  SDL2 via pysdl2 (+ pysdl2-dll). Controles conhecidos pelo SDL viram
          "sdl-gamecontroller" (botões por posição); o resto, "sdl-joystick" (cru).
Saída:    teclado virtual por SendInput (scancodes); controles virtuais Xbox 360
          pelo ViGEmBus via vgamepad.
Esconder: o Windows não tem o "agarre" do evdev. Pra os jogos não verem os
          controles físicos, use o HidHide (veja docs/setup.md); com
          `hidhide = true` na config o ficha tenta configurá-lo sozinho.

Dependências: pip install "ficha[windows]" (pysdl2, pysdl2-dll, vgamepad) e os
drivers ViGEmBus e (opcional) HidHide.
"""

import ctypes
import errno
import os
import subprocess
import sys
from ctypes import wintypes

from .. import codes as ev
from .. import config
from ..codes import AbsInfo
from . import windows_maps as wm

import sdl2   # noqa: E402  (pysdl2; falta = ImportError tratado no __main__)
import vgamepad   # noqa: E402

SYN = (ev.EV_SYN, ev.SYN_REPORT, 0)


# --- entrada (SDL) ------------------------------------------------------------

class SDLDevice:
    def __init__(self, index):
        self.controller = None
        if sdl2.SDL_IsGameController(index):
            self.controller = sdl2.SDL_GameControllerOpen(index)
            joy = sdl2.SDL_GameControllerGetJoystick(self.controller)
            self.driver = "sdl-gamecontroller"
        else:
            joy = sdl2.SDL_JoystickOpen(index)
            self.driver = "sdl-joystick"
        if not joy:
            raise OSError(errno.ENODEV, "SDL não abriu o controle %d" % index)
        self.joy = joy
        self.instance = sdl2.SDL_JoystickInstanceID(joy)
        self.key = "sdl%d" % self.instance
        self.path = (sdl2.SDL_JoystickPath(joy) or b"").decode(errors="replace") if hasattr(sdl2, "SDL_JoystickPath") else ""
        self.name = (sdl2.SDL_JoystickName(joy) or b"?").decode(errors="replace")
        self.vendor = sdl2.SDL_JoystickGetVendor(joy)
        self.product = sdl2.SDL_JoystickGetProduct(joy)
        serial = sdl2.SDL_JoystickGetSerial(joy) if hasattr(sdl2, "SDL_JoystickGetSerial") else None
        self.serial = (serial or b"").decode(errors="replace")
        self.uniq = ""
        self.player_index = sdl2.SDL_JoystickGetPlayerIndex(joy)
        self.grabbed = False
        self.removed = False
        self.queue = []
        self.absinfo = {}
        self._keys = set()
        if self.controller:
            self._keys = set(wm.SDL_BUTTON_TO_CODE.values())
            for code, lo, hi in wm.SDL_AXIS_TO_CODE.values():
                self.absinfo[code] = AbsInfo(0, lo, hi)
        else:
            for n in range(sdl2.SDL_JoystickNumButtons(joy)):
                c = wm.raw_button_code(n)
                if c is not None:
                    self._keys.add(c)
            for n in range(sdl2.SDL_JoystickNumAxes(joy)):
                c = wm.raw_axis_code(n)
                if c is not None:
                    self.absinfo[c] = AbsInfo(sdl2.SDL_JoystickGetAxis(joy, n), -32768, 32767)
            if sdl2.SDL_JoystickNumHats(joy):
                self.absinfo[ev.ABS_HAT0X] = AbsInfo(0, -1, 1)
                self.absinfo[ev.ABS_HAT0Y] = AbsInfo(0, -1, 1)
        for code, info in self.current_abs().items():
            self.absinfo[code].value = info

    @property
    def is_gamepad(self):
        return bool(self._keys)

    def has_key(self, code):
        return code in self._keys

    def pressed_keys(self):
        out = set()
        if self.controller:
            for b, code in wm.SDL_BUTTON_TO_CODE.items():
                if sdl2.SDL_GameControllerGetButton(self.controller, b):
                    out.add(code)
        else:
            for n in range(sdl2.SDL_JoystickNumButtons(self.joy)):
                if sdl2.SDL_JoystickGetButton(self.joy, n) and wm.raw_button_code(n) is not None:
                    out.add(wm.raw_button_code(n))
        return out

    def current_abs(self):
        out = {}
        if self.controller:
            for a, (code, _, _) in wm.SDL_AXIS_TO_CODE.items():
                out[code] = sdl2.SDL_GameControllerGetAxis(self.controller, a)
        else:
            for n in range(sdl2.SDL_JoystickNumAxes(self.joy)):
                c = wm.raw_axis_code(n)
                if c is not None:
                    out[c] = sdl2.SDL_JoystickGetAxis(self.joy, n)
        return out

    def grab(self):
        # Sem agarre exclusivo no Windows: quem esconde dos jogos é o HidHide.
        self.grabbed = True

    def read(self):
        if self.removed and not self.queue:
            raise OSError(errno.ENODEV, "controle removido")
        out, self.queue = self.queue, []
        return out

    def close(self):
        if self.controller:
            sdl2.SDL_GameControllerClose(self.controller)
        else:
            sdl2.SDL_JoystickClose(self.joy)


# --- saída --------------------------------------------------------------------

INPUT_KEYBOARD, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 1, 0x1, 0x2, 0x8


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("_pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class SendInputKeyboard:
    """Teclado virtual: scancodes por SendInput (vão pra janela em foco)."""

    def emit(self, type_, code, value, syn=True):
        if type_ != ev.EV_KEY:
            return
        scan, extended = wm.scancode(code)
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if extended else 0) | (0 if value else KEYEVENTF_KEYUP)
        inp = INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(0, scan, flags, 0, None)))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def close(self):
        pass


class ViGEmPad:
    """Controle virtual Xbox 360 (ViGEmBus). Recebe os mesmos códigos dos
    controles virtuais do Linux e traduz pro XUSB."""

    def __init__(self):
        self.pad = vgamepad.VX360Gamepad()
        self.hat = [0, 0]

    def emit(self, type_, code, value, syn=True):
        if type_ == ev.EV_KEY and code in wm.VPAD_BUTTON:
            btn = getattr(vgamepad.XUSB_BUTTON, "XUSB_GAMEPAD_" + wm.VPAD_BUTTON[code])
            (self.pad.press_button if value else self.pad.release_button)(button=btn)
        elif type_ == ev.EV_ABS and code in wm.VPAD_TRIGGER:
            getattr(self.pad, wm.VPAD_TRIGGER[code] + "_trigger")(value=max(0, min(255, value)))
        elif type_ == ev.EV_ABS and code in (ev.ABS_HAT0X, ev.ABS_HAT0Y):
            self.hat[code - ev.ABS_HAT0X] = value
            for name, on in (("LEFT", self.hat[0] < 0), ("RIGHT", self.hat[0] > 0),
                             ("UP", self.hat[1] < 0), ("DOWN", self.hat[1] > 0)):
                btn = getattr(vgamepad.XUSB_BUTTON, "XUSB_GAMEPAD_DPAD_" + name)
                (self.pad.press_button if on else self.pad.release_button)(button=btn)
        elif type_ == ev.EV_SYN:
            self.pad.update()

    def close(self):
        self.pad.reset()
        self.pad.update()
        del self.pad


def _xinput_connected():
    """Quais slots XInput (0-3) têm controle agora."""
    try:
        xinput = ctypes.windll.xinput1_4
    except OSError:
        return set()
    state = (ctypes.c_byte * 16)()
    return {i for i in range(4) if xinput.XInputGetState(i, ctypes.byref(state)) == 0}


# --- HidHide (opcional) -------------------------------------------------------

HIDHIDE_CLI = r"C:\Program Files\Nefarius Software Solutions\HidHide\x64\HidHideCLI.exe"


def _hidhide(*args):
    if not os.path.exists(HIDHIDE_CLI):
        return False
    return subprocess.run([HIDHIDE_CLI] + list(args), capture_output=True).returncode == 0


# --- a plataforma -------------------------------------------------------------

class WindowsPlatform:
    name = "windows"
    trigger_max = 255

    def __init__(self):
        sdl2.SDL_SetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")
        if sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER | sdl2.SDL_INIT_JOYSTICK) != 0:
            raise RuntimeError(sdl2.SDL_GetError().decode())
        self.devices = {}         # instance id -> SDLDevice
        self.pending = set()      # índices de joystick novos
        self.own_xinput = set()   # slots XInput dos controles virtuais do próprio ficha
        self.use_hidhide = bool(config.CONFIG.get("hidhide"))
        if self.use_hidhide:
            _hidhide("--app-reg", sys.executable)   # o ficha continua enxergando tudo
            _hidhide("--cloak-on")

    def make_keyboard(self, keys):
        return SendInputKeyboard()

    def make_vpads(self):
        before = _xinput_connected()
        pads = [ViGEmPad(), ViGEmPad()]
        self.own_xinput = _xinput_connected() - before
        return pads

    def discover(self, known):
        self._pump(0)
        found = []
        for index in range(sdl2.SDL_NumJoysticks()):
            iid = sdl2.SDL_JoystickGetDeviceInstanceID(index)
            if iid in self.devices or "sdl%d" % iid in known:
                continue
            if sdl2.SDL_JoystickGetDevicePlayerIndex(index) in self.own_xinput:
                continue   # um dos controles virtuais do ficha
            try:
                dev = SDLDevice(index)
            except OSError:
                continue
            if not dev.is_gamepad:
                dev.close()
                continue
            self.devices[dev.instance] = dev
            if self.use_hidhide and dev.path:
                iid_path = wm.hidhide_instance_id(dev.path)
                if iid_path:
                    _hidhide("--dev-hide", iid_path)
            found.append(dev)
        return found

    def _pump(self, timeout_ms):
        event = sdl2.SDL_Event()
        got = sdl2.SDL_WaitEventTimeout(ctypes.byref(event), timeout_ms) if timeout_ms else \
            sdl2.SDL_PollEvent(ctypes.byref(event))
        while got:
            self._dispatch(event)
            got = sdl2.SDL_PollEvent(ctypes.byref(event))

    def _dispatch(self, e):
        t = e.type
        if t == sdl2.SDL_CONTROLLERBUTTONDOWN or t == sdl2.SDL_CONTROLLERBUTTONUP:
            dev, code = self.devices.get(e.cbutton.which), wm.SDL_BUTTON_TO_CODE.get(e.cbutton.button)
            if dev and code is not None:
                dev.queue += [(ev.EV_KEY, code, int(t == sdl2.SDL_CONTROLLERBUTTONDOWN)), SYN]
        elif t == sdl2.SDL_CONTROLLERAXISMOTION:
            dev, spec = self.devices.get(e.caxis.which), wm.SDL_AXIS_TO_CODE.get(e.caxis.axis)
            if dev and spec:
                dev.queue += [(ev.EV_ABS, spec[0], e.caxis.value), SYN]
        elif t == sdl2.SDL_JOYBUTTONDOWN or t == sdl2.SDL_JOYBUTTONUP:
            dev = self.devices.get(e.jbutton.which)
            if dev and dev.driver == "sdl-joystick" and wm.raw_button_code(e.jbutton.button) is not None:
                dev.queue += [(ev.EV_KEY, wm.raw_button_code(e.jbutton.button), int(t == sdl2.SDL_JOYBUTTONDOWN)), SYN]
        elif t == sdl2.SDL_JOYAXISMOTION:
            dev = self.devices.get(e.jaxis.which)
            if dev and dev.driver == "sdl-joystick" and wm.raw_axis_code(e.jaxis.axis) is not None:
                dev.queue += [(ev.EV_ABS, wm.raw_axis_code(e.jaxis.axis), e.jaxis.value), SYN]
        elif t == sdl2.SDL_JOYHATMOTION:
            dev = self.devices.get(e.jhat.which)
            if dev and dev.driver == "sdl-joystick" and e.jhat.hat == 0:
                v = e.jhat.value
                hx = -1 if v & sdl2.SDL_HAT_LEFT else (1 if v & sdl2.SDL_HAT_RIGHT else 0)
                hy = -1 if v & sdl2.SDL_HAT_UP else (1 if v & sdl2.SDL_HAT_DOWN else 0)
                dev.queue += [(ev.EV_ABS, ev.ABS_HAT0X, hx), (ev.EV_ABS, ev.ABS_HAT0Y, hy), SYN]
        elif t == sdl2.SDL_JOYDEVICEREMOVED:
            dev = self.devices.pop(e.jdevice.which, None)
            if dev:
                dev.removed = True

    def wait(self, devices, timeout):
        self._pump(max(1, int(timeout * 1000)))
        return [d for d in devices if d.queue or d.removed]
