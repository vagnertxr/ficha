# Setup and permissions

[Português](setup.pt-BR.md)

## Linux

1. **Python 3.11+.** No other dependency.
2. **Install:** `pipx install git+https://github.com/vagnertxr/ficha`, or clone the repo and run `python -m ficha`.
3. **Permissions:**
   - **Reading controllers:** gamepads get read access for the logged-in user through systemd (`uaccess`), so nothing to do there.
   - **Creating virtual devices:** this goes through `/dev/uinput`. If `ficha` says *No access to /dev/uinput*, install the rule:
     ```bash
     sudo cp contrib/60-ficha.rules /etc/udev/rules.d/
     sudo udevadm control --reload && sudo udevadm trigger
     ```
     Packages like `steam-devices` ship an equivalent rule.
4. **Optional menu entry:** `cp contrib/ficha.desktop ~/.local/share/applications/`.

### Where things live

| What | Where |
|---|---|
| Config | `~/.config/ficha/config.toml` |
| Profiles (controllers, players) | `~/.config/ficha/perfis.json` |
| Your own games | `~/.config/ficha/games/*.toml` |
| Your own art (optional) | `~/.config/ficha/art/<game-id>.jpg`, plus `<game-id>-bg.jpg` for the blurred backdrop |

### config.toml

```toml
idioma = "en"          # "pt" or "en" (default: system language)
porta = 7373           # panel port
lan = false            # serve the panel on the local network
fechar_steam = false   # close Steam when it grabs a controller and no Steam game is running
[caminhos]
fightcade = "/path"    # Fightcade data (flatpak) or install folder (native)
steam = "/path"        # the folder that contains steamapps/
```

Fightcade and Steam are detected automatically: flatpak first, then native installs.

## Windows (experimental)

1. **Python 3.11+**, then `pip install "ficha[windows] @ git+https://github.com/vagnertxr/ficha"`. This pulls in pysdl2, pysdl2-dll and vgamepad.
2. **Virtual controllers:** install the [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases) driver. ficha creates its "ficha P1/P2" as virtual Xbox 360 controllers.
3. **Hiding physical controllers:**
   - **Why it's needed:** Windows has no exclusive grab like Linux, so games see the physical controllers too and may pick one of them as P1.
   - **What to install:** [HidHide](https://github.com/nefarius/HidHide/releases).
   - **Configuring it:** in its configuration client, hide your controllers and add the Python running ficha to the allowed applications.
   - **Automatic option:** with `hidhide = true` in config.toml, ficha tries to do this itself through `HidHideCLI.exe`.
4. **Keyboard output:** goes through `SendInput` to the focused window.

This platform was written without access to a Windows PC. If something fails, please open an issue with the console output.
