"""Panneau latéral et paramètres.

Side panel and settings."""
import logging
import tkinter as tk
from collections import deque

from . import __version__, auth, config, core
from .app_common import REPO_URL
from .ui.widgets import (
    Button,
    Field,
    IconButton,
    ScrollArea,
    Select,
    StatusCard,
    Switch,
)

log = logging.getLogger("streamlink_launcher")


class SettingsMixin:
    """Panneau latéral et paramètres.

    Side panel and settings."""

    # =====================================================
    # Paramètres
    # Settings
    # =====================================================
    def open_panel(self, kind, title, body_builder, footer_builder=None):
        self.close_panel()
        self.popover.close()
        c, px = self.c, self.px
        panel = tk.Frame(self, bg=c.panel)
        panel.place(relx=1.0, rely=0, anchor="ne", relheight=1.0, width=min(px(392), self.winfo_width()))
        tk.Frame(panel, bg=c.border, width=1).pack(side="left", fill="y")
        inner = tk.Frame(panel, bg=c.panel)
        inner.pack(side="left", fill="both", expand=True)
        head = tk.Frame(inner, bg=c.panel)
        head.pack(fill="x", padx=(px(24), px(14)), pady=(px(16), px(8)))
        tk.Label(head, text=title, font=self.fonts.panel_title, bg=c.panel, fg=c.text).pack(side="left")
        IconButton(head, self, "close", command=self.close_panel, size=36, icon_size=13).pack(side="right")
        if footer_builder:
            foot = tk.Frame(inner, bg=c.panel)
            foot.pack(side="bottom", fill="x")
            tk.Frame(foot, bg=c.border, height=1).pack(fill="x")
            fbody = tk.Frame(foot, bg=c.panel)
            fbody.pack(fill="x", padx=px(24), pady=px(12))
            footer_builder(fbody)
        area = ScrollArea(inner, self, c.panel)
        area.pack(fill="both", expand=True, padx=(px(24), px(6)), pady=(0, px(8)))
        body = tk.Frame(area.body, bg=c.panel)
        body.pack(fill="both", expand=True, padx=(0, px(12)))
        panel.update_idletasks()
        body_builder(body)
        panel.lift()
        self.panel, self.panel_kind, self.panel_area = panel, kind, area

    def close_panel(self):
        if self.panel is not None:
            self.panel.destroy()
        self.panel = self.panel_kind = None
        self.popover.close()
        cancel = getattr(self, "_login_cancel", None)
        if cancel:
            cancel.set()

    def _section(self, parent, title, first=False):
        c, px = self.c, self.px
        f = tk.Frame(parent, bg=c.panel)
        f.pack(fill="x", pady=(0 if first else px(22), 0))
        tk.Label(f, text=title.upper(), font=self.fonts.caps, bg=c.panel, fg=c.muted).pack(anchor="w",
                                                                                          pady=(0, px(6)))
        return f

    def _hint(self, parent, text, link=None):
        lbl = tk.Label(parent, text=text, font=self.fonts.tiny, bg=self.c.panel, fg=self.c.faint, justify="left",
                       wraplength=self.px(320), anchor="w")
        lbl.pack(anchor="w", pady=(self.px(6), 0))
        if link:
            lbl.configure(cursor="hand2", fg=self.c.muted)
            lbl.bind("<ButtonRelease-1>", lambda e: self.open_url(link))
        return lbl

    def _setting_row(self, parent, label, widget_factory):
        row = tk.Frame(parent, bg=self.c.panel)
        row.pack(fill="x", pady=self.px(4))
        tk.Label(row, text=label, font=self.fonts.body, bg=self.c.panel, fg=self.c.text).pack(side="left")
        widget_factory(row).pack(side="right")

    def _switch_row(self, parent, title, sub, value, on_change):
        c, px = self.c, self.px
        row = tk.Frame(parent, bg=c.panel)
        row.pack(fill="x", pady=px(4))
        Switch(row, self, value, on_change, accent=self.accent).pack(side="right")
        left = tk.Frame(row, bg=c.panel)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, font=self.fonts.body, bg=c.panel, fg=c.text, anchor="w").pack(anchor="w")
        if sub:
            tk.Label(left, text=sub, font=self.fonts.tiny, bg=c.panel, fg=c.faint, anchor="w", justify="left",
                     wraplength=px(260)).pack(anchor="w")

    def _field(self, parent, value, placeholder="", secret=False):
        var = tk.StringVar(value=value)
        f = Field(parent, self, var, placeholder=placeholder, height=40, font=self.fonts.body, radius=8,
                  accent=self.accent, bg_key="field")
        if secret:
            f.entry.configure(show="•")
        f.pack(fill="x", pady=(self.px(4), 0))
        return var

    def open_settings(self, section=None):
        t = self.t
        s = self.settings_state = {k: (list(v) if isinstance(v, list) else v) for k, v in self.cfg.items()
                                   if k not in ("tabs", "accounts", "geometry", "selected")}
        accounts = self.cfg["accounts"]

        def body(b):
            sec = self._section(b, t("chat_section_display"), first=True)
            langs = core.available_languages()
            self._setting_row(sec, t("label_language"), lambda r: Select(
                r, self, [("", t("chat_system_language"))] + [(code, name) for code, name in langs],
                s["language"], lambda v: s.update(language=v), height=36, width=180, font=self.fonts.small))
            self._setting_row(sec, t("label_theme"), lambda r: Select(
                r, self, [("auto", t("theme_auto")), ("light", t("theme_light")), ("dark", t("theme_dark"))],
                s["theme"], lambda v: s.update(theme=v), height=36, width=180, font=self.fonts.small))
            self._setting_row(sec, t("chat_label_font_size"), lambda r: Select(
                r, self, [(n, f"{n} px") for n in config.FONT_SIZES], s["font_size"],
                lambda v: s.update(font_size=v), height=36, width=110, font=self.fonts.small))
            self._switch_row(sec, t("chat_label_timestamps"), None, s["timestamps"],
                             lambda v: s.update(timestamps=v))
            self._switch_row(sec, t("chat_label_badges"), None, s["badges"], lambda v: s.update(badges=v))
            self._switch_row(sec, t("chat_label_platform_colors"), t("chat_hint_platform_colors"),
                             s["platform_colors"], lambda v: s.update(platform_colors=v))
            self._switch_row(sec, t("chat_label_animated"), None, s["animated"], lambda v: s.update(animated=v))

            sec = self._section(b, t("chat_section_emotes"))
            for pid, label in (("bttv", "BetterTTV"), ("ffz", "FrankerFaceZ"), ("7tv", "7TV")):
                def toggle(v, pid=pid):
                    s["providers"] = [x for x in s["providers"] if x != pid] + ([pid] if v else [])
                self._switch_row(sec, label, None, pid in s["providers"], toggle)
            self._hint(sec, t("chat_hint_emotes"))

            sec = self._section(b, t("chat_section_highlights"))
            hl = self._field(sec, ", ".join(s["highlights"]), placeholder=t("chat_highlights_placeholder"))
            s["_highlights_var"] = hl
            self._hint(sec, t("chat_hint_highlights"))
            self._setting_row(sec, t("chat_label_max_messages"), lambda r: Select(
                r, self, [(n, str(n)) for n in config.MAX_MESSAGES], s["max_messages"],
                lambda v: s.update(max_messages=v), height=36, width=110, font=self.fonts.small))

            sec = self._section(b, t("chat_section_watch"))
            self._setting_row(sec, t("chat_label_quality"), lambda r: Select(
                r, self, [(q, q) for q in core.QUALITIES], s["quality"], lambda v: s.update(quality=v), height=36,
                width=140, font=self.fonts.small))
            tk.Label(sec, text=t("chat_label_streamlink"), font=self.fonts.body, bg=self.c.panel,
                     fg=self.c.text).pack(anchor="w", pady=(self.px(8), 0))
            s["_streamlink_var"] = self._field(sec, s["streamlink_path"], placeholder=t("chat_streamlink_auto"))
            self._hint(sec, t("chat_hint_watch"))

            sec = self._section(b, t("chat_section_updates"))
            self.app_card = StatusCard(sec, self, True, "", "", t("btn_check"), self._app_card_action)
            self.app_card.pack(fill="x")
            self._update_app_card()
            links = tk.Frame(sec, bg=self.c.panel)
            links.pack(fill="x", pady=(self.px(6), self.px(4)))
            Button(links, self, text=t("link_release_notes"), kind="link", height=26, font=self.fonts.tiny, pad=4,
                   command=self._open_release_notes).pack(side="left")
            Button(links, self, text="GitHub", kind="link", height=26, font=self.fonts.tiny, pad=8,
                   command=lambda: self.open_url(REPO_URL)).pack(side="left")
            self._switch_row(sec, t("label_update_check"), t("hint_update_check"), s["update_check"],
                             lambda v: s.update(update_check=v))
            self._switch_row(sec, t("label_auto_update"), t("hint_auto_update"), s["auto_update"],
                             lambda v: s.update(auto_update=v))

            sec = self._section(b, t("chat_section_accounts"))
            self.accounts_box = sec
            self._account_block(sec, "twitch", accounts.get("twitch") or {})
            self._account_block(sec, "kick", accounts.get("kick") or {})
            if section == "accounts":
                self.after(50, lambda: self._scroll_to(sec))

        def footer(fb):
            Button(fb, self, text=t("btn_save"), kind="primary", accent=self.accent, height=40,
                   command=self.save_settings).pack(side="right")
            version = tk.Label(fb, text=f"Streamlink Chat {__version__}", font=self.fonts.tiny, bg=self.c.panel,
                               fg=self.c.faint, cursor="hand2")
            version.pack(side="left")
            version.bind("<ButtonRelease-1>", lambda e: self.open_url(REPO_URL))
        self.open_panel("settings", t("title_settings"), body, footer)

    # =====================================================

    def _scroll_to(self, widget):
        try:
            area = self.panel_area
            area.update_idletasks()
            total = max(1, area.body.winfo_height())
            area.canvas.yview_moveto(max(0.0, widget.winfo_y() / total - 0.02))
        except (tk.TclError, AttributeError):
            pass

    def _account_block(self, parent, platform, acc):
        t, c, px = self.t, self.c, self.px
        box = tk.Frame(parent, bg=c.panel)
        box.pack(fill="x", pady=(px(4), px(14)))
        top = tk.Frame(box, bg=c.panel)
        top.pack(fill="x")
        color = config.PLATFORMS[platform][1]
        dot = tk.Canvas(top, width=px(10), height=px(10), bg=c.panel, highlightthickness=0, bd=0)
        self.painter.circle(dot, px(5), px(5), px(8), color, bg=c.panel)
        dot.pack(side="left", padx=(0, px(8)))
        tk.Label(top, text=self.platform_name(platform), font=self.fonts.body_semi, bg=c.panel,
                 fg=c.text).pack(side="left")
        logged = bool(acc.get("access_token"))
        state = t("chat_account_logged", name=acc.get("login") or "?") if logged else t("chat_account_none")
        tk.Label(top, text=state, font=self.fonts.tiny, bg=c.panel, fg=c.ok if logged else c.faint).pack(
            side="right")
        if logged:
            Button(box, self, text=t("chat_logout"), kind="secondary", height=36,
                   command=lambda: self.logout(platform)).pack(anchor="w", pady=(px(8), 0))
            return
        cid = self._field(box, acc.get("client_id", ""), placeholder=t("chat_client_id"))
        secret = None
        if platform == "kick":
            secret = self._field(box, acc.get("client_secret", ""), placeholder=t("chat_client_secret"),
                                 secret=True)
        Button(box, self, text=t("chat_login", platform=self.platform_name(platform)), kind="primary",
               accent=config.PLATFORMS[platform][1:], height=36,
               command=lambda: self.login(platform, cid.get().strip(), secret.get().strip() if secret else "")
               ).pack(anchor="w", pady=(px(8), 0))
        if platform == "twitch":
            self._hint(box, t("chat_hint_twitch_app"), link="https://dev.twitch.tv/console/apps/create")
        else:
            self._hint(box, t("chat_hint_kick_app", redirect=auth.KICK_REDIRECT),
                       link="https://kick.com/settings/developer")

    def save_settings(self):
        s = self.settings_state
        sl = s.pop("_streamlink_var", None)
        if sl is not None:
            s["streamlink_path"] = sl.get().strip()
        hl = s.pop("_highlights_var", None)
        if hl is not None:
            s["highlights"] = [w.strip() for w in hl.get().split(",") if w.strip()][:30]
        rebuild = any(s[k] != self.cfg[k] for k in ("language", "theme", "font_size", "timestamps", "badges",
                                                       "platform_colors"))
        providers_changed = sorted(s["providers"]) != sorted(self.cfg["providers"])
        self.cfg.update({k: v for k, v in s.items() if k in self.cfg})
        config.save(self.cfg)
        for tab in self.tabs:
            if tab.history.maxlen != self.cfg["max_messages"]:
                tab.history = deque(tab.history, maxlen=self.cfg["max_messages"])
        self.close_panel()
        self._anims_dirty = True  # « Emotes animées » peut avoir changé / "Animated emotes" may have changed
        if rebuild:
            lang = self.cfg["language"] or core.detect_system_language()
            self.t = core.I18n(lang)
            self._make_chat_fonts()
            self.build()
        if providers_changed:
            self.global_emotes, self.channel_emotes = {}, {}
            self._rebuild_emote_maps()
            self._load_global_emotes()
            for tab in self.tabs:
                self._load_channel_emotes(tab)
        self.toast(self.t("toast_settings_saved"))
