"""Painel local: HTML + Server-Sent Events + API JSON, só stdlib."""

import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import backends, config, i18n
from .backends import steam
from .games import GAMES
from .i18n import t

UI = os.path.join(os.path.dirname(__file__), "ui", "index.html")
ART_RE = re.compile(r"^/art/[a-z0-9_-]+\.jpg$")


def any_running():
    return backends.any_running(GAMES.values())


class Panel:
    def __init__(self, hub):
        self.hub = hub
        self.game_state = {"running": False, "ini_ok": False}
        self._refresh_game()

    @property
    def game(self):
        return self.hub.game

    @property
    def emu(self):
        return backends.get(self.hub.game.backend_type)

    def _refresh_game(self):
        self.game_state = {"running": self.emu.is_running(self.game), "ini_ok": not self.emu.check(self.game)}
        self.hub.set_output(self.game_state["running"])

    def watch_game(self):
        while True:
            before = dict(self.game_state)
            self._refresh_game()
            # O FBNeo regrava o .ini ao fechar: se ele foi aberto com a config
            # antiga (antes do ficha subir), desfaz a nossa. Conserta assim que fecha.
            if not self.game_state["running"] and not self.game_state["ini_ok"]:
                self.emu.install(self.game)
                self.hub.log(t("log.config_reapplied"))
                self._refresh_game()
            self._free_from_steam()
            if self.game_state != before:
                self.hub.bump()
            time.sleep(1)

    def _free_from_steam(self):
        """A Steam (Steam Input) pode agarrar controles, e aí os botões não chegam
        no ficha. Com `fechar_steam = true` na config e nenhum jogo da Steam
        aberto, fecha a Steam; o hub tenta agarrar de novo a cada scan."""
        if not config.CONFIG.get("fechar_steam"):
            return
        held = [p for p in list(self.hub.pads.values()) if not p.dev.grabbed]
        if not held or steam.is_running() or not steam.client_running():
            return
        if time.monotonic() - getattr(self, "_steam_closed_at", -60) < 30:
            return
        self._steam_closed_at = time.monotonic()
        steam.shutdown_client()
        self.hub.log(t("log.closed_steam", pads=", ".join(self.hub.label(p) for p in held)))

    def state(self):
        s = self.hub.snapshot()
        s["game"].update(self.game_state)
        return s

    def action(self, name, body):
        hub = self.hub
        pad = hub.pads.get(body.get("pad", ""))
        if name == "swap":
            hub.swap()
        elif name == "player" and pad:
            hub.set_player(pad, str(body.get("player", "")))
        elif name == "game":
            if any_running():
                hub.log(t("log.close_game_first"))
            else:
                hub.set_game(body.get("game"))
        elif name == "rename" and pad:
            hub.rename(pad, str(body.get("alias", "")))
        elif name == "remap" and pad:
            hub.start_wizard(pad)
        elif name == "cancel" and pad:
            hub.cancel_wizard(pad)
        elif name == "reset" and pad:
            hub.reset_mapping(pad)
        elif name == "assign" and pad:
            slot = body.get("slot")
            hub.assign(pad, slot if slot in (0, 1) else None)
        elif name == "launch" and any_running():
            hub.log(t("log.already_open"))
        elif name == "launch":
            mode = "training" if body.get("mode") == "training" and hub.game.training else "play"
            if self.emu.check(self.game):
                self.emu.install(self.game)
            if self.emu.launch(self.game, mode) is None and not self.emu.is_running(self.game):
                hub.log(t("log.cannot_launch", game=hub.game.short))
            else:
                hub.log(t("log.opening_training" if mode == "training" else "log.opening", game=hub.game.short))
        elif name == "stop":
            for g in GAMES.values():
                backends.get(g.backend_type).stop(g)
            hub.log(t("log.closing_game"))
        elif name == "lang" and body.get("lang") in i18n.LANGS:
            i18n.set_lang(body["lang"])
            hub.store.data["idioma"] = body["lang"]
            hub.store.save()
            hub.log(t("log.lang"))
        elif name == "quit":
            hub.log(t("log.quitting"))
            hub.running = False
        elif name == "install":
            self.emu.install(self.game)
            hub.log(t("log.config_applied", game=self.game.short))
        else:
            return False
        self._refresh_game()
        hub.bump()
        return True

    def handler(self):
        panel = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json"):
                data = body.encode() if isinstance(body, str) else body
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    self._send(200, open(UI, "rb").read(), "text/html; charset=utf-8")
                elif self.path == "/i18n.json":
                    self._send(200, json.dumps({"lang": i18n.lang(), "t": i18n.table()}))
                elif ART_RE.match(self.path):
                    try:
                        data = open(os.path.join(config.config_dir(), "art", self.path[5:]), "rb").read()
                    except OSError:
                        return self._send(404, "{}")
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=3600")
                    self.end_headers()
                    self.wfile.write(data)
                elif self.path == "/state":
                    self._send(200, json.dumps(panel.state()))
                elif self.path == "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    seen = -1
                    try:
                        while True:
                            with panel.hub.changed:
                                if panel.hub.version == seen:
                                    panel.hub.changed.wait(10)
                            seen = panel.hub.version
                            self.wfile.write(b"data: " + json.dumps(panel.state()).encode() + b"\n\n")
                            self.wfile.flush()
                            time.sleep(1 / 30)  # luzes dos botões a 30 fps no máximo
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                else:
                    self._send(404, "{}")

            def do_POST(self):
                if not self.path.startswith("/api/"):
                    return self._send(404, "{}")
                # Só aceita do próprio painel (evita página aleatória mexendo via CSRF).
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self._send(415, "{}")
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(n) or b"{}")
                except ValueError:
                    return self._send(400, "{}")
                ok = panel.action(self.path[5:], body if isinstance(body, dict) else {})
                self._send(200 if ok else 400, json.dumps({"ok": ok}))

        return H

    def serve(self, host, port):
        httpd = ThreadingHTTPServer((host, port), self.handler())
        httpd.daemon_threads = True
        threading.Thread(target=self.watch_game, daemon=True).start()
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd
