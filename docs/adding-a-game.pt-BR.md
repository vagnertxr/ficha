# Adicionando um jogo

[English](adding-a-game.md)

## Onde fica o arquivo

Cada jogo é um arquivo TOML:
- **Jogos que já vêm prontos:** em `ficha/games/`.
- **Os seus:** em `~/.config/ficha/games/`. Um arquivo seu com o mesmo `id` substitui o que vem pronto.

Rode `ficha jogos` pra conferir se ele carregou. Erros (chave desconhecida, layout citando botão que não existe…) aparecem ao subir, e o arquivo é ignorado.

Há exemplos prontos pra copiar em [`docs/examples/`](examples/).

## Estrutura

```toml
id = "sf2-retroarch"            # único, usado nos comandos (ficha jogar sf2-retroarch)
title = "Street Fighter II"
short = "SF2"                   # nome curto no painel
year = 1991                     # opcional
accent = "#3fa7ff"              # cor no painel
training = false                # o backend tem modo treino? (só FBNeo/Fightcade)
optional = []                   # botões que o mapeamento deixa pular
grid = [["lp", "mp", "hp"], ["lk", "mk", "hk"]]   # como os botões aparecem no painel (fileiras)

[backend]
type = "gamepad"                # fbneo-fightcade | flycast-fightcade | steam | gamepad | keyboard
# ...campos do backend (abaixo)

[[buttons]]                     # um bloco por botão, na ordem
id = "lp"
short = "LP"
name = { pt = "Soco fraco", en = "Light Punch" }   # ou um texto só
target = "x"                    # o que o botão aperta (depende do backend); pode ser ["P1", "P2"]

[layout]                        # layout padrão por posição física
lp = "west"
mp = "north"
hp = "r1"
lk = "south"
mk = "east"
hk = "r2"

[macros.3p]                     # opcional: um botão do controle aperta vários
name = { pt = "3 socos", en = "3 punches" }
buttons = ["lp", "mp", "hp"]

[system]                        # o que START e SELECT apertam (padrão: start = "start")
start = "start"
coin = "back"
```

> **Pegadinha do TOML:** chaves soltas (`grid`, `optional`…) têm que vir **antes** do primeiro `[backend]` ou `[[buttons]]`. Depois de um cabeçalho de tabela, as chaves passam a pertencer a ela. Se isso acontecer, o ficha recusa o arquivo com uma mensagem clara.

## Posições físicas

| | | | | |
|---|---|---|---|---|
| fileira de cima | `west` (□ / X) | `north` (△ / Y) | `r1` (R1 / RB) | `l1` (L1 / LB) |
| fileira de baixo | `south` (× / A) | `east` (○ / B) | `r2` (R2 / RT) | `l2` (L2 / LT) |
| outros | `start` | `select` | `l3` | `r3` |

Num arcade comum de 8 botões, a fileira de cima é west, north, R1, L1 e a de baixo é south, east, R2, L2.

## Backends e o `target`

**`gamepad`** (qualquer jogo que lê controle):
- O `target` é um botão do controle Xbox virtual: `a b x y lb rb lt rt back start guide l3 r3`.
- Campos:
  - `command`: lista ou texto; sem ele, o ficha não abre o jogo.
  - `process`: nome do executável, pra saber se o jogo está aberto.
  - `files`: caminhos, pra saber se está instalado.
  - `sdl_filter`: padrão `true`. O ficha abre o jogo com um aviso pro SDL que esconde os controles físicos, então P1/P2 são sempre os do ficha.

**`keyboard`** (qualquer jogo configurável por teclado):
- O `target` é o nome da tecla de cada lado, por exemplo `["KEY_U", "KEY_Z"]`. Os nomes estão em `ficha/codes.py`.
- Campos:
  - `directions`: as teclas de direção de cada lado.
  - `[system]`: também por lado, como `start = ["KEY_1", "KEY_2"]`.
  - `command`, `process`, `files`: iguais aos do `gamepad`.
- As teclas vão pra janela em foco; o ficha só aperta com o jogo aberto.

**`fbneo-fightcade`:**
- O `target` é o nome do input no `.ini` do FBNeo (`"Weak Punch"` pra `P1 Weak Punch`).
- Campos:
  - `rom`: o nome do romset, como `sfiii3nr1`;
  - `files`: os zips na pasta de ROMs.
- O ficha reescreve o `.ini` do jogo uma vez (com backup) pra apontar pras teclas fixas dele. Até 6 botões.

**`flycast-fightcade`:**
- O `target` é um botão Xbox virtual. O Flycast traduz pra X/Y/A/B/L/R do Dreamcast.
- `files`: os nomes das imagens na pasta de ROMs do Flycast.

**`steam`:**
- O `target` é um botão Xbox virtual.
- Campos:
  - `appid`;
  - `process`: o .exe do jogo;
  - `files`: relativos a `steamapps/common`;
  - opcional `[backend.display]`, pra forçar tela cheia no formato `DisplaySetting.cfg` da Arc System Works.
- Rode `ficha steam configurar <id>` uma vez (veja [problemas comuns](troubleshooting.pt-BR.md)).

## Testando um jogo novo

1. Rode `ficha jogar <id>`.
2. Olhe as luzes dos botões no painel.
3. Confira, na tela de teste de botões ou no modo treino do jogo, se cada botão faz o que o painel diz.

Se o jogo deixa configurar os botões, configure **uma vez**: P1 = "ficha P1", P2 = "ficha P2", e os botões batendo com os `target`s.
