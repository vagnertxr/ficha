# Instalação e permissões

[English](setup.md)

## Linux

1. **Python 3.11+.** Nenhuma outra dependência.
2. **Instalar:** `pipx install git+https://github.com/vagnertxr/ficha`, ou clone o repositório e rode `python -m ficha`.
3. **Permissões:**
   - **Ler os controles:** o systemd (`uaccess`) já libera os controles pro usuário logado, então não precisa fazer nada.
   - **Criar os dispositivos virtuais:** isso passa pelo `/dev/uinput`. Se o `ficha` disser *Sem acesso a /dev/uinput*, instale a regra:
     ```bash
     sudo cp contrib/60-ficha.rules /etc/udev/rules.d/
     sudo udevadm control --reload && sudo udevadm trigger
     ```
     Pacotes como o `steam-devices` já trazem uma regra equivalente.
4. **Atalho no menu (opcional):** `cp contrib/ficha.desktop ~/.local/share/applications/`.

### Onde fica cada coisa

| O quê | Onde |
|---|---|
| Config | `~/.config/ficha/config.toml` |
| Perfis (controles, jogadores) | `~/.config/ficha/perfis.json` |
| Seus jogos | `~/.config/ficha/games/*.toml` |
| Suas artes (opcional) | `~/.config/ficha/art/<id-do-jogo>.jpg`, mais `<id-do-jogo>-bg.jpg` pro fundo desfocado |

### config.toml

```toml
idioma = "pt"          # "pt" ou "en" (padrão: idioma do sistema)
porta = 7373           # porta do painel
lan = false            # painel também na rede local
fechar_steam = false   # fecha a Steam quando ela agarra um controle e nenhum jogo dela está aberto
[caminhos]
fightcade = "/caminho" # dados do Fightcade (flatpak) ou pasta de instalação (nativo)
steam = "/caminho"     # a pasta que tem steamapps/
```

Fightcade e Steam são detectados sozinhos: primeiro flatpak, depois instalação nativa.

## Windows (experimental)

1. **Python 3.11+**, depois `pip install "ficha[windows] @ git+https://github.com/vagnertxr/ficha"`. Isso instala pysdl2, pysdl2-dll e vgamepad.
2. **Controles virtuais:** instale o driver [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases). O ficha cria o "ficha P1/P2" como controles Xbox 360 virtuais.
3. **Esconder os controles físicos:**
   - **Por que precisa:** o Windows não tem o "agarre exclusivo" do Linux, então os jogos também enxergam os controles físicos e podem pegar um deles como P1.
   - **O que instalar:** o [HidHide](https://github.com/nefarius/HidHide/releases).
   - **Como configurar:** no cliente de configuração dele, esconda seus controles e coloque o Python que roda o ficha na lista de aplicativos liberados.
   - **Opção automática:** com `hidhide = true` no config.toml, o ficha tenta fazer isso sozinho pelo `HidHideCLI.exe`.
4. **Saída de teclado:** vai pelo `SendInput` pra janela em foco.

Essa plataforma foi escrita sem acesso a um PC com Windows. Se algo falhar, abra uma issue com o que aparecer no console.
