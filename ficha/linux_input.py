"""evdev e uinput na mão, só com a stdlib (fcntl/struct/os).

Evita depender de python-evdev: a máquina da jogatina só precisa de Python.
Constantes de /usr/include/linux/input.h, input-event-codes.h e uinput.h.
"""

import array
import fcntl
import os
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

EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
SYN_REPORT, SYN_DROPPED = 0, 3
INPUT_PROP_ACCELEROMETER = 0x06

ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11
ABS_MAX = 0x3F

BTN_JOYSTICK = 0x120  # BTN_TRIGGER
BTN_SOUTH, BTN_EAST, BTN_C = 0x130, 0x131, 0x132
BTN_NORTH, BTN_WEST, BTN_Z = 0x133, 0x134, 0x135  # BTN_X == BTN_NORTH, BTN_Y == BTN_WEST
BTN_TL, BTN_TR, BTN_TL2, BTN_TR2 = 0x136, 0x137, 0x138, 0x139
BTN_SELECT, BTN_START, BTN_MODE = 0x13A, 0x13B, 0x13C
BTN_THUMBL, BTN_THUMBR = 0x13D, 0x13E
BTN_DPAD_UP, BTN_DPAD_DOWN, BTN_DPAD_LEFT, BTN_DPAD_RIGHT = 0x220, 0x221, 0x222, 0x223
BTN_TRIGGER_HAPPY1, BTN_TRIGGER_HAPPY40 = 0x2C0, 0x2E7
KEY_MAX = 0x2FF

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


class AbsInfo:
    __slots__ = ("value", "min", "max", "fuzz", "flat", "res")

    def __init__(self, raw):
        self.value, self.min, self.max, self.fuzz, self.flat, self.res = struct.unpack("6i", raw)


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
                    self.absinfo[code] = AbsInfo(bytes(_ioctl_buf(self.fd, EVIOCGABS(code), 24)))
            self.driver, self.serial = _sysfs_info(path)
        except Exception:
            os.close(self.fd)
            raise
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
                out[code] = AbsInfo(bytes(_ioctl_buf(self.fd, EVIOCGABS(code), 24))).value
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
