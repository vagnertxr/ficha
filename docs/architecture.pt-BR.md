# Como funciona

[English](architecture.md)

```
controles físicos ──> plataforma (Linux: evdev + agarre exclusivo │ Windows: SDL)
                            │  códigos comuns (os códigos do evdev como língua comum)
                            v
              hub (ficha/core.py): P1/P2, perfis por pessoa e por jogo,
                            │      mapeamento, combos, SOCD
                            v
          backend (ficha/backends/*): "botão X do P1" -> saída concreta
                            │
        ┌───────────────────┴──────────────────────┐
  teclado virtual (teclas fixas)          2 controles virtuais "ficha P1/P2"
  uinput │ SendInput                      uinput │ ViGEm
         │                                         │
    FBNeo (.ini aponta pras teclas)      Flycast / Steam / qualquer jogo SDL ou XInput
```

## Decisões e por quê

- **Saídas fixas, em vez de reescrever a config do jogo pra cada pessoa:** a config do jogo é mexida uma vez, e P1/P2 nunca dependem da ordem em que os controles foram plugados.
- **Teclado virtual no FBNeo (Fightcade):**
  - O FBNeo escolhe joystick pelo índice.
  - No wine, o DS4 é lido por hidraw, que não dá pra esconder dele.
  - Tecla é global e fixa.
- **Controles virtuais no Flycast/Steam/SDL:**
  - O Flycast põe o teclado inteiro numa porta só.
  - O SDL respeita `SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT` também pra joystick cru, então o jogo só enxerga "ficha P1" (índice 0) e "ficha P2" (índice 1).
- **Códigos do evdev como língua comum:**
  - Perfis, layouts e o hub são iguais no Linux e no Windows.
  - No Windows, a plataforma traduz SDL → códigos na entrada, e códigos → ViGEm/SendInput na saída.
- **Layout por posição física:** a mesma pessoa tem o mesmo layout em qualquer controle com driver posicional.
- **Saída só com o jogo aberto:** senão o teclado virtual digitaria na janela que estiver em foco.

## Mapa do código

| Arquivo | Papel |
|---|---|
| `ficha/core.py` | o hub |
| `ficha/profiles.py` | identidade, posições, perfis (`perfis.json`) |
| `ficha/games.py` + `ficha/games/*.toml` | definição dos jogos |
| `ficha/backends/` | um módulo por tipo de jogo; `steam_setup.py` + `vdf.py` pra Steam |
| `ficha/platform/` | `linux.py`, `windows.py`, `windows_maps.py` |
| `ficha/web.py` + `ficha/ui/index.html` | painel (HTTP da stdlib + Server-Sent Events) |
| `ficha/i18n.py` + `ficha/locales/` | pt / en |
| `tests/test_unit.py` | testes sem dispositivo (CI) |
| `tests/test_sim.py` | teste de ponta a ponta com controles virtuais uinput (Linux; o ficha tem que estar fechado) |
