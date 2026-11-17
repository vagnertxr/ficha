# Troubleshooting

[Português](troubleshooting.pt-BR.md)

## Buttons type letters into other windows
**Cause:** in keyboard-backed games (FBNeo/`keyboard`), ficha presses keys on a virtual keyboard, and keys go to whatever window has focus.

**What ficha does about it:** it only sends keys **while the game is running**.

**What's left:** if you alt-tab away mid-game, presses will land in the other window.

## A controller does nothing; the panel says "held by another program"
**Cause:** another program took exclusive access first, usually Steam (Steam Input).

**Fix, any one of these:**
- Close Steam when you're not playing a Steam game.
- Turn off Steam Input for that controller type in Steam's controller settings.
- Set `fechar_steam = true` in config.toml, so ficha closes Steam when no Steam game is running.

ficha takes over as soon as the controller is released.

## Steam game: only one player works, or a player becomes the keyboard
**Cause:**
- With Steam Input on, Steam wraps every controller (including ficha's virtual ones) into its own virtual pads (`28de:11ff`).
- On Linux, Proton puts those first, ahead of ficha's.

**Fix:**
```bash
ficha steam setup <game> --steam-input-global off
```
This turns Steam Input off for that game, adds ficha's launch option, and turns it off globally for Xbox/PlayStation/Switch/generic controllers. The global part affects every Steam game. The command shows every change, backs files up and asks first.

## Steam game (Linux): black window, "not responding"
**Cause:** some Proton versions hang some games at startup. Guilty Gear XX AC+R hung on Proton Experimental 11 (October 2026) in every display mode, windowed included.

**Fix:** try another Proton:
```bash
ficha steam setup <game> --proton proton_9
```
**Rule of thumb:** if a Steam game hangs, test another Proton **before** touching controllers or display settings.

## FBNeo game ignores the controllers after it was opened outside ficha
**Cause:** FBNeo rewrites the game's `.ini` when it closes. If it was opened with the old config, it undoes ficha's.

**Fix:** none needed. ficha re-applies the config as soon as the game closes; the panel shows a warning with a "Fix" button meanwhile. To go back to the original config:
```bash
ficha restore <game>
```

## No access to /dev/uinput
See [setup](setup.md): install `contrib/60-ficha.rules`.

## The mapping wizard doesn't accept any button
**Cause:** an axis that doesn't rest where ficha expects keeps looking "pressed", and the wizard waits for everything to be released.

**What ficha does about it:** it takes the rest value at plug-in time.

**Fix:** unplug the controller, plug it back in **without holding anything**, and start the mapping again. If it persists, open an issue with the output of `cat /proc/bus/input/devices` for the controller.

## Diagnosing a Steam/Proton game
Create the file `ficha-debug` in the `$HOME` that Steam sees (in the Steam flatpak: `~/.var/app/com.valvesoftware.Steam/`). With it, ficha's launch script turns on `PROTON_LOG=1`, and the log goes to `steam-<appid>.log` in the same folder. Delete the file when done.
