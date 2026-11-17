"""Tabelas de tradução da plataforma Windows (funções puras, testáveis em qualquer sistema)."""

from .. import codes as ev

# SDL_GameControllerButton -> código comum (posicional: o SDL já normaliza)
SDL_BUTTON_TO_CODE = {
    0: ev.BTN_SOUTH, 1: ev.BTN_EAST, 2: ev.BTN_WEST, 3: ev.BTN_NORTH,
    4: ev.BTN_SELECT, 5: ev.BTN_MODE, 6: ev.BTN_START, 7: ev.BTN_THUMBL, 8: ev.BTN_THUMBR,
    9: ev.BTN_TL, 10: ev.BTN_TR,
    11: ev.BTN_DPAD_UP, 12: ev.BTN_DPAD_DOWN, 13: ev.BTN_DPAD_LEFT, 14: ev.BTN_DPAD_RIGHT,
    15: ev.BTN_TRIGGER_HAPPY1,                       # misc (Share/Capture)
    16: ev.BTN_TRIGGER_HAPPY1 + 1, 17: ev.BTN_TRIGGER_HAPPY1 + 2,   # paddles
    18: ev.BTN_TRIGGER_HAPPY1 + 3, 19: ev.BTN_TRIGGER_HAPPY1 + 4,
    20: ev.BTN_TRIGGER_HAPPY1 + 5,                   # touchpad
}
# SDL_GameControllerAxis -> (código comum, mínimo, máximo)
SDL_AXIS_TO_CODE = {
    0: (ev.ABS_X, -32768, 32767), 1: (ev.ABS_Y, -32768, 32767),
    2: (ev.ABS_RX, -32768, 32767), 3: (ev.ABS_RY, -32768, 32767),
    4: (ev.ABS_Z, 0, 32767), 5: (ev.ABS_RZ, 0, 32767),
}


def raw_button_code(n):
    """Joystick cru (sem mapeamento do SDL): botão n -> BTN_TRIGGER_HAPPYn."""
    return ev.BTN_TRIGGER_HAPPY1 + n if n < 40 else None


def raw_axis_code(n):
    return ev.ABS_X + n if n < 8 else None   # X Y Z RX RY RZ THROTTLE RUDDER


# Código de tecla do Linux -> (scancode set 1, estendida?)
_EXTENDED = {96: 0x1C, 97: 0x1D, 98: 0x35, 100: 0x38, 102: 0x47, 103: 0x48, 104: 0x49,
             105: 0x4B, 106: 0x4D, 107: 0x4F, 108: 0x50, 109: 0x51, 110: 0x52, 111: 0x53}


def scancode(code):
    if code in _EXTENDED:
        return _EXTENDED[code], True
    if code == 87:
        return 0x57, False   # F11
    if code == 88:
        return 0x58, False   # F12
    return code, False       # o resto do teclado principal: código Linux == set 1


# Código comum de botão -> nome do botão XUSB do ViGEm (mesmos alvos que VPAD_OUT)
VPAD_BUTTON = {0x130: "A", 0x131: "B", 0x133: "X", 0x134: "Y", 0x136: "LEFT_SHOULDER",
               0x137: "RIGHT_SHOULDER", 0x13A: "BACK", 0x13B: "START", 0x13C: "GUIDE",
               0x13D: "LEFT_THUMB", 0x13E: "RIGHT_THUMB"}
VPAD_TRIGGER = {ev.ABS_Z: "left", ev.ABS_RZ: "right"}


def hidhide_instance_id(sdl_path):
    """\\\\?\\hid#vid_054c&pid_09cc#7&2b2a1b6c&0&0000#{guid} -> HID\\VID_054C&PID_09CC\\7&2B2A1B6C&0&0000"""
    p = sdl_path
    if p.startswith("\\\\?\\"):
        p = p[4:]
    parts = p.split("#")
    if len(parts) < 3:
        return None
    return "\\".join(parts[:3]).upper()
