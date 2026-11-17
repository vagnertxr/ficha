# Controles e manias dos drivers

[English](controllers.md)

## Quem ganha layout automático

O ficha usa o layout padrão do TOML do jogo quando confia nas **posições** dos botões que o driver informa:

| Driver (Linux) | Controles | Observação |
|---|---|---|
| `playstation` / `sony` | DualShock 4, DualSense, a maioria dos arcades PS4/PS5 no modo PS | segue a convenção posicional do kernel |
| `xpad` / `xone` / `xpadneo` | controles Xbox, arcades e boxes XInput, GP2040-CE em modo XInput | **mania:** informa o X do Xbox (oeste) como `BTN_X` = `BTN_NORTH`; o ficha corrige |
| `hid-microsoft` | alguns controles Xbox por Bluetooth | |
| `sdl-gamecontroller` (Windows) | tudo que o SDL conhece | o SDL já normaliza as posições |

Os outros passam pelo **mapeamento guiado** (8 toques). Isso inclui o `hid-generic`: placas DInput genéricas, GP2040-CE em modo DInput, placas Brook que aparecem como "ZEROPLUS P4". O mapeamento fica salvo.

## Identidade: como o ficha reconhece "o seu" controle

1. `uniq` (o DS4/DualSense informa o endereço MAC): único por controle.
2. Número de série USB: único por controle.
3. Senão, fabricante:produto + nome: compartilhado entre modelos iguais. O painel mostra o selo "por modelo".

## Manias conhecidas

- **Gatilhos analógicos:**
  - xpad: LT/RT são eixos (`ABS_Z`/`ABS_RZ`, 0–255).
  - hid-playstation: L2/R2 vêm como botão **e** como eixo. O mapeamento prefere o botão.
- **Placas Brook no modo PS4/PS5, via hid-generic:**
  - L2/R2 ficam em `ABS_RX`/`ABS_RY` e repousam em **0**, não no meio.
  - O ficha pega o repouso de cada eixo do momento em que o controle é plugado. Então não segure nada ao plugar.
- **Raspberry Pi Pico (GP2040-CE):**
  - O modo XInput é o mais fácil: usa o `xpad` e ganha layout automático.
  - O modo teclado não funciona: o ficha lê controles, não teclados.
- **Controles virtuais da Steam (28de:11ff):**
  - O ficha ignora, porque espelham um controle físico que ele já lê.
  - Veja [problemas comuns](troubleshooting.pt-BR.md) pra quando a Steam agarra controles.
- **SOCD:** esquerda+direita = neutro, cima+baixo = cima (padrão de torneio), em todas as saídas.
