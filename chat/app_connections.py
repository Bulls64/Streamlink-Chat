"""Chat affiché, connexions aux plateformes et file d'événements.

Displayed chat, platform connections and event queue."""
import logging
import queue
import tkinter as tk

from . import config
from .app_view import ChatView
from .common import mentions
from .kick import KickManager
from .steam import SteamManager
from .twitch import TwitchConnection
from .ui.widgets import Button

log = logging.getLogger("streamlink_launcher")


class ConnectionsMixin:
    """Chat affiché, connexions aux plateformes et file d'événements.

    Displayed chat, platform connections and event queue."""

    # --- vue du chat courant
    # --- view of the current chat
    def refresh_current(self):
        tab = self.current
        self._anims_dirty = True  # animations du nouveau chat affiché / animations of the newly displayed chat
        accent = self.accent
        self.input.set_accent(accent)
        self.send_btn.set_accent(accent)
        self._paint_card()
        if not tab:
            self.header.pack_forget()
            self.header_sep.pack_forget()
            self.empty.pack(fill="both", expand=True)
            self._update_input()
            self.apply_chrome()
            return
        self.empty.pack_forget()
        if not self.header.winfo_ismapped():
            self.header_sep.pack(fill="x", pady=(self.px(8), 0), before=self.views_box)
            self.header.pack(fill="x", padx=(self.px(14), self.px(8)), pady=(self.px(8), 0),
                             before=self.header_sep)
        if tab.view is None:
            tab.view = ChatView(self, self.views_box, tab)
            if tab.history:
                tab.view.add(list(tab.history))
        tab.view.frame.pack(fill="both", expand=True)
        tab.view.scroll_to_end()
        self.update_header()
        self._update_input()
        self.apply_chrome()

    def update_header(self):
        tab = self.current
        if not tab:
            return
        c, t = self.c, self.t
        self.header_title.configure(text=tab.title)
        status = {"connecting": (t("chat_status_connecting"), c.muted),
                  "reconnecting": (t("chat_status_reconnecting"), c.warn),
                  "error": (self._error_text(tab), c.error)}.get(tab.status)
        if tab.status == "connected":
            conn = self.conns.get(tab.platform)
            status = (t("chat_status_rw") if conn and conn.can_send else t("chat_status_ro"), c.ok)
        text, color = status or ("", c.muted)
        self.header_status.configure(text=f"●  {self.platform_name(tab.platform)} · {text}", fg=color)

    def _error_text(self, tab):
        d, t = tab.detail, self.t
        if d == "blocked":
            return t("chat_err_blocked")
        if d == "not_found":
            return t("chat_err_not_found")
        if d == "offline":
            return t("chat_err_offline")
        return t("chat_status_error")

    def update_more_button(self, view):
        if view is not (self.current.view if self.current else None):
            return
        if view.at_bottom:
            if self.more_btn is not None:
                self.more_btn.place_forget()
            return
        if self.more_btn is None or not self.more_btn.winfo_exists():
            self.more_btn = Button(self.views_box, self, text=self.t("chat_more"), icon="arrow_down",
                                   command=lambda: self.current and self.current.view and
                                   self.current.view.scroll_to_end(), kind="primary", height=32,
                                   accent=self.accent, radius=16, font=self.fonts.small_semi, icon_size=12, pad=14)
        self.more_btn.set_accent(self.accent)
        self.more_btn.place(relx=0.5, rely=1.0, y=-self.px(12), anchor="s")
        tk.Misc.lift(self.more_btn)

    def _update_input(self):
        tab, t = self.current, self.t
        conn = self.conns.get(tab.platform) if tab else None
        can = bool(tab and conn and conn.can_send and tab.status == "connected")
        if not tab:
            hint = t("chat_input_none")
        elif tab.platform == "steamtv":
            hint = t("chat_input_steam")
        elif not (conn and conn.can_send):
            hint = t("chat_input_login", platform=self.platform_name(tab.platform))
        elif not can:
            hint = t("chat_status_connecting")
        else:
            hint = t("chat_input_placeholder", channel=tab.title)
        self.input.set_placeholder(hint)
        self.input.set_disabled(not can)
        self.send_btn.set_disabled(not can)
        self._input_needs_login = bool(tab and tab.platform != "steamtv" and not (conn and conn.can_send))

    def _input_click(self, e):
        if getattr(self, "_input_needs_login", False):
            self.open_settings(section="accounts")

    # =====================================================
    # Connexions et événements
    # Connections and events
    # =====================================================
    def _connection(self, platform):
        conn = self.conns.get(platform)
        if conn is not None:
            return conn
        emit = self.events.put
        if platform == "twitch":
            acc = self.cfg["accounts"].get("twitch") or {}
            conn = TwitchConnection(emit, acc.get("login"), acc.get("access_token"),
                                    emote_lookup=lambda ch: self.emote_maps.get(("twitch", ch), self.global_emotes),
                                    theme="dark" if self.c.dark else "light")
        elif platform == "kick":
            acc = self.cfg["accounts"].get("kick") or {}
            conn = KickManager(emit, acc.get("access_token"),
                               emote_lookup=lambda ch: self.emote_maps.get(("kick", ch), {}))
        else:
            conn = SteamManager(emit)
        self.conns[platform] = conn.start()
        return conn

    def restart_connection(self, platform):
        old = self.conns.pop(platform, None)
        if old:
            old.stop()
        tabs = [t for t in self.tabs if t.platform == platform]
        if tabs:
            conn = self._connection(platform)
            for tab in tabs:
                conn.join(tab.channel)
        self._update_input()
        self.update_header()

    def reconnect(self, tab):
        conn = self.conns.get(tab.platform)
        if conn:
            conn.part(tab.channel)
            conn.join(tab.channel)

    def _tab(self, platform, channel):
        return next((t for t in self.tabs if t.platform == platform and t.channel == channel), None)

    def _pump(self):
        batches = {}
        try:
            for _ in range(800):
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "message":
                    msg = ev[1]
                    if msg.channel == "*":  # avis général de Twitch : chat courant
                                            # general notice from Twitch: current chat
                        if self.current and self.current.platform == msg.platform:
                            msg.channel = self.current.channel
                        else:
                            continue
                    tab = self._tab(msg.platform, msg.channel)
                    if tab:
                        tab.history.append(msg)
                        batches.setdefault(tab.key, (tab, []))[1].append(msg)
                elif kind == "call":
                    try:
                        ev[1](ev[2])
                    except tk.TclError:
                        pass
                else:
                    self._event(ev, batches)
        except queue.Empty:
            pass
        for tab, msgs in batches.values():
            if tab.view:
                tab.view.add(msgs)
            if tab is not self.current:
                tab.unread += sum(1 for m in msgs if m.kind == "msg")
                if any(m.kind == "msg" and self.is_mention(tab, m) for m in msgs):
                    tab.mentioned = True
                w = self.tab_widgets.get(tab.key)
                if w:
                    w.refresh()
        if any(tab is not self.current for tab, _ in batches.values()):
            self._flow_tabs()
        self.after(40, self._pump)

    def _event(self, ev, batches):
        kind = ev[0]
        if kind == "open":
            for platform, channel in ev[1]:
                self.open_tab(platform, channel)
            self.deiconify()
            self.lift()
            self.focus_force()
            return
        if kind == "auth_failed":
            self.toast(self.t("chat_auth_failed", platform=self.platform_name(ev[1])), "error")
            self.cfg["accounts"][ev[1]] = {k: v for k, v in self.cfg["accounts"][ev[1]].items()
                                          if k in ("client_id", "client_secret")}
            config.save(self.cfg)
            self.after(100, lambda: self.restart_connection(ev[1]))
            return
        platform, channel = ev[1], ev[2]
        tab = self._tab(platform, channel)
        if tab is None:
            return
        if kind == "status":
            tab.status, tab.detail = ev[3], ev[4]
            w = self.tab_widgets.get(tab.key)
            if w:
                w.redraw()
            if tab is self.current:
                self.update_header()
                self._update_input()
        elif kind == "room":
            info = ev[3]
            tab.info.update(info)
            if info.get("name") and info["name"] != tab.title:
                tab.title = info["name"]
                self.build_tabs()
                if tab is self.current:
                    self.update_header()
            self._load_channel_emotes(tab)
        elif kind == "delete" and tab.view:
            self._flush(tab, batches)
            tab.view.delete_message(ev[3])
        elif kind == "clear_user" and tab.view:
            self._flush(tab, batches)
            tab.view.clear_user(ev[3])
        elif kind == "clear":
            from .common import ChatMessage
            msg = ChatMessage(platform, channel, text=self.t("chat_cleared"), kind="notice",
                              fragments=[("text", self.t("chat_cleared"))])
            tab.history.append(msg)
            batches.setdefault(tab.key, (tab, []))[1].append(msg)

    def _flush(self, tab, batches):
        """Affiche les messages en attente avant une suppression qui pourrait les viser.

        Shows the pending messages before a deletion that could target them."""
        pending = batches.pop(tab.key, None)
        if pending and tab.view:
            tab.view.add(pending[1])

    def is_mention(self, tab, msg):
        names = []
        acc = self.cfg["accounts"].get(tab.platform) or {}
        if acc.get("login"):
            names.append(acc["login"])
        if msg.own or not (names or self.cfg["highlights"]):
            return False
        return mentions(msg.fragments, names, self.cfg["highlights"])
