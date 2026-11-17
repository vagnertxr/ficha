# Problemas comuns

[English](troubleshooting.md)

## Os botões digitam letras em outras janelas
**Causa:** nos jogos por teclado (FBNeo/`keyboard`), o ficha aperta teclas num teclado virtual, e a tecla vai pra janela que estiver em foco.

**O que o ficha faz:** só manda tecla **com o jogo aberto**.

**O que sobra:** se você trocar de janela no meio do jogo, os botões vão parar na outra janela.

## Um controle não faz nada e o painel diz "segurado por outro programa"
**Causa:** outro programa pegou o controle com exclusividade antes, geralmente a Steam (Steam Input).

**Solução, qualquer uma destas:**
- Feche a Steam quando não for jogar algo dela.
- Desligue o Steam Input pra esse tipo de controle nas configurações de controle da Steam.
- Ponha `fechar_steam = true` no config.toml, e o ficha fecha a Steam quando nenhum jogo dela estiver aberto.

O ficha assume o controle assim que ele é liberado.

## Jogo da Steam: só um jogador funciona, ou um jogador vira o teclado
**Causa:**
- Com o Steam Input ligado, a Steam embrulha todo controle (inclusive os virtuais do ficha) em controles virtuais dela (`28de:11ff`).
- No Linux, o Proton coloca esses na frente dos do ficha.

**Solução:**
```bash
ficha steam configurar <jogo> --steam-input-global off
```
Isso desliga o Steam Input nesse jogo, põe a opção de inicialização do ficha e desliga o Steam Input globalmente pra controles Xbox/PlayStation/Switch/genéricos. A parte global vale pra todos os jogos da Steam. O comando mostra cada mudança, faz backup e pergunta antes.

## Jogo da Steam (Linux): janela preta, "não está respondendo"
**Causa:** algumas versões do Proton travam alguns jogos na abertura. O Guilty Gear XX AC+R travava no Proton Experimental 11 (outubro de 2026) em qualquer modo de tela, inclusive em janela.

**Solução:** teste outro Proton:
```bash
ficha steam configurar <jogo> --proton proton_9
```
**Regra prática:** se um jogo da Steam travar, teste outro Proton **antes** de mexer em controle ou em tela.

## Jogo do FBNeo ignora os controles depois de ser aberto por fora do ficha
**Causa:** o FBNeo regrava o `.ini` do jogo ao fechar. Se ele foi aberto com a config antiga, desfaz a do ficha.

**Solução:** não precisa fazer nada. O ficha reaplica a config assim que o jogo fecha; enquanto isso, o painel mostra um aviso com o botão "Consertar". Pra voltar à config original:
```bash
ficha restaurar <jogo>
```

## Sem acesso a /dev/uinput
Veja [instalação](setup.pt-BR.md): instale o `contrib/60-ficha.rules`.

## O mapeamento não aceita nenhum botão
**Causa:** um eixo que não repousa onde o ficha espera fica parecendo "apertado", e o mapeamento espera tudo ser solto.

**O que o ficha faz:** pega o repouso de cada eixo na hora em que o controle é plugado.

**Solução:** desplugue o controle, plugue de novo **sem segurar nada** e recomece o mapeamento. Se continuar, abra uma issue com a saída de `cat /proc/bus/input/devices` pro controle.

## Diagnosticando um jogo da Steam/Proton
Crie o arquivo `ficha-debug` no `$HOME` que a Steam enxerga (na Steam flatpak: `~/.var/app/com.valvesoftware.Steam/`). Com ele, o script de inicialização do ficha liga o `PROTON_LOG=1`, e o log vai pra `steam-<appid>.log` na mesma pasta. Apague o arquivo quando terminar.
