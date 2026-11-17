"""Plataforma Linux: evdev e uinput na mão, só com a stdlib (fcntl/struct/os).

Evita depender de python-evdev: a máquina da jogatina só precisa de Python.
Constantes de /usr/include/linux/input.h, input-event-codes.h e uinput.h.
"""

import array
import fcntl
import os
import select
import struct

# --- ioctl -------------------------------------------------------------------

_IOC_WRITE, _IOC_READ = 1, 2


def _IOC(d, t, nr, size):
    return (d << 30) | (size << 16) | (ord(t) << 8) | nr


def _IOR(t, nr, size):
    return _IOC(_IOC_READ, t, nr, size)


def _IOW(t, nr, size):
    return _IOC(_IOC_WRITE, t, nr, size)


def _IO(t, nr):
    return _IOC(0, t, nr, 0)


EVIOCGID = _IOR("E", 0x02, 8)
EVIOCGRAB = _IOW("E", 0x90, 4)


def EVIOCGNAME(n): return _IOC(_IOC_READ, "E", 0x06, n)
def EVIOCGPHYS(n): return _IOC(_IOC_READ, "E", 0x07, n)
def EVIOCGUNIQ(n): return _IOC(_IOC_READ, "E", 0x08, n)
def EVIOCGPROP(n): return _IOC(_IOC_READ, "E", 0x09, n)
def EVIOCGKEY(n): return _IOC(_IOC_READ, "E", 0x18, n)
def EVIOCGBIT(ev, n): return _IOC(_IOC_READ, "E", 0x20 + ev, n)
def EVIOCGABS(code): return _IOR("E", 0x40 + code, 24)


UI_DEV_CREATE = _IO("U", 1)
UI_DEV_DESTROY = _IO("U", 2)
UI_DEV_SETUP = _IOW("U", 3, 92)
UI_ABS_SETUP = _IOW("U", 4, 28)
UI_SET_EVBIT = _IOW("U", 100, 4)
UI_SET_KEYBIT = _IOW("U", 101, 4)
UI_SET_ABSBIT = _IOW("U", 103, 4)


def UI_GET_SYSNAME(n): return _IOC(_IOC_READ, "U", 44, n)


# --- códigos -----------------------------------------------------------------

from ..codes import *  # noqa: F401,F403 (os códigos são a língua comum)
from ..codes import AbsInfo

# input_event em 64 bits: timeval(16) + type u16 + code u16 + value s32
EVENT = struct.Struct("llHHi")


def _test_bit(buf, bit):
    return bool(buf[bit // 8] & (1 << (bit % 8)))


def _ioctl_buf(fd, req, n):
    buf = array.array("B", [0] * n)
    fcntl.ioctl(fd, req, buf, True)
    return buf


def _ioctl_str(fd, req_fn, n=256):
    try:
        return bytes(_ioctl_buf(fd, req_fn(n), n)).split(b"\0", 1)[0].decode(errors="replace")
    except OSError:
        return ""


def _absinfo(raw):
    return AbsInfo(*struct.unpack("6i", raw))


def _sysfs_info(event_path):
    """Driver e serial USB a partir do sysfs (o evdev não expõe nenhum dos dois)."""
    node = os.path.basename(event_path)
    base = os.path.realpath(f"/sys/class/input/{node}/device")
    driver, serial = "", ""
    # Sobe a árvore: o primeiro 'driver' acima do inputN é o que importa
    # (xpad no nível da interface USB; playstation/hid-generic no nível HID).
    p = base
    while p not in ("/", "/sys", "/sys/devices"):
        if not driver and os.path.islink(os.path.join(p, "driver")):
            driver = os.path.basename(os.path.realpath(os.path.join(p, "driver")))
        # O serial só vale no próprio aparelho USB (a pasta com idVendor). Acima
        # dele vem o hub raiz, cujo "serial" é o endereço PCI da porta.
        if os.path.isfile(os.path.join(p, "idVendor")):
            try:
                serial = open(os.path.join(p, "serial")).read().strip()
            except OSError:
                pass
            break
        p = os.path.dirname(p)
    return driver, serial


class InputDevice:
    """Um /dev/input/eventN aberto em modo não-bloqueante."""

    def __init__(self, path):
        self.path = path
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            self.name = _ioctl_str(self.fd, EVIOCGNAME)
            self.phys = _ioctl_str(self.fd, EVIOCGPHYS)
            self.uniq = _ioctl_str(self.fd, EVIOCGUNIQ)
            idbuf = _ioctl_buf(self.fd, EVIOCGID, 8)
            self.bustype, self.vendor, self.product, self.version = struct.unpack("4H", bytes(idbuf))
            self.keys = _ioctl_buf(self.fd, EVIOCGBIT(EV_KEY, KEY_MAX // 8 + 1), KEY_MAX // 8 + 1)
            self.abs_bits = _ioctl_buf(self.fd, EVIOCGBIT(EV_ABS, ABS_MAX // 8 + 1), ABS_MAX // 8 + 1)
            self.props = _ioctl_buf(self.fd, EVIOCGPROP(8), 8)
            self.absinfo = {}
            for code in range(ABS_MAX + 1):
                if _test_bit(self.abs_bits, code):
                    self.absinfo[code] = _absinfo(bytes(_ioctl_buf(self.fd, EVIOCGABS(code), 24)))
            self.driver, self.serial = _sysfs_info(path)
        except Exception:
            os.close(self.fd)
            raise
        self.key = os.path.basename(path)   # chave estável enquanto plugado
        self.grabbed = False
        self._partial = b""

    def has_key(self, code):
        return _test_bit(self.keys, code)

    def key_codes(self):
        return [c for c in range(KEY_MAX + 1) if _test_bit(self.keys, c)]

    def pressed_keys(self):
        """Estado atual das teclas (para não perder botão segurado durante o plug)."""
        n = KEY_MAX // 8 + 1
        try:
            buf = _ioctl_buf(self.fd, EVIOCGKEY(n), n)
        except OSError:
            return set()
        return {c for c in range(KEY_MAX + 1) if _test_bit(buf, c)}

    def current_abs(self):
        out = {}
        for code in self.absinfo:
            try:
                out[code] = _absinfo(bytes(_ioctl_buf(self.fd, EVIOCGABS(code), 24))).value
            except OSError:
                pass
        return out

    @property
    def is_gamepad(self):
        """Joystick/gamepad de verdade (não sensor de movimento nem touchpad do DS4)."""
        if _test_bit(self.props, INPUT_PROP_ACCELEROMETER):
            return False
        for c in range(BTN_JOYSTICK, BTN_THUMBR + 1):
            if self.has_key(c):
                return True
        for c in range(BTN_TRIGGER_HAPPY1, BTN_TRIGGER_HAPPY40 + 1):
            if self.has_key(c):
                return True
        return False

    def grab(self):
        try:
            fcntl.ioctl(self.fd, EVIOCGRAB, 1)
            self.grabbed = True
        except OSError:
            self.grabbed = False

    def read(self):
        """Lê todos os eventos pendentes. Levanta OSError(ENODEV) se desplugou."""
        try:
            data = self._partial + os.read(self.fd, EVENT.size * 64)
        except BlockingIOError:
            return []
        n = len(data) // EVENT.size * EVENT.size
        self._partial = data[n:]
        return [EVENT.unpack_from(data, i)[2:] for i in range(0, n, EVENT.size)]

    def fileno(self):
        return self.fd

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


class UInput:
    """Dispositivo virtual. Com abs=None vira teclado; com abs vira gamepad (testes)."""

    def __init__(self, name, keys, abs=None, vendor=0x1209, product=0xF1C4, bustype=0x03):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
        for k in keys:
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, k)
        if abs:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_ABS)
            for code, (lo, hi) in abs.items():
                fcntl.ioctl(self.fd, UI_SET_ABSBIT, code)
                rest = lo if code in (ABS_Z, ABS_RZ) and lo == 0 else (lo + hi) // 2
                setup = struct.pack("HH6i", code, 0, rest, lo, hi, 0, 0, 0)
                fcntl.ioctl(self.fd, UI_ABS_SETUP, setup)
        setup = struct.pack("4H80sI", bustype, vendor, product, 1, name.encode()[:79], 0)
        fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)

    def sysname(self):
        return bytes(_ioctl_buf(self.fd, UI_GET_SYSNAME(64), 64)).split(b"\0", 1)[0].decode()

    def emit(self, type_, code, value, syn=True):
        os.write(self.fd, EVENT.pack(0, 0, type_, code, value))
        if syn:
            os.write(self.fd, EVENT.pack(0, 0, EV_SYN, SYN_REPORT, 0))

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)


# --- a plataforma -------------------------------------------------------------

KEYBOARD_NAME = "ficha teclado virtual"
# Controles virtuais: layout de controle Xbox com ID próprio (pid.codes 1209:f1c5),
# pra dar pra esconder dos jogos (via SDL) todo o resto.
VPAD_NAMES = ("ficha P1", "ficha P2")
VPAD_ID = (0x1209, 0xF1C5)
VPAD_BTNS = [0x130, 0x131, 0x133, 0x134, 0x136, 0x137, 0x13A, 0x13B, 0x13C, 0x13D, 0x13E]
VPAD_ABS = {ABS_X: (-32768, 32767), ABS_Y: (-32768, 32767), ABS_Z: (0, 255),
            ABS_RX: (-32768, 32767), ABS_RY: (-32768, 32767), ABS_RZ: (0, 255),
            ABS_HAT0X: (-1, 1), ABS_HAT0Y: (-1, 1)}
OWN_DEVICES = {KEYBOARD_NAME} | set(VPAD_NAMES)
STEAM_VIRTUAL = (0x28DE, 0x11FF)   # controle virtual do Steam Input: espelha um físico


class LinuxPlatform:
    name = "linux"
    trigger_max = 255

    def __init__(self, input_dir="/dev/input"):
        self.input_dir = input_dir
        self.ignored = {}

    def make_keyboard(self, keys):
        return UInput(KEYBOARD_NAME, keys)

    def make_vpads(self):
        # P1 criado antes do P2: eventN menor, então índice SDL 0.
        return [UInput(n, VPAD_BTNS, VPAD_ABS, vendor=VPAD_ID[0], product=VPAD_ID[1]) for n in VPAD_NAMES]

    def discover(self, known):
        """Controles novos (já abertos), fora os de chave em 'known'."""
        try:
            names = [n for n in os.listdir(self.input_dir) if n.startswith("event")]
        except OSError:
            return []
        found, present = [], set()
        for n in names:
            path = os.path.join(self.input_dir, n)
            present.add(path)
            if n in known:
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            stamp = (st.st_ino, st.st_ctime_ns)
            if self.ignored.get(path) == stamp:
                continue
            try:
                dev = InputDevice(path)
            except OSError:
                # Sem permissão (teclado, mouse...) ou sumiu no meio. Joysticks
                # ganham ACL pelo uaccess do systemd; se aparecer depois, o stamp muda.
                self.ignored[path] = stamp
                continue
            if not dev.is_gamepad or dev.name in OWN_DEVICES or (dev.vendor, dev.product) == STEAM_VIRTUAL:
                dev.close()
                self.ignored[path] = stamp
                continue
            found.append(dev)
        for path in list(self.ignored):
            if path not in present:
                del self.ignored[path]
        return found

    def wait(self, devices, timeout):
        """Os dispositivos com eventos pendentes, esperando até 'timeout' segundos."""
        fds = {d.fd: d for d in devices}
        try:
            ready, _, _ = select.select(list(fds), [], [], timeout)
        except (OSError, ValueError):
            return []
        return [fds[fd] for fd in ready]
