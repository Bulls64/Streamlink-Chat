"""Onglets : ouverture, fermeture, sélection, menu et champ d'ajout.

Tabs: opening, closing, selection, menu and add field."""
import logging
from collections import deque

from . import config
from .app_view import ChannelTab, Tab
from .ui.widgets import Button

log = logging.getLogger("streamlink_launcher")


class TabsMixin:
    """Onglets : ouverture, fermeture, sélection, menu et champ d'ajout.

    Tabs: opening, closing, selection, menu and add field."""

    # --- onglets
    # --- tabs
    def build_tabs(self):
        for w in self.tabs_row.winfo_children():
            w.destroy()
        self.tab_widgets = {}
        for tab in self.tabs:
            self.tab_widgets[tab.key] = ChannelTab(self.tabs_row, self, tab, tab is self.current,
                                                   lambda tb=tab: self.select_tab(tb),
                                                   lambda tb=tab: self.close_tab(tb),
                                                   lambda w, tb=tab: self.tab_menu(w, tb))
        self.more_tabs = Button(self.tabs_row, self, icon="more", command=self._hidden_tabs_menu, kind="secondary",
                                height=34, width=40, radius=17)
        self._flow_tabs()

    def _flow_tabs(self):
        width = self.tabs_row.winfo_width()
        if width <= 1:
            return
        gap, x, reserve = self.px(6), 0, self.px(46)
        self._hidden = []
        widgets = [(tab, self.tab_widgets.get(tab.key)) for tab in self.tabs]
        for i, (tab, w) in enumerate(widgets):
            if w is None:
                continue
            need = int(w.cget("width"))
            limit = width - (reserve if i < len(widgets) - 1 else 0)
            if not self._hidden and x + need <= limit:
                w.place(x=x, y=0)
                x += need + gap
            else:
                w.place_forget()
                self._hidden.append(tab)
        if self._hidden:
            self.more_tabs.place(x=x, y=0)
            self.more_tabs.set_badge(self.c.warn if any(t.mentioned for t in self._hidden) else None)
        else:
            self.more_tabs.place_forget()

    def _hidden_tabs_menu(self):
        items = [{"label": t.title, "value": t, "right": self.platform_name(t.platform),
                  "right_dot": config.PLATFORMS[t.platform][1], "right_color": self.c.muted,
                  "selected": t is self.current} for t in getattr(self, "_hidden", [])]
        self.popover.show(self.more_tabs, items, lambda it: self.select_tab(it["value"], to_front=True),
                          width=self.px(260))

    def open_tab(self, platform, channel, select=True, save=True):
        for tab in self.tabs:
            if tab.key == (platform, channel):
                if select:
                    self.select_tab(tab)
                return tab
        tab = Tab(platform, channel)
        tab.history = deque(maxlen=self.cfg["max_messages"])
        self.tabs.append(tab)
        self._connection(platform).join(channel)
        if self.tab_widgets is not None and hasattr(self, "tabs_row"):
            self.build_tabs()
        if select:
            self.select_tab(tab)
        if save:
            self.save_tabs()
        return tab

    def close_tab(self, tab):
        if tab not in self.tabs:
            return
        i = self.tabs.index(tab)
        self.tabs.remove(tab)
        conn = self.conns.get(tab.platform)
        if conn:
            conn.part(tab.channel)
        if tab.view:
            tab.view.destroy()
        if self.current is tab:
            self.current = None
            if self.tabs:
                self.select_tab(self.tabs[min(i, len(self.tabs) - 1)])
            else:
                self.refresh_current()
        self.build_tabs()
        self.save_tabs()

    def select_tab(self, tab, to_front=False):
        if to_front and tab in self.tabs:
            self.tabs.remove(tab)
            self.tabs.insert(0, tab)
            self.build_tabs()
        previous, self.current = self.current, tab
        if previous and previous.view and previous is not tab:
            previous.view.frame.pack_forget()
        tab.unread, tab.mentioned = 0, False
        for t, w in list(self.tab_widgets.items()):
            w.refresh(selected=(t == tab.key))
        self._flow_tabs()
        self.refresh_current()
        self.save_tabs()

    def cycle_tab(self, d):
        if self.tabs and self.current in self.tabs:
            self.select_tab(self.tabs[(self.tabs.index(self.current) + d) % len(self.tabs)])
        return "break"

    def tab_menu(self, widget, tab):
        t = self.t
        items = [{"label": t("chat_menu_watch"), "icon": "play", "value": "watch"},
                 {"label": t("chat_menu_browser"), "icon": "link", "value": "browser"},
                 {"label": t("chat_menu_reconnect"), "icon": "sync", "value": "reconnect"},
                 {"label": t("chat_menu_close"), "icon": "close", "value": "close"}]

        def pick(item):
            v = item["value"]
            if v == "watch":
                self.watch(tab)
            elif v == "browser":
                self.open_in_browser(tab)
            elif v == "reconnect":
                self.reconnect(tab)
            else:
                self.close_tab(tab)
        self.popover.show(widget, items, pick, width=self.px(240))

    def save_tabs(self):
        self.cfg["tabs"] = [{"platform": t.platform, "channel": t.channel} for t in self.tabs]
        self.cfg["selected"] = self.tabs.index(self.current) if self.current in self.tabs else 0
        try:
            config.save(self.cfg)
        except OSError as e:
            log.warning("chat.json : %s", e)

    def _add_placeholder(self, pid):
        return self.t("chat_add_placeholder", platform=self.platform_name(pid))

    def select_platform(self, pid, save=True):
        """Plateforme des chats ajoutés par nom : pastille, accent et texte d'aide du champ d'ajout.

        Platform of chats added by name: pill, accent and hint text of the add field."""
        if pid not in config.PLATFORMS or (pid == self.cfg["default_platform"] and not save):
            return
        self.cfg["default_platform"] = pid
        for p, pill in self.pills.items():
            pill.set_state(selected=p == pid)
        self.add_field.set_accent(config.PLATFORMS[pid][1:])
        self.add_field.set_placeholder(self._add_placeholder(pid))
        self.add_field.redraw()
        if save:
            config.save(self.cfg)

    def _detect_added_platform(self, *_):
        """Un lien collé ou tapé dans le champ d'ajout sélectionne sa plateforme.

        A link pasted or typed in the add field selects its platform."""
        pid = config.detect_platform(self.add_var.get())
        if pid and pid != self.cfg["default_platform"]:
            self.select_platform(pid)

    def _add_from_field(self, e=None):
        target = config.parse_target(self.add_var.get(), self.cfg["default_platform"])
        if not target:
            self.toast(self.t("chat_bad_channel"), "warn")
            return "break"
        self.add_var.set("")
        self.open_tab(*target)
        self.input.focus()
        return "break"
