# How it works

[Português](architecture.pt-BR.md)

```
physical controllers ──> platform (Linux: evdev + exclusive grab │ Windows: SDL)
                               │  common codes (Linux evdev codes as the lingua franca)
                               v
                  hub (ficha/core.py): P1/P2, per-player and per-game profiles,
                               │       wizard, combos, SOCD
                               v
              backend (ficha/backends/*): "button X of P1" -> concrete output
                               │
          ┌────────────────────┴─────────────────────┐
   virtual keyboard (fixed keys)            2 virtual gamepads "ficha P1/P2"
   uinput │ SendInput                       uinput │ ViGEm
          │                                          │
     FBNeo (.ini points at the keys)     Flycast / Steam / any SDL or XInput game
```

## Decisions and why

- **Fixed outputs instead of rewriting the game's config for each person:** the game's config is touched once, and P1/P2 never depend on plug-in order.
- **Virtual keyboard for FBNeo (Fightcade):**
  - FBNeo picks joysticks by index.
  - Under wine, DS4 controllers are read through hidraw, which can't be hidden from it.
  - Keys are global and fixed.
- **Virtual gamepads for Flycast/Steam/SDL:**
  - Flycast puts the whole keyboard on a single port.
  - SDL respects `SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT` for raw joysticks too, so the game only sees "ficha P1" (index 0) and "ficha P2" (index 1).
- **Linux evdev codes as the common language:**
  - Profiles, layouts and the hub are identical on Linux and Windows.
  - On Windows, the platform translates SDL → codes on input and codes → ViGEm/SendInput on output.
- **Layout by physical position:** the same person gets the same layout on any controller with a positional driver.
- **Output only while the game is running:** a virtual keyboard would otherwise type into whatever window has focus.

## Code map

| File | Role |
|---|---|
| `ficha/core.py` | the hub |
| `ficha/profiles.py` | identity, positions, profiles (`perfis.json`) |
| `ficha/games.py` + `ficha/games/*.toml` | game definitions |
| `ficha/backends/` | one module per game type; `steam_setup.py` + `vdf.py` for Steam |
| `ficha/platform/` | `linux.py`, `windows.py`, `windows_maps.py` |
| `ficha/web.py` + `ficha/ui/index.html` | panel (stdlib HTTP + Server-Sent Events) |
| `ficha/i18n.py` + `ficha/locales/` | pt / en |
| `tests/test_unit.py` | device-free tests (CI) |
| `tests/test_sim.py` | end-to-end test with uinput virtual controllers (Linux; ficha must be closed) |
