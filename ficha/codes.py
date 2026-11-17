"""Códigos de input comuns a todas as plataformas.

O ficha usa os códigos do evdev do Linux (linux/input-event-codes.h) como
língua comum: no Linux eles vêm direto do kernel; no Windows a camada de
plataforma traduz o que o SDL lê pra esses códigos e traduz de volta na saída
(ViGEm/SendInput). Assim perfis, layouts e núcleo são os mesmos nos dois.
"""

EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
SYN_REPORT, SYN_DROPPED = 0, 3
INPUT_PROP_ACCELEROMETER = 0x06

ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11
ABS_MAX = 0x3F
HAT_CODES = range(ABS_HAT0X, 0x18)

BTN_JOYSTICK = 0x120  # BTN_TRIGGER
BTN_SOUTH, BTN_EAST, BTN_C = 0x130, 0x131, 0x132
BTN_NORTH, BTN_WEST, BTN_Z = 0x133, 0x134, 0x135  # BTN_X == BTN_NORTH, BTN_Y == BTN_WEST
BTN_TL, BTN_TR, BTN_TL2, BTN_TR2 = 0x136, 0x137, 0x138, 0x139
BTN_SELECT, BTN_START, BTN_MODE = 0x13A, 0x13B, 0x13C
BTN_THUMBL, BTN_THUMBR = 0x13D, 0x13E
BTN_DPAD_UP, BTN_DPAD_DOWN, BTN_DPAD_LEFT, BTN_DPAD_RIGHT = 0x220, 0x221, 0x222, 0x223
BTN_TRIGGER_HAPPY1, BTN_TRIGGER_HAPPY40 = 0x2C0, 0x2E7
KEY_MAX = 0x2FF

# Teclas por nome, pro backend de teclado genérico (KEY_A etc. nos TOML).
# Em letras, números e afins o código do Linux é o mesmo scancode set 1 do PC.
KEYS = {"KEY_ESC": 1, "KEY_MINUS": 12, "KEY_EQUAL": 13, "KEY_BACKSPACE": 14, "KEY_TAB": 15,
        "KEY_LEFTBRACE": 26, "KEY_RIGHTBRACE": 27, "KEY_ENTER": 28, "KEY_LEFTCTRL": 29,
        "KEY_SEMICOLON": 39, "KEY_APOSTROPHE": 40, "KEY_GRAVE": 41, "KEY_LEFTSHIFT": 42,
        "KEY_BACKSLASH": 43, "KEY_COMMA": 51, "KEY_DOT": 52, "KEY_SLASH": 53, "KEY_RIGHTSHIFT": 54,
        "KEY_LEFTALT": 56, "KEY_SPACE": 57, "KEY_UP": 103, "KEY_LEFT": 105, "KEY_RIGHT": 106,
        "KEY_DOWN": 108, "KEY_RIGHTCTRL": 97, "KEY_RIGHTALT": 100}
KEYS.update({"KEY_%d" % ((i + 1) % 10): 2 + i for i in range(10)})
for row, first in (("QWERTYUIOP", 16), ("ASDFGHJKL", 30), ("ZXCVBNM", 44)):
    KEYS.update({"KEY_" + ch: first + i for i, ch in enumerate(row)})
KEYS.update({"KEY_F%d" % n: 58 + n for n in range(1, 11)})


class AbsInfo:
    """Faixa e valor atual de um eixo (struct input_absinfo)."""
    __slots__ = ("value", "min", "max", "fuzz", "flat", "res")

    def __init__(self, value=0, min=0, max=0, fuzz=0, flat=0, res=0):
        self.value, self.min, self.max, self.fuzz, self.flat, self.res = value, min, max, fuzz, flat, res
