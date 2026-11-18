**Plug-and-play controllers for local fighting game sessions.** / **Controles plug-and-play pra jogatina presencial.**

## Downloads

| File | For |
|---|---|
| `ficha.pyz` | **Linux.** A single file, no dependencies: `python3 ficha.pyz` (Python 3.11+). |
| `ficha-windows-x64.exe` | **Windows (experimental, untested on real hardware).** Needs the [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases) driver; [HidHide](https://github.com/nefarius/HidHide/releases) recommended. |
| `ficha-*.whl` / `ficha-*.tar.gz` | Python package: `pipx install ficha-*.whl` (Windows: `pip install "ficha-*.whl[windows]"`). |

**English:** see the [README](https://github.com/vagnertxr/ficha#readme) and [docs/setup.md](https://github.com/vagnertxr/ficha/blob/main/docs/setup.md) for permissions (Linux needs access to `/dev/uinput`).

**Português:** veja o [README em português](https://github.com/vagnertxr/ficha/blob/main/README.pt-BR.md) e as [instruções de instalação](https://github.com/vagnertxr/ficha/blob/main/docs/setup.pt-BR.md). No Linux, o ficha precisa de acesso ao `/dev/uinput`.

## What's in 0.2.0 / O que tem na 0.2.0

- Automatic P1/P2, per-player and per-game layouts, mapping wizard, web panel. / P1/P2 automático, layout por pessoa e por jogo, mapeamento guiado, painel web.
- Games as TOML files; backends for Fightcade (FBNeo, Flycast), Steam/Proton, and generic `gamepad`/`keyboard`. / Jogos em TOML; backends pro Fightcade (FBNeo, Flycast), Steam/Proton e os genéricos `gamepad`/`keyboard`.
- Built-in: Street Fighter III: 3rd Strike, Marvel vs. Capcom 2 (Dreamcast), Guilty Gear XX Accent Core Plus R.
- `ficha steam setup|configurar`: guided Steam configuration with backups. / configuração guiada da Steam com backup.
- English and Portuguese. / Português e inglês.

ficha does not include or download games or ROMs. / O ficha não inclui nem baixa jogos ou ROMs.
