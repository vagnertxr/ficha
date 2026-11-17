# Controllers and driver quirks

[Português](controllers.pt-BR.md)

## What gets a layout automatically

ficha uses the default layout from the game's TOML when it trusts the driver's button **positions**:

| Driver (Linux) | Controllers | Note |
|---|---|---|
| `playstation` / `sony` | DualShock 4, DualSense, most PS4/PS5 arcade sticks in PS mode | follows the kernel's positional convention |
| `xpad` / `xone` / `xpadneo` | Xbox pads, XInput sticks and boxes, GP2040-CE in XInput mode | **quirk:** reports Xbox X (west) as `BTN_X` = `BTN_NORTH`; ficha corrects it |
| `hid-microsoft` | some Xbox pads over Bluetooth | |
| `sdl-gamecontroller` (Windows) | anything SDL knows | SDL already normalizes positions |

Everything else runs the **mapping wizard** (8 presses). That includes `hid-generic`: generic DInput boards, GP2040-CE in DInput mode, Brook boards that show up as "ZEROPLUS P4". The mapping is remembered.

## Identity: how ficha recognizes "your" controller

1. `uniq` (DS4/DualSense expose their MAC address): unique per controller.
2. USB serial number: unique per controller.
3. Otherwise vendor:product + name: shared by identical models. The panel shows a "by model" badge.

## Known quirks

- **Analog triggers:**
  - xpad: LT/RT are axes (`ABS_Z`/`ABS_RZ`, 0–255).
  - hid-playstation: L2/R2 come both as a button **and** an axis. The wizard prefers the button.
- **Brook boards in PS4/PS5 mode, via hid-generic:**
  - L2/R2 are on `ABS_RX`/`ABS_RY` and rest at **0**, not at the middle.
  - ficha takes each axis's rest value from the moment the controller is plugged in. So don't hold anything while plugging in.
- **Raspberry Pi Pico (GP2040-CE):**
  - XInput mode is the easiest: it uses `xpad` and gets an automatic layout.
  - Keyboard mode doesn't work: ficha reads gamepads, not keyboards.
- **Steam's virtual controllers (28de:11ff):**
  - ficha ignores them, because they mirror a physical controller it already reads.
  - See [troubleshooting](troubleshooting.md) for when Steam grabs controllers.
- **SOCD:** left+right = neutral, up+down = up (tournament standard), applied to every output.
