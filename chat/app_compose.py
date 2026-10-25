"""Envoi de messages, complétion, menus contextuels et lancement du stream.

Sending messages, completion, context menus and launching the stream."""
import logging
import subprocess
import tkinter as tk

from . import config, core

log = logging.getLogger("streamlink_launcher")


class ComposeMixin:
    """Envoi de messages, complétion, menus contextuels et lancement du stream.

    Sending messages, completion, context menus and launching the stream."""

    # Envoi
    # Sending
    # =====================================================
    def send(self):
        tab = self.current
        text = self.input_var.get().strip()
        if not tab or not text:
            return "break"
        conn = self.conns.get(tab.platform)
        if not conn or not conn.can_send:
            self.open_settings(section="accounts")
            return "break"
        self.history_input.append(text)
        self.history_input = self.history_input[-50:]
        self.history_pos = None
        self.input_var.set("")
        if tab.platform == "twitch":
            echo = conn.send_message(tab.channel, text)
            if echo:
                self.events.put(("message", echo))
        else:
            channel = tab.channel
            self.run_in_thread(lambda: conn.send_message(channel, text), self._sent)
        return "break"

    def _sent(self, result):
        if isinstance(result, Exception):
            log.warning("Envoi : %s", result)
            self.toast(self.t("chat_send_failed"), "error")

    def _recall(self, d):
        if not self.history_input:
            return "break"
        if self.history_pos is None:
            self.history_pos = len(self.history_input)
        self.history_pos = max(0, min(len(self.history_input), self.history_pos + d))
        self.input_var.set(self.history_input[self.history_pos] if self.history_pos < len(self.history_input) else "")
        self.input.entry.icursor("end")
        return "break"

    def _reset_complete(self, e):
        if e.keysym not in ("Tab", "Shift_L", "Shift_R"):
            self._complete = None

    def _tab_complete(self, e):
        tab = self.current
        if not tab:
            return "break"
        entry = self.input.entry
        text, pos = self.input_var.get(), entry.index("insert")
        if self._complete is None:
            start = pos
            while start > 0 and not text[start - 1].isspace():
                start -= 1
            word = text[start:pos]
            if not word:
                return "break"
            at = word.startswith("@")
            prefix = word.lstrip("@").lower()
            names = sorted(set(tab.chatters.values()), key=str.lower)
            cands = [("@" if at else "") + n for n in names if n.lower().startswith(prefix)]
            if not at:
                cands += sorted(n for n in self.emote_maps.get(tab.key, {}) if n.lower().startswith(prefix))
            if not cands:
                return "break"
            self._complete = [start, cands, -1, len(word)]
        start, cands, i, length = self._complete
        i = (i + 1) % len(cands)
        new = cands[i] + " "
        self.input_var.set(text[:start] + new + text[start + length:])
        entry.icursor(start + len(new))
        self._complete = [start, cands, i, len(new)]
        return "break"

    # =====================================================
    # Menus
    # =====================================================
    def _anchor_at(self, e):
        anchor = getattr(self, "_menu_anchor", None)
        if anchor is None or not anchor.winfo_exists():
            anchor = self._menu_anchor = tk.Frame(self, width=1, height=1, bg=self.c.bg)
        anchor.place(x=e.x_root - self.winfo_rootx(), y=e.y_root - self.winfo_rooty())
        anchor.update_idletasks()
        return anchor

    def user_menu(self, view, e, name, msg):
        t, tab = self.t, view.tab
        conn = self.conns.get(tab.platform)
        items = []
        if conn and conn.can_send:
            items.append({"label": t("chat_menu_mention", name=name), "icon": "chat", "value": "mention"})
        items += [{"label": t("chat_menu_copy_name"), "icon": "link", "value": "copy"},
                  {"label": t("chat_menu_open_chat", name=name), "icon": "add", "value": "open"},
                  {"label": t("chat_menu_profile"), "icon": "link", "value": "profile"}]

        def pick(item):
            v = item["value"]
            login = (msg.user if msg and msg.user else name).lower()
            if v == "mention":
                cur = self.input_var.get()
                self.input_var.set((cur + " " if cur and not cur.endswith(" ") else cur) + f"@{name} ")
                self.input.focus()
            elif v == "copy":
                self.clipboard_clear()
                self.clipboard_append(name)
            elif v == "open":
                target = config.parse_target(login, tab.platform)
                if target:
                    self.open_tab(*target)
            elif v == "profile":
                self.open_url(config.channel_url(tab.platform, login))
        self.popover.show(self._anchor_at(e), items, pick, width=self.px(260))

    def message_menu(self, view, e, msg):
        t = self.t
        items = [{"label": t("chat_menu_copy_message"), "icon": "link", "value": "copy"}]
        if msg.user:
            items.append({"label": t("chat_menu_copy_name"), "icon": "link", "value": "name"})

        def pick(item):
            self.clipboard_clear()
            self.clipboard_append(msg.text if item["value"] == "copy" else msg.display_name)
            self.toast(t("chat_copied"))
        self.popover.show(self._anchor_at(e), items, pick, width=self.px(240))

    # =====================================================
    # Regarder / ouvrir
    # Watch / open
    # =====================================================
    def open_in_browser(self, tab=None):
        tab = tab or self.current
        if tab:
            self.open_url(config.channel_url(tab.platform, tab.channel))

    def watch(self, tab=None):
        """Lance le stream avec Streamlink (lecteur réglé dans la configuration de Streamlink).

        Starts the stream with Streamlink (player set in Streamlink's configuration)."""
        tab = tab or self.current
        if not tab:
            return
        t = self.t
        streamlink = core.find_streamlink(self.cfg["streamlink_path"])
        if not streamlink:
            self.toast(t("toast_no_streamlink"), "error", action=(t("title_settings"), self.open_settings))
            return
        command = core.watch_command(streamlink, tab.platform, config.channel_url(tab.platform, tab.channel),
                                     self.cfg["quality"])
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags)
            self.toast(t("chat_watch_started", channel=tab.title))
        except OSError as e:
            log.warning("Streamlink : %s", e)
            self.toast(t("toast_launch_failed"), "error")
