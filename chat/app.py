"""Streamlink Chat : les chats Twitch, Kick et Steam TV dans une fenêtre, dans le style de Streamlink Launcher.

Streamlink Chat: Twitch, Kick and Steam TV chats in one window, in the style of Streamlink Launcher."""
import logging
import os
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from collections import OrderedDict

from . import __version__, config, core, emotes, instance, updater
from .app_accounts import AccountsMixin
from .app_common import ASSETS, GEOMETRY_RE
from .app_compose import ComposeMixin
from .app_connections import ConnectionsMixin
from .app_media import MediaMixin
from .app_settings import SettingsMixin
from .app_tabs import TabsMixin
from .app_updates import UpdatesMixin

# réexporté pour slink_chat.py
# re-exported for slink_chat.py
from .config import targets_from_argv
from .ui.gfx import Painter
from .ui.theme import (
    Fonts,
    apply_window_chrome,
    enable_dpi_awareness,
    mix,
    palette,
    resolve_theme,
    set_app_id,
)
from .ui.widgets import (
    Button,
    Field,
    IconButton,
    Pill,
    Popover,
    Toast,
)

log = logging.getLogger("streamlink_launcher")


# =====================================================
# Application
# =====================================================
class ChatApp(TabsMixin, ConnectionsMixin, MediaMixin, ComposeMixin, SettingsMixin, UpdatesMixin, AccountsMixin, tk.Tk):
    def __init__(self, targets=()):
        super().__init__(className="StreamlinkChat")
        self.withdraw()
        self.scale = max(1.0, min(3.0, self.winfo_fpixels("1i") / 96.0))
        self.cfg = config.load()
        lang = self.cfg["language"] or core.detect_system_language()
        self.t = core.I18n(lang)
        self.painter = Painter(self)
        self.fonts = Fonts(self, self.px)
        self.popover = Popover(self)
        self.events = queue.Queue()
        self.tabs = []
        self.current = None
        self.panel = self.panel_kind = None
        self.toast_widget = None
        self.more_btn = None
        self.tab_widgets = {}
        self.history_input, self.history_pos = [], None
        self._complete = None
        self.global_emotes = {}
        self.channel_emotes = {}
        self.emote_maps = {}
        self.images = OrderedDict()  # url -> PhotoImage, False (illisible) ; absent = pas encore demandé (LRU)
                                    # url -> PhotoImage, False (unreadable); missing = not requested yet (LRU)
        self.gifs = {}              # url -> (octets du GIF, délais) des emotes animées, décodées seulement si visibles
                                    # url -> (GIF bytes, delays) of animated emotes, decoded only when visible
        self._anims_dirty = False
        self.emote_names = {}
        self.anims = {}             # url -> [image affichée, [(image, délai)], index, prochain changement]
                                    # url -> [displayed image, [(image, delay)], index, next change]
                                    # seulement pour le chat affiché / only for the displayed chat
        self.badge_images, self.badge_tags, self.badge_labels = {}, {}, {}
        self.loader = emotes.ImageLoader(config.CACHE_DIR)
        self.conns = {}
        self.input_var = tk.StringVar()
        self.add_var = tk.StringVar()
        self.add_var.trace_add("write", self._detect_added_platform)
        self._make_chat_fonts()
        self.title("Streamlink Chat")
        try:
            self._icons = [tk.PhotoImage(master=self, file=str(ASSETS / f"icon_{s}.png")) for s in (48, 32, 16)]
            self.iconphoto(True, *self._icons)
            if os.name == "nt":
                self.iconbitmap(default=str(ASSETS / "app.ico"))  # icône nette dans la barre des tâches
                                                                  # sharp icon in the taskbar
        except tk.TclError:
            pass
        self.minsize(self.px(380), self.px(460))
        self._restore_geometry()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<ButtonPress-1>", self._global_click, add="+")
        self.bind("<Escape>", lambda e: self.popover.close() if self.popover.is_open else self.close_panel())
        self.bind("<Control-t>", lambda e: self.add_field.focus())
        self.bind("<Control-w>", lambda e: self.close_tab(self.current) if self.current else None)
        self.bind("<Control-Tab>", lambda e: self.cycle_tab(1))
        for seq in ("<Control-Shift-Tab>", "<Control-ISO_Left_Tab>"):  # ISO_Left_Tab : X11 seulement
                                                                       # ISO_Left_Tab: X11 only
            try:
                self.bind(seq, lambda e: self.cycle_tab(-1))
            except tk.TclError:
                pass
        self.build()
        for saved in self.cfg["tabs"]:
            self.open_tab(saved["platform"], saved["channel"], select=False, save=False)
        if self.tabs:
            self.select_tab(self.tabs[min(self.cfg["selected"], len(self.tabs) - 1)])
        for platform, channel in targets:
            self.open_tab(platform, channel)
        self.deiconify()
        self.after(40, self._pump)
        self.after(200, self._load_global_emotes)
        self.after(60, self._animate)
        self.after(300, self._check_accounts)
        instance.serve(lambda targets: self.events.put(("open", targets)))
        # Mise à jour de l'application (releases GitHub)
        # Application update (GitHub releases)
        self.app_update = None
        self._app_state, self._app_error, self._app_dl = "idle", None, (0, 0)
        self._app_cancel = threading.Event()
        self._updated_from = updater.arg_value("--updated-from")
        if core.FROZEN:  # restes d'une mise à jour précédente (ancien exécutable, téléchargement interrompu)
                         # leftovers of a previous update (old executable, interrupted download)
            threading.Thread(target=updater.cleanup_leftovers, daemon=True).start()
        if self._updated_from:
            self.after(900, lambda: self.toast(self.t("toast_updated", old=self._updated_from, new=__version__),
                                               duration=6000))
        if self.cfg["update_check"]:
            self.after(5000, lambda: self.check_app_update(manual=False))

    # --- outils
    # --- tools
    def px(self, v):
        return int(round(v * self.scale))

    @property
    def c(self):
        return self._palette

    @property
    def accent(self):
        if self.current:
            return config.PLATFORMS[self.current.platform][1:]
        return config.NEUTRAL

    def platform_name(self, pid):
        return config.PLATFORMS[pid][0]

    def _make_chat_fonts(self):
        size = self.cfg["font_size"]
        family = self.fonts.body.actual("family")
        semi = self.fonts.body_semi.actual()
        self.chat_font = tkfont.Font(root=self, family=family, size=-self.px(size))
        self.chat_bold = tkfont.Font(root=self, family=semi["family"], size=-self.px(size),
                                     weight=semi.get("weight", "normal"))
        self.chat_small = tkfont.Font(root=self, family=family, size=-self.px(max(10, size - 2)))

    def run_in_thread(self, work, done):
        def runner():
            try:
                result = work()
            except Exception as e:
                result = e
            self.events.put(("call", done, result))
        threading.Thread(target=runner, daemon=True).start()

    def open_url(self, url):
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    def _restore_geometry(self):
        m = GEOMETRY_RE.match(self.cfg.get("geometry") or "")
        if m and 0 <= int(m.group(3)) < self.winfo_screenwidth() - 100 \
                and 0 <= int(m.group(4)) < self.winfo_screenheight() - 100:
            self.geometry(self.cfg["geometry"])
        else:
            self.geometry(f"{self.px(560)}x{self.px(780)}")

    def toast(self, text, kind="ok", action=None, duration=3200):
        if self.toast_widget is not None:
            self.toast_widget.dismiss()
        self.toast_widget = Toast(self, text, kind, action, duration, bottom=self.px(96))

    def _global_click(self, e):
        if self.popover.is_open and not self.popover.contains(e.widget) and \
                not (self.popover.anchor and str(e.widget).startswith(str(self.popover.anchor))):
            self.popover.close()

    # =====================================================
    # Construction
    # =====================================================
    def build(self):
        self.popover.close()
        for w in self.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()
        self.panel = self.panel_kind = None
        self.more_btn = None
        self.mode = resolve_theme(self.cfg["theme"])
        self._palette = c = palette(self.mode)
        t, px, f = self.t, self.px, self.fonts
        self.configure(bg=c.bg)
        for tab in self.tabs:
            tab.view = None

        content = tk.Frame(self, bg=c.bg)
        content.pack(fill="both", expand=True, padx=px(20), pady=(px(16), px(16)))
        self.content = content

        head = tk.Frame(content, bg=c.bg)
        head.pack(fill="x")
        tk.Label(head, text=t("chat_title"), font=f.title, bg=c.bg, fg=c.text).pack(side="left")
        self.settings_btn = IconButton(head, self, "settings", command=self.open_settings)
        self.settings_btn.pack(side="right")
        if getattr(self, "app_update", None) and self.app_update.get("update"):
            self.settings_btn.set_badge(self.c.warn)

        row = tk.Frame(content, bg=c.bg)
        row.pack(fill="x", pady=(px(12), 0))
        pid = self.cfg["default_platform"]
        self.add_field = Field(row, self, self.add_var, placeholder=self._add_placeholder(pid), icon="add",
                               kbd=t("kbd_enter"), ring=True, height=44, font=f.body, radius=10,
                               accent=config.PLATFORMS[pid][1:], bg_key="surface")
        self.add_field.pack(side="left", fill="x", expand=True)
        self.add_field.entry.bind("<Return>", self._add_from_field)
        self.add_field.entry.bind("<KP_Enter>", self._add_from_field)
        # Pastilles des plateformes, comme dans Streamlink Launcher : la choisie est pleine de sa couleur
        # Platform pills, as in Streamlink Launcher: the selected one is filled with its color
        pills = tk.Frame(content, bg=c.bg)
        pills.pack(fill="x", pady=(px(10), 0))
        self.pills = {}
        for p, (name, color, on) in config.PLATFORMS.items():
            pill = Pill(pills, self, name, dot=color, command=lambda p=p: self.select_platform(p),
                        selected=p == pid, accent=(color, on))
            pill.pack(side="left", padx=(0, px(8)))
            self.pills[p] = pill
        tk.Frame(content, bg=c.border, height=1).pack(fill="x", pady=(px(12), 0))

        self.tabs_row = tk.Frame(content, bg=c.bg, height=px(34))
        self.tabs_row.pack(fill="x", pady=(px(12), 0))
        self.tabs_row.pack_propagate(False)
        self.tabs_row.bind("<Configure>", lambda e: self._flow_tabs())

        # Saisie
        # Input
        bottom = tk.Frame(content, bg=c.bg)
        bottom.pack(side="bottom", fill="x", pady=(px(12), 0))
        self.send_btn = Button(bottom, self, icon="send", command=self.send, kind="primary", height=44, width=44,
                               accent=self.accent, icon_size=16)
        self.send_btn.pack(side="right", padx=(px(8), 0))
        self.input = Field(bottom, self, self.input_var, placeholder="", height=44, font=f.body, radius=10,
                           ring=True, accent=self.accent, bg_key="surface")
        self.input.pack(side="left", fill="x", expand=True)
        e = self.input.entry
        e.bind("<Return>", lambda ev: self.send())
        e.bind("<KP_Enter>", lambda ev: self.send())
        e.bind("<Up>", lambda ev: self._recall(-1))
        e.bind("<Down>", lambda ev: self._recall(1))
        e.bind("<Tab>", self._tab_complete)
        e.bind("<Key>", self._reset_complete, add="+")
        self.input.cv.bind("<ButtonRelease-1>", self._input_click, add="+")
        # Carte du chat
        # Chat card
        self.card = tk.Frame(content, bg=c.bg)
        self.card.pack(fill="both", expand=True, pady=(px(12), 0))
        self.card_cv = tk.Canvas(self.card, bg=c.bg, highlightthickness=0, bd=0)
        self.card_cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.card_cv.bind("<Configure>", lambda e: self._draw_card())
        inner = tk.Frame(self.card, bg=c.surface)
        inner.pack(fill="both", expand=True, padx=px(1), pady=px(1))
        self.card_inner = inner
        self.header = tk.Frame(inner, bg=c.surface)
        self.header.pack(fill="x", padx=(px(14), px(8)), pady=(px(8), 0))
        self.platform_dot = tk.Canvas(self.header, width=px(10), height=px(10), bg=c.surface, highlightthickness=0,
                                      bd=0)
        self.platform_dot.pack(side="left", padx=(0, px(8)))
        self.header_title = tk.Label(self.header, text="", font=f.card_title, bg=c.surface, fg=c.text)
        self.header_title.pack(side="left")
        self.header_status = tk.Label(self.header, text="", font=f.tiny, bg=c.surface, fg=c.muted)
        self.header_status.pack(side="left", padx=(px(10), 0))
        self.header_btns = tk.Frame(self.header, bg=c.surface)
        self.header_btns.pack(side="right")
        IconButton(self.header_btns, self, "link", command=self.open_in_browser, size=32, icon_size=14,
                   bg=c.surface).pack(side="right")
        IconButton(self.header_btns, self, "play", command=self.watch, size=32, icon_size=14,
                   bg=c.surface).pack(side="right")
        self.header_sep = tk.Frame(inner, bg=c.border, height=1)
        self.header_sep.pack(fill="x", pady=(px(8), 0))
        self.views_box = tk.Frame(inner, bg=c.surface)
        self.views_box.pack(fill="both", expand=True)
        self.empty = tk.Label(self.views_box, text=t("chat_empty"), font=f.body, bg=c.surface, fg=c.muted,
                              justify="center", wraplength=px(360))

        self.build_tabs()
        if self.current:
            current, self.current = self.current, None
            self.select_tab(current)
        else:
            self.refresh_current()
        self.after_idle(self.apply_chrome)

    def apply_chrome(self):
        apply_window_chrome(self, self.c.dark, border=self.accent[0], caption=self.c.title, text=self.c.text)

    def _draw_card(self):
        cv, c, px = self.card_cv, self.c, self.px
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w > 2 and h > 2:
            fill, border = self.card_colors(self.current.platform if self.current else None)
            self.painter.round_rect(cv, 0, 0, w, h, px(12), fill, border, c.bg)
            self.card_inner.pack_configure(padx=px(4), pady=px(4))

    def card_colors(self, platform):
        """(fond, bordure) de la carte du chat : teintés de la couleur de la plateforme (réglage), comme les
        cartes de favoris de Streamlink Launcher.

        (background, border) of the chat card: tinted with the platform's color (setting), like the
        favorite cards of Streamlink Launcher."""
        c = self.c
        if not platform or not self.cfg["platform_colors"]:
            return c.surface, c.border
        color = config.PLATFORMS[platform][1]
        return mix(c.surface, color, 0.07 if c.dark else 0.05), mix(c.border, color, 0.6)

    def _paint_card(self):
        """Couleurs de la carte pour le chat affiché (en-tête, séparateur, zone des messages).

        Card colors for the displayed chat (header, separator, message area)."""
        platform = self.current.platform if self.current else None
        fill, border = self.card_colors(platform)
        for w in (self.card_inner, self.header, self.header_title, self.header_status, self.header_btns,
                  self.views_box, self.empty):
            w.configure(bg=fill)
        for b in self.header_btns.winfo_children():
            b.configure(bg=fill)
            b.redraw()
        self.header_sep.configure(bg=border)
        self.platform_dot.configure(bg=fill)
        self.platform_dot.delete("all")
        if platform:
            d = self.px(10)
            self.painter.circle(self.platform_dot, d / 2, d / 2, d, config.PLATFORMS[platform][1], bg=fill)
        self._draw_card()

    # =====================================================
    # Fermeture
    # Closing
    # =====================================================
    def on_close(self, relaunching=False):
        if self._app_state in ("downloading", "verifying") and not relaunching:
            self._app_cancel.set()
        try:
            if self.state() == "normal":
                self.cfg["geometry"] = self.geometry()
            self.save_tabs()
        except (tk.TclError, OSError):
            log.debug("Enregistrement à la fermeture incomplet", exc_info=True)
        for conn in self.conns.values():
            conn.stop()
        self.loader.shutdown()
        instance.stop()
        self.destroy()


def main(targets=()):
    core.setup_logging()
    waited = updater.arg_value("--wait-pid")  # relance après une mise à jour : on attend la fin de l'ancienne
                                              # restart after an update: wait for the old one to end
    if waited and waited.isdigit():
        updater.wait_for_pid(int(waited), 20)
    if instance.forward(targets):
        return  # déjà ouvert : la fenêtre existante ouvre ces chats
                # already open: the existing window opens these chats
    enable_dpi_awareness()
    set_app_id("Bulls64.StreamlinkChat")
    ChatApp(targets).mainloop()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main(targets_from_argv(sys.argv[1:]))
