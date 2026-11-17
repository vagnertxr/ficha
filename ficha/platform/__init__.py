"""Camada de plataforma: de onde vêm os controles e pra onde vão as saídas.

Cada plataforma oferece:
  discover(known)   -> controles novos já abertos (objetos com a interface de
                       linux.InputDevice: key, name, vendor, product, uniq, serial,
                       driver, absinfo, has_key, pressed_keys, current_abs, read,
                       grab, grabbed, close)
  wait(devs, t)     -> os que têm eventos pendentes
  make_keyboard(keys), make_vpads() -> saídas virtuais com emit(type, code, value, syn)
  trigger_max       -> valor de gatilho totalmente apertado nos controles virtuais
"""

import sys


def current():
    if sys.platform.startswith("linux"):
        from .linux import LinuxPlatform
        return LinuxPlatform()
    if sys.platform == "win32":
        from .windows import WindowsPlatform
        return WindowsPlatform()
    raise RuntimeError("plataforma sem suporte: %s" % sys.platform)


def vpad_id():
    """(vendor, product) dos controles virtuais do ficha nesta plataforma."""
    if sys.platform == "win32":
        return (0x045E, 0x028E)   # o ViGEm cria controles Xbox 360
    from .linux import VPAD_ID
    return VPAD_ID
