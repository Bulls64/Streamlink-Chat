"""Comptes Twitch et Kick : connexion, déconnexion, vérification.

Twitch and Kick accounts: login, logout, check."""
import logging
import threading
import time
import tkinter as tk
import webbrowser

from . import auth, config
from .ui.widgets import Button

log = logging.getLogger("streamlink_launcher")


class AccountsMixin:
    """Comptes Twitch et Kick : connexion, déconnexion, vérification.

    Twitch and Kick accounts: login, logout, check."""

    # --- comptes
    # --- accounts
    def login(self, platform, client_id, secret=""):
        t = self.t
        if not client_id or (platform == "kick" and not secret):
            self.toast(t("chat_need_client_id"), "warn")
            return
        acc = self.cfg["accounts"].setdefault(platform, {})
        acc["client_id"] = client_id
        if secret:
            acc["client_secret"] = secret
        config.save(self.cfg)
        self._login_cancel = cancel = threading.Event()
        if platform == "twitch":
            self.run_in_thread(lambda: auth.twitch_device_start(client_id),
                               lambda r: self._twitch_device(client_id, r, cancel))
        else:
            page = ("<html><body style='font-family:sans-serif;background:#141518;color:#EDEDEF;padding:40px'>"
                    f"<h2>Streamlink Chat</h2><p>{t('chat_login_browser_done')}</p></body></html>").encode()
            self.toast(t("chat_login_browser"), duration=6000)
            self.run_in_thread(lambda: auth.kick_login(client_id, secret, webbrowser.open, cancel, page=page),
                               lambda r: self._login_done("kick", r))

    def _twitch_device(self, client_id, device, cancel):
        t, c, px = self.t, self.c, self.px
        if isinstance(device, Exception):
            log.warning("Twitch device : %s", device)
            self.toast(t("chat_login_failed", platform="Twitch"), "error")
            return
        uri = device.get("verification_uri") or "https://www.twitch.tv/activate"

        def body(b):
            tk.Label(b, text=t("chat_device_intro"), font=self.fonts.body, bg=c.panel, fg=c.text, justify="left",
                     wraplength=px(320), anchor="w").pack(anchor="w")
            code = tk.Label(b, text=device.get("user_code", ""), font=self.fonts.title, bg=c.panel, fg=c.text)
            code.pack(anchor="w", pady=(px(18), px(18)))
            row = tk.Frame(b, bg=c.panel)
            row.pack(fill="x")
            Button(row, self, text=t("chat_device_open"), icon="link", kind="primary", height=40,
                   accent=config.PLATFORMS["twitch"][1:], command=lambda: self.open_url(uri)).pack(side="left")

            def copy():
                self.clipboard_clear()
                self.clipboard_append(device.get("user_code", ""))
                self.toast(t("chat_copied"))
            Button(row, self, text=t("chat_device_copy"), kind="secondary", height=40, command=copy).pack(
                side="left", padx=(px(8), 0))
            self._hint(b, t("chat_device_wait"))
        self.open_panel("login", t("chat_login", platform="Twitch"), body)
        self._login_cancel = cancel
        self.open_url(uri)
        self.run_in_thread(lambda: auth.twitch_device_poll(client_id, device, cancel),
                           lambda r: self._login_done("twitch", r))

    def _login_done(self, platform, result):
        t = self.t
        if isinstance(result, Exception):
            if str(result) != "cancelled":
                log.warning("Connexion %s : %s", platform, result)
                key = "chat_login_port" if str(result) == "port" else "chat_login_failed"
                self.toast(t(key, platform=self.platform_name(platform), port=auth.KICK_PORT), "error")
            return
        acc = self.cfg["accounts"].setdefault(platform, {})
        acc.update(result)
        config.save(self.cfg)
        if self.panel_kind == "login":
            self.close_panel()
        elif self.panel_kind == "settings":
            self.open_settings(section="accounts")
        self.toast(t("chat_login_ok", platform=self.platform_name(platform), name=result.get("login") or "?"))
        self.restart_connection(platform)

    def logout(self, platform):
        acc = self.cfg["accounts"].get(platform) or {}
        self.cfg["accounts"][platform] = {k: v for k, v in acc.items() if k in ("client_id", "client_secret")}
        config.save(self.cfg)
        self.restart_connection(platform)
        if self.panel_kind == "settings":
            self.open_settings(section="accounts")

    def _check_accounts(self):
        """Au démarrage : vérifie / renouvelle les jetons enregistrés (hors de l'interface).

        At start-up: checks / renews the saved tokens (outside the interface)."""
        tw = self.cfg["accounts"].get("twitch") or {}
        if tw.get("access_token"):
            self.run_in_thread(lambda: auth.twitch_ensure(tw), lambda r: self._account_checked("twitch", tw, r))
        kk = self.cfg["accounts"].get("kick") or {}
        if kk.get("access_token") and kk.get("refresh_token") and kk.get("expires_at", 0) < time.time() + 300:
            self.run_in_thread(lambda: auth.kick_refresh(kk), lambda r: self._account_checked("kick", kk, r))

    def _account_checked(self, platform, old, result):
        if isinstance(result, Exception):
            return  # réseau indisponible : on garde le jeton, la connexion le dira
                    # network unavailable: the token is kept, the connection will tell
        if result is None:
            self.cfg["accounts"][platform] = {k: v for k, v in old.items() if k in ("client_id", "client_secret")}
            self.toast(self.t("chat_auth_failed", platform=self.platform_name(platform)), "warn")
        elif result != old:
            self.cfg["accounts"][platform] = result
        else:
            return
        config.save(self.cfg)
        self.restart_connection(platform)
