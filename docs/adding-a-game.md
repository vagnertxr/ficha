# Adding a game

[Português](adding-a-game.pt-BR.md)

## Where the file goes

Each game is one TOML file:
- **Built-in games:** in `ficha/games/`.
- **Your games:** in `~/.config/ficha/games/`. A file there with the same `id` replaces the built-in one.

Run `ficha games` to check that it loaded. Mistakes, such as an unknown key or a layout naming a button that doesn't exist, are reported on start and the file is skipped.

Ready-to-copy examples are in [`docs/examples/`](examples/).

## Structure

```toml
id = "sf2-retroarch"            # unique, used in commands (ficha play sf2-retroarch)
title = "Street Fighter II"
short = "SF2"                   # short name for the panel
year = 1991                     # optional
accent = "#3fa7ff"              # panel colour
training = false                # does the backend have a training mode? (FBNeo/Fightcade only)
optional = []                   # buttons the mapping wizard lets you skip
grid = [["lp", "mp", "hp"], ["lk", "mk", "hk"]]   # how the buttons appear in the panel (rows)

[backend]
type = "gamepad"                # fbneo-fightcade | flycast-fightcade | steam | gamepad | keyboard
# ...backend fields (below)

[[buttons]]                     # one block per button, in order
id = "lp"
short = "LP"
name = { pt = "Soco fraco", en = "Light Punch" }   # or a single string
target = "x"                    # what the button presses (depends on the backend); can be ["P1", "P2"]

[layout]                        # default layout by physical position
lp = "west"
mp = "north"
hp = "r1"
lk = "south"
mk = "east"
hk = "r2"

[macros.3p]                     # optional: one controller button presses several
name = { pt = "3 socos", en = "3 punches" }
buttons = ["lp", "mp", "hp"]

[system]                        # what START and SELECT press (default: start = "start")
start = "start"
coin = "back"
```

> **TOML gotcha:** loose keys (`grid`, `optional`…) must come **before** the first `[backend]` or `[[buttons]]`. After a table header, keys belong to that table. ficha rejects the file with a clear message if this happens.

## Physical positions

| | | | | |
|---|---|---|---|---|
| top row | `west` (□ / X) | `north` (△ / Y) | `r1` (R1 / RB) | `l1` (L1 / LB) |
| bottom row | `south` (× / A) | `east` (○ / B) | `r2` (R2 / RT) | `l2` (L2 / LT) |
| others | `start` | `select` | `l3` | `r3` |

On a typical 8-button arcade stick the top row is west, north, R1, L1 and the bottom row is south, east, R2, L2.

## Backends and their `target`

**`gamepad`** (any game that reads controllers):
- `target` is a button of the virtual Xbox pad: `a b x y lb rb lt rt back start guide l3 r3`.
- Fields:
  - `command`: list or string; without it ficha doesn't launch the game.
  - `process`: executable name, to know when the game is open.
  - `files`: paths, to know whether it's installed.
  - `sdl_filter`: default `true`. ficha launches the game with an SDL hint that hides the physical controllers, so P1/P2 are always ficha's.

**`keyboard`** (any game configurable by keyboard):
- `target` is a key name per side, for example `["KEY_U", "KEY_Z"]`. Key names are in `ficha/codes.py`.
- Fields:
  - `directions`: the directional keys per side.
  - `[system]`: also per side, e.g. `start = ["KEY_1", "KEY_2"]`.
  - `command`, `process`, `files`: same as in `gamepad`.
- Keys go to the focused window; ficha only sends them while the game is open.

**`fbneo-fightcade`:**
- `target` is the input name in FBNeo's `.ini` (`"Weak Punch"` for `P1 Weak Punch`).
- Fields:
  - `rom`: the romset name, e.g. `sfiii3nr1`;
  - `files`: zips in the ROMs folder.
- ficha rewrites the game's `.ini` once (with a backup) to point at its fixed keys. Up to 6 buttons.

**`flycast-fightcade`:**
- `target` is a virtual Xbox button. Flycast maps it to Dreamcast X/Y/A/B/L/R.
- `files`: image names in the Flycast ROMs folder.

**`steam`:**
- `target` is a virtual Xbox button.
- Fields:
  - `appid`;
  - `process`: the game's .exe;
  - `files`: relative to `steamapps/common`;
  - optionally `[backend.display]`, to force fullscreen in Arc System Works' `DisplaySetting.cfg` format.
- Run `ficha steam setup <id>` once (see [troubleshooting](troubleshooting.md)).

## Testing a new game

1. Run `ficha play <id>`.
2. Watch the button lights in the panel.
3. Check in the game's own button-test or training screen that each button does what the panel says.

If the game lets you configure buttons, set it up **once**: P1 = "ficha P1", P2 = "ficha P2", and the buttons matching the `target`s.
