"""Composants dessinés sur des Canvas Tk (repris de Streamlink Launcher) : peu d'objets, aucune dépendance."""
import logging
import tkinter as tk

from .gfx import draw_icon
from .theme import accent_ring, fit_text, mix, readable_on

log = logging.getLogger("streamlink_launcher")


def _schedule_redraw(widget):
    """Regroupe les redessins dus aux changements de taille : un seul passage, à la fin du calcul de la mise
    en page. Sans cela, chaque composant était dessiné une fois à sa taille demandée puis une fois à sa taille
    réelle (deux fois plus de travail à chaque ouverture de panneau)."""
    app = widget.app
    pending = app.__dict__.setdefault("_redraw_pending", {})
    pending[str(widget)] = widget
    if not app.__dict__.get("_redraw_job"):
        app._redraw_job = app.after_idle(_flush_redraws, app)


def _flush_redraws(app):
    app._redraw_job = None
    pending, app._redraw_pending = app._redraw_pending, {}
    for w in pending.values():
        try:
            if w.winfo_exists() and w._size() != w._drawn:
                w.redraw()
        except tk.TclError:
            pass


class Widget(tk.Canvas):
    """Base : redessine à la taille réelle, gère survol, clic, clavier et focus.

    Zones : un composant à plusieurs parties cliquables redéfinit zone_at(x, y) ; la zone survolée est
    alors suivie dans self.zone (et redessinée quand elle change). zone_cursor : main uniquement
    au-dessus d'une zone, flèche ailleurs.
    """

    zone_cursor = False

    def __init__(self, parent, app, width=1, height=1, command=None, bg=None, focusable=None):
        self.app = app
        self.command = command
        self.zone = None
        self.hover = False
        self.focused = False
        self.disabled = False
        bg = bg or parent.cget("bg")
        focus = (command is not None) if focusable is None else focusable
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0,
                         takefocus=1 if focus else 0, cursor="hand2" if command else "")
        self._drawn = None  # taille du dernier dessin
        self.bind("<Configure>", self._on_configure)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Motion>", self._motion)
        if focus:
            self.bind("<KeyPress-Return>", lambda e: self.activate())
            self.bind("<KeyPress-space>", lambda e: self.activate())
            self.bind("<FocusIn>", lambda e: self._set_focus(True))
            self.bind("<FocusOut>", lambda e: self._set_focus(False))

    # --- état
    def _enter(self, e):
        self.hover = True
        self.redraw()

    def _leave(self, e):
        self.hover = False
        self._set_zone(None)
        self.redraw()

    def _set_focus(self, value):
        self.focused = value
        self.redraw()

    def zone_at(self, x, y):
        return None

    def _set_zone(self, zone):
        if zone == self.zone:
            return False
        self.zone = zone
        if self.zone_cursor:
            self.configure(cursor="hand2" if zone is not None else "")
        return True

    def _motion(self, e):
        if self._set_zone(self.zone_at(e.x, e.y)):
            self.redraw()

    def _release(self, e):
        if self.disabled:
            return
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self.on_click(e)

    def on_click(self, e):
        self.activate()

    def activate(self):
        if self.command and not self.disabled:
            self.command()

    def set_disabled(self, value):
        self.disabled = value
        self.configure(cursor="" if value or not self.command else "hand2")
        self.redraw()

    # --- dessin
    @property
    def c(self):
        return self.app.c

    @property
    def P(self):
        return self.app.painter

    @property
    def px(self):
        return self.app.px

    def icon(self, name, x, y, size, color):
        draw_icon(self, self.app.fonts, name, x, y, size, color)

    def _on_configure(self, e):
        if (e.width, e.height) != self._drawn:
            _schedule_redraw(self)

    def _size(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            w = int(self.cget("width"))
        if h <= 1:
            h = int(self.cget("height"))
        return w, h

    def redraw(self):
        try:
            w, h = self._size()
        except tk.TclError:
            return
        self._drawn = (w, h)
        self.delete("all")
        self.draw(w, h)
        if self.focused:
            self.create_rectangle(1, 1, w - 1, h - 1, outline=self.c.focus, width=2)

    def draw(self, w, h):
        pass


class Button(Widget):
    """kind : primary (couleur d'accent), secondary (contour), ghost (fond au survol), link (texte)."""

    def __init__(self, parent, app, text="", icon=None, command=None, kind="secondary", height=40, font=None,
                 accent=None, width=None, pad=16, icon_size=14, radius=10, bg=None, color=None):
        self.app = app
        self.text, self.icon_name, self.kind = text, icon, kind
        self.font = font or app.fonts.body_semi
        self.accent = accent
        self.fg_color = color
        self.icon_size = app.px(icon_size)
        self.pad = app.px(pad)
        self.radius = app.px(radius)
        h = app.px(height)
        w = app.px(width) if width else self._natural_width(h)
        super().__init__(parent, app, width=w, height=h, command=command, bg=bg)

    def _natural_width(self, h):
        if not self.text:
            return h
        icon = self.icon_size + self.app.px(8) if self.icon_name else 0
        return self.font.measure(self.text) + icon + 2 * self.pad

    def set_accent(self, accent):
        self.accent = accent
        self.redraw()

    def set_text(self, text):
        self.text = text
        self.configure(width=self._natural_width(int(self.cget("height"))))
        self.redraw()

    def draw(self, w, h):
        c, bg = self.c, self.cget("bg")
        fill = outline = None
        if self.kind == "primary":
            col, on = self.accent or (c.text, c.bg)
            fill = mix(col, "#000000" if c.dark else "#FFFFFF", 0.12) if self.hover and not self.disabled else col
            if self.disabled:
                fill = mix(col, bg, 0.55)
            fg = on
        elif self.kind == "secondary":
            fill = c.hover(bg) if self.hover else bg
            outline = c.border_strong if self.hover else c.border
            fg = c.text
        elif self.kind == "ghost":
            fill = c.hover(bg) if self.hover else None
            fg = c.text if self.hover else (self.fg_color or c.muted)
        else:  # link
            fg = self.fg_color or (c.text if self.hover else c.muted)
            if self.fg_color and self.hover:
                fg = mix(self.fg_color, c.text, 0.3)
        if self.disabled and self.kind != "primary":
            fg = c.faint
        if fill or outline:
            self.P.round_rect(self, 0, 0, w, h, self.radius, fill, outline, bg)
        gap = self.px(8)
        tw = self.font.measure(self.text) if self.text else 0
        iw = self.icon_size if self.icon_name else 0
        total = tw + iw + (gap if tw and iw else 0)
        x = (w - total) / 2
        if self.icon_name:
            self.icon(self.icon_name, x + iw / 2, h / 2, self.icon_size, fg)
            x += iw + (gap if tw else 0)
        if self.text:
            self.create_text(x, h / 2, text=self.text, font=self.font, fill=fg, anchor="w")
        badge = getattr(self, "badge", None)
        if badge:  # petite pastille (ex. mise à jour disponible)
            self.P.circle(self, w - self.px(10), self.px(10), self.px(8), badge, bg=fill or bg)

    def set_badge(self, color):
        self.badge = color
        self.redraw()


class IconButton(Button):
    def __init__(self, parent, app, icon, command=None, size=40, icon_size=18, bg=None, color=None):
        super().__init__(parent, app, icon=icon, command=command, kind="ghost", height=size, width=size,
                         icon_size=icon_size, radius=10, bg=bg, color=color)


class Pill(Widget):
    def __init__(self, parent, app, text, dot=None, command=None, selected=False, accent=None, dashed=False,
                 icon=None):
        self.text, self.dot, self.selected, self.accent = text, dot, selected, accent
        self.dashed, self.icon_name = dashed, icon
        self.font = app.fonts.small_semi if selected else app.fonts.small
        super().__init__(parent, app, width=self._width(app), height=app.px(34), command=command)

    def _width(self, app):
        lead = app.px(16) if (self.dot or self.icon_name) else 0
        return app.px(12) + lead + app.fonts.small_semi.measure(self.text) + app.px(14)

    def set_state(self, selected=None, accent=None, text=None):
        if selected is not None:
            self.selected = selected
        if accent is not None:
            self.accent = accent
        if text is not None:
            self.text = text
        self.configure(width=self._width(self.app))
        self.redraw()

    def draw(self, w, h):
        c, bg = self.c, self.cget("bg")
        r = h // 2
        if self.dashed and not self.selected:
            if self.hover:
                self.P.round_rect(self, 0, 0, w, h, r, c.hover(bg), c.hover(bg), bg)
            self.P.dashed_round_rect(self, 0, 0, w, h, r, c.border_strong if self.hover else c.border)
            fill, fg, dot = c.hover(bg) if self.hover else bg, c.muted, None
        elif self.selected:
            col, on = self.accent
            self.P.round_rect(self, 0, 0, w, h, r, col, col, bg)
            fill, fg, dot = col, on, (on if self.dot else None)
        else:
            fill = c.hover(bg) if self.hover else bg
            self.P.round_rect(self, 0, 0, w, h, r, fill, c.border_strong if self.hover else c.border, bg)
            fg, dot = c.text, self.dot
        x = self.px(12)
        if self.icon_name:
            self.icon(self.icon_name, x + self.px(5), h / 2, self.px(14), fg)
            x += self.px(16)
        elif dot:
            self.P.circle(self, x + self.px(4), h / 2, self.px(8), dot, bg=fill)
            x += self.px(16)
        font = self.app.fonts.small_semi if self.selected else self.app.fonts.small
        self.create_text(x, h / 2, text=self.text, font=font, fill=fg, anchor="w")


class Field(tk.Frame):
    """Champ arrondi avec icône, raccourci clavier, badge, bouton d'action et texte indicatif."""

    def __init__(self, parent, app, variable, placeholder="", icon=None, kbd=None, ring=False, mono=False,
                 height=40, font=None, radius=8, accent=None, action_icon=None, action_command=None,
                 badge=None, bg_key="field", plain=False):
        bg = parent.cget("bg")
        super().__init__(parent, bg=bg)
        self.plain = plain  # sans cadre (barre du mode mini)
        self.app, self.var = app, variable
        self.icon_name, self.kbd, self.ring, self.radius = icon, kbd, ring, app.px(radius)
        self.accent = accent
        self.action_icon, self.action_command, self.badge = action_icon, action_command, badge
        self.bg_key = bg_key
        self.disabled = False
        c = app.c
        self.font = font or (app.fonts.mono_field if mono else app.fonts.body)
        fbg = c[bg_key]
        # Petite largeur demandée : le champ s'étire, sans écraser ses voisins
        self.cv = tk.Canvas(self, width=app.px(120), height=app.px(height), bg=bg, highlightthickness=0, bd=0,
                            cursor="xterm")
        self.cv.pack(fill="x")
        self.entry = tk.Entry(self.cv, textvariable=variable, relief="flat", bd=0, highlightthickness=0, bg=fbg,
                              fg=c.text, insertbackground=c.text, font=self.font, disabledbackground=fbg,
                              disabledforeground=c.faint, selectbackground=mix(fbg, accent[0] if accent else c.muted, 0.45),
                              selectforeground=c.text, insertwidth=max(1, app.px(1.5)))
        self.ph = tk.Label(self.cv, text=placeholder, bg=fbg, fg=c.faint, font=self.font, anchor="w", bd=0,
                           cursor="xterm", padx=0, pady=0)
        self.ph.bind("<Button-1>", lambda e: self.focus())
        self._win = self._phwin = None
        self._action_x = None
        self._trace = variable.trace_add("write", self._sync)
        self.bind("<Destroy>", self._cleanup)
        self.entry.bind("<FocusIn>", lambda e: self.redraw(), add="+")
        self.entry.bind("<FocusOut>", lambda e: self.redraw(), add="+")
        self.cv.bind("<Configure>", lambda e: self.redraw())
        self.cv.bind("<ButtonRelease-1>", self._click)
        self.cv.bind("<Motion>", self._motion)

    def _cleanup(self, e):
        if e.widget is self and self._trace:
            try:
                self.var.trace_remove("write", self._trace)
            except tk.TclError:
                pass
            self._trace = None

    def focus(self):
        if not self.disabled:
            self.entry.focus_set()
            self.entry.icursor("end")

    def has_focus(self):
        try:
            return self.app.focus_get() is self.entry
        except (KeyError, tk.TclError):
            return False

    def set_accent(self, accent):
        self.accent = accent
        self.entry.configure(selectbackground=mix(self.app.c[self.bg_key], accent[0], 0.45))
        self.redraw()

    def set_placeholder(self, text):
        self.ph.configure(text=text)

    def set_disabled(self, value):
        self.disabled = value
        self.entry.configure(state="disabled" if value else "normal")
        self.cv.configure(cursor="" if value else "xterm")
        self.redraw()

    def _action_zone(self, x):
        return self.action_icon and self._action_x and self._action_x[0] <= x <= self._action_x[1]

    def _motion(self, e):
        self.cv.configure(cursor="hand2" if self._action_zone(e.x) else ("" if self.disabled else "xterm"))

    def _click(self, e):
        if self._action_zone(e.x):
            if self.action_command:
                self.action_command()
        else:
            self.focus()

    def _sync(self, *args):
        """Appelé quand le texte change : texte indicatif et badge."""
        if self.badge:
            self.redraw()
        else:
            self._update_placeholder()

    def _update_placeholder(self):
        if self._phwin is None:
            return
        try:
            self.cv.itemconfigure(self._phwin, state="hidden" if self.var.get() else "normal")
        except tk.TclError:
            pass

    def redraw(self):
        app, c, px, P, cv = self.app, self.app.c, self.app.px, self.app.painter, self.cv
        try:
            w, h = cv.winfo_width(), cv.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            return
        cv.delete("deco")
        bg, fbg = self.cget("bg"), c[self.bg_key]
        focused = self.has_focus() and not self.disabled
        inset = px(3) if self.ring else 0
        corner_bg = bg
        accent = self.accent[0] if self.accent else c.focus
        if self.plain:
            cv.create_rectangle(0, 0, w, h, fill=fbg, width=0, tags="deco")
        else:
            if self.ring and focused:
                ring = accent_ring(accent, bg)
                P.round_rect(cv, 0, 0, w, h, self.radius + inset, ring, ring, bg, tags="deco")
                corner_bg = ring
            outline = accent if focused else c.border
            P.round_rect(cv, inset, inset, w - inset, h - inset, self.radius, fbg, outline, corner_bg, tags="deco")
        x = inset + px(14)
        if self.icon_name:
            draw_icon(cv, app.fonts, self.icon_name, x + px(8), h / 2, px(17), c.muted, tags="deco")
            x += px(28)
        right = w - inset - px(12)
        self._action_x = None
        if self.kbd:
            tw = app.fonts.tiny.measure(self.kbd)
            kx0 = right - tw - px(14)
            P.round_rect(cv, kx0, h / 2 - px(11), right, h / 2 + px(11), px(6), fbg, c.border, fbg, tags="deco")
            cv.create_text((kx0 + right) / 2, h / 2, text=self.kbd, font=app.fonts.tiny, fill=c.faint, tags="deco")
            right = kx0 - px(10)
        if self.action_icon:
            ax = right - px(10)
            draw_icon(cv, app.fonts, self.action_icon, ax, h / 2, px(15), c.muted, tags="deco")
            self._action_x = (ax - px(16), ax + px(16))
            right = ax - px(20)
        if self.badge:
            info = self.badge()
            if info:
                text, color, icon = (tuple(info) + ("check",))[:3]
                tw = app.fonts.tiny.measure(text)
                cv.create_text(right, h / 2, text=text, font=app.fonts.tiny, fill=color, anchor="e", tags="deco")
                draw_icon(cv, app.fonts, icon, right - tw - px(9), h / 2, px(12), color, tags="deco")
                right -= tw + px(26)
        eh = self.font.metrics("linespace") + px(2)
        width = max(px(20), right - x)
        if self._win is None:
            self._win = cv.create_window(x, h / 2, anchor="w", window=self.entry, width=width, height=eh)
            self._phwin = cv.create_window(x + px(2), h / 2, anchor="w", window=self.ph, width=width - px(2),
                                           height=eh)
        else:
            cv.coords(self._win, x, h / 2)
            cv.itemconfigure(self._win, width=width)
            cv.coords(self._phwin, x + px(2), h / 2)
            cv.itemconfigure(self._phwin, width=width - px(2))
        cv.tag_lower("deco")
        self._update_placeholder()


class Select(Widget):
    """Liste déroulante (ouvre un menu dessiné par l'application)."""

    def __init__(self, parent, app, options, value, on_change, height=52, width=None, font=None, bg_key="field",
                 popup_width=None):
        self.options, self.value, self.on_change = options, value, on_change
        self.font = font or app.fonts.body
        self.bg_key = bg_key
        self.popup_width = popup_width
        w = app.px(width) if width else self._natural_width(app)
        super().__init__(parent, app, width=w, height=app.px(height), command=self.open)

    def _natural_width(self, app):
        widest = max([self.font.measure(lbl) for _, lbl in self.options] or [app.px(40)])
        return max(app.px(110), widest + app.px(14 + 38))

    def label(self):
        return next((lbl for v, lbl in self.options if v == self.value), self.value or "—")

    def set_options(self, options, value):
        self.options, self.value = options, value
        self.redraw()

    def open(self):
        if self.app.popover.is_open_for(self):
            self.app.popover.close()
            return
        items = [{"label": lbl, "value": v, "selected": v == self.value} for v, lbl in self.options]
        width = max(self.winfo_width(), self.app.px(self.popup_width or 160))
        self.app.popover.show(self, items, self._pick, width=width)

    def _pick(self, item):
        self.value = item["value"]
        self.redraw()
        if self.on_change:
            self.on_change(item["value"])

    def draw(self, w, h):
        c, bg, px = self.c, self.cget("bg"), self.px
        fbg = c[self.bg_key]
        self.P.round_rect(self, 0, 0, w, h, px(10) if h > px(44) else px(8), fbg,
                          c.border_strong if self.hover and not self.disabled else c.border, bg)
        fg = c.faint if self.disabled else c.text
        self.create_text(px(14), h / 2, text=fit_text(self.font, self.label(), w - px(46)), font=self.font, fill=fg,
                         anchor="w")
        self.icon("chevron_down", w - px(18), h / 2, px(11), c.muted)


class Switch(Widget):
    def __init__(self, parent, app, value, on_change=None, accent=None):
        self.value, self.on_change, self.accent = bool(value), on_change, accent
        super().__init__(parent, app, width=app.px(40), height=app.px(22), command=self.toggle)

    def toggle(self):
        self.value = not self.value
        self.redraw()
        if self.on_change:
            self.on_change(self.value)

    def draw(self, w, h):
        c, bg, px = self.c, self.cget("bg"), self.px
        track = (self.accent[0] if self.accent else c.focus) if self.value else c.switch_off
        if self.hover:
            track = mix(track, c.text, 0.08)
        self.P.round_rect(self, 0, 0, w, h, h // 2, track, track, bg)
        d = h - px(6)
        x = w - px(3) - d if self.value else px(3)
        self.P.round_rect(self, x, px(3), x + d, px(3) + d, d // 2, c.knob, c.knob, track)


class Popover:
    """Petit menu flottant (liste de choix, suggestions). Un seul ouvert à la fois."""

    ROWS = 8

    def __init__(self, app):
        self.app = app
        self.cv = None
        self.anchor = None
        self.items = []
        self.hi = None
        self.offset = 0
        self.on_pick = None

    @property
    def is_open(self):
        return self.cv is not None

    def is_open_for(self, anchor):
        return self.cv is not None and self.anchor is anchor

    def show(self, anchor, items, on_pick, width=None, highlight=None):
        self.close()
        if not items:
            return
        app, px = self.app, self.app.px
        self.anchor, self.items, self.on_pick, self.hi, self.offset = anchor, items, on_pick, highlight, 0
        self.row_h, self.pad = px(40), px(6)
        n = min(len(items), self.ROWS)
        h = n * self.row_h + 2 * self.pad
        w = int(width or anchor.winfo_width())
        rx, ry = app.winfo_rootx(), app.winfo_rooty()
        x = anchor.winfo_rootx() - rx
        y = anchor.winfo_rooty() - ry + anchor.winfo_height() + px(6)
        if y + h > app.winfo_height() - px(8):
            y = max(px(8), anchor.winfo_rooty() - ry - h - px(6))
        x = max(px(8), min(x, app.winfo_width() - w - px(8)))
        self.cv = tk.Canvas(app, width=w, height=h, bg=app.c.bg, highlightthickness=0, bd=0, cursor="hand2")
        self.cv.place(x=x, y=y)
        tk.Misc.lift(self.cv)  # Canvas.lift() agit sur les éléments dessinés, pas sur le widget
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<ButtonRelease-1>", self._click)
        self.cv.bind("<MouseWheel>", self._wheel)
        self.cv.bind("<Button-4>", lambda e: self._scroll(-1))
        self.cv.bind("<Button-5>", lambda e: self._scroll(1))
        self.draw()

    def close(self):
        if self.cv is not None:
            try:
                self.cv.destroy()
            except tk.TclError:
                pass
        self.cv = None
        self.anchor = None

    def contains(self, widget):
        return self.cv is not None and _is_inside(widget, self.cv)

    def _index_at(self, y):
        i = int((y - self.pad) // self.row_h)
        k = i + self.offset
        return k if 0 <= i < self.ROWS and 0 <= k < len(self.items) else None

    def _motion(self, e):
        i = self._index_at(e.y)
        if i != self.hi:
            self.hi = i
            self.draw()

    def _click(self, e):
        i = self._index_at(e.y)
        if i is not None:
            self.pick(i)

    def _wheel(self, e):
        self._scroll(-1 if e.delta > 0 else 1)

    def _scroll(self, d):
        self.offset = max(0, min(self.offset + d, len(self.items) - self.ROWS))
        self.draw()

    def move(self, d):
        if not self.items:
            return
        self.hi = 0 if self.hi is None else max(0, min(len(self.items) - 1, self.hi + d))
        if self.hi < self.offset:
            self.offset = self.hi
        elif self.hi >= self.offset + self.ROWS:
            self.offset = self.hi - self.ROWS + 1
        self.draw()

    def pick(self, index=None):
        index = self.hi if index is None else index
        if index is None or not (0 <= index < len(self.items)):
            return False
        item, cb = self.items[index], self.on_pick
        self.close()
        if cb:
            cb(item)
        return True

    def draw(self):
        if self.cv is None:
            return
        app, c, px, P, cv = self.app, self.app.c, self.app.px, self.app.painter, self.cv
        cv.delete("all")
        w, h = int(cv.cget("width")), int(cv.cget("height"))
        P.round_rect(cv, 0, 0, w, h, px(10), c.popover, c.border_strong, c.bg)
        draw_rows(cv, app, self.items, self.hi, self.offset, self.ROWS, self.pad, self.row_h, w, c.popover)


def draw_rows(cv, app, items, hi, offset, max_rows, pad, row_h, w, bg):
    """Lignes de choix / suggestions (partagé par le menu flottant et le mode mini)."""
    c, px, P, f = app.c, app.px, app.painter, app.fonts
    hover_bg = mix(bg, "#808080", 0.16)
    for row in range(min(max_rows, len(items) - offset)):
        k = row + offset
        item = items[k]
        y0 = pad + row * row_h
        yc = y0 + row_h / 2
        row_bg = hover_bg if k == hi else bg
        if k == hi:
            P.round_rect(cv, pad, y0, w - pad, y0 + row_h, px(7), hover_bg, hover_bg, bg)
        x = pad + px(12)
        if item.get("icon"):
            draw_icon(cv, f, item["icon"], x + px(7), yc, px(14), item.get("icon_color") or c.muted)
            x += px(26)
        right = w - pad - px(12)
        if item.get("selected"):
            draw_icon(cv, f, "check", right - px(6), yc, px(13), c.text)
            right -= px(24)
        if item.get("right"):
            rt = item["right"]
            cv.create_text(right, yc, text=rt, font=f.tiny, fill=item.get("right_color") or c.muted, anchor="e")
            if item.get("right_dot"):
                P.circle(cv, right - f.tiny.measure(rt) - px(9), yc, px(7), item["right_dot"], bg=row_bg)
                right -= px(14)
            right -= f.tiny.measure(rt) + px(12)
        label = item["label"]
        bold = item.get("bold", 0)
        avail = right - x
        if bold and label.lower().startswith(item.get("query", "").lower()):
            head, tail = label[:bold], label[bold:]
            cv.create_text(x, yc, text=head, font=f.body_semi, fill=c.text, anchor="w")
            cv.create_text(x + f.body_semi.measure(head), yc,
                           text=fit_text(f.body, tail, avail - f.body_semi.measure(head)), font=f.body,
                           fill=c.text, anchor="w")
        else:
            cv.create_text(x, yc, text=fit_text(f.body, label, avail), font=f.body, fill=c.text, anchor="w")


def _is_inside(widget, container):
    try:
        while widget is not None:
            if widget is container:
                return True
            widget = widget.master
    except AttributeError:
        pass
    return False


class ThinScrollbar(tk.Canvas):
    """Barre de défilement fine, cachée quand tout le contenu est visible."""

    def __init__(self, parent, app, target):
        super().__init__(parent, width=app.px(10), bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.app, self.target = app, target
        self.first, self.last = 0.0, 1.0
        self._drag = None
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self.draw()

    def draw(self):
        self.delete("all")
        if self.last - self.first >= 0.999:
            return
        h = self.winfo_height()
        px = self.app.px
        y0 = self.first * h
        y1 = max(y0 + px(24), self.last * h)
        self.app.painter.round_rect(self, px(3), y0 + px(2), px(8), y1 - px(2), px(3), self.app.c.scroll,
                                    self.app.c.scroll, self.cget("bg"))

    def _press(self, e):
        h = max(1, self.winfo_height())
        pos = e.y / h
        if not (self.first <= pos <= self.last):
            self.target.yview_moveto(max(0.0, pos - (self.last - self.first) / 2))
        self._drag = (e.y, self.first)

    def _move(self, e):
        if self._drag:
            h = max(1, self.winfo_height())
            y, first = self._drag
            self.target.yview_moveto(first + (e.y - y) / h)


class ScrollArea(tk.Frame):
    def __init__(self, parent, app, bg):
        super().__init__(parent, bg=bg)
        self.app = app
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = ThinScrollbar(self, app, self.canvas)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.body = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, anchor="nw", window=self.body)
        self._region_job = None
        self.body.bind("<Configure>", self._body_changed)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)

    def _body_changed(self, e):
        # Une seule mise à jour de la zone de défilement par passage, pas une par ligne ajoutée
        if self._region_job is None:
            self._region_job = self.after_idle(self._update_region)

    def _update_region(self):
        self._region_job = None
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

    def destroy(self):
        if self._region_job is not None:
            self.after_cancel(self._region_job)
            self._region_job = None
        super().destroy()

    def _bind_wheel(self, e):
        self.bind_all("<MouseWheel>", self._wheel)
        self.bind_all("<Button-4>", lambda ev: self._scroll(-1))
        self.bind_all("<Button-5>", lambda ev: self._scroll(1))

    def _unbind_wheel(self, e):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _wheel(self, e):
        self._scroll(-1 if e.delta > 0 else 1)

    def _scroll(self, d):
        if self.bar.last - self.bar.first < 0.999:
            self.canvas.yview_scroll(d * 3, "units")


class Toast(tk.Canvas):
    """Notification non bloquante, en bas de la fenêtre."""

    def __init__(self, app, text, kind="ok", action=None, duration=2800, bottom=60):
        c, f, px = app.c, app.fonts, app.px
        self.app, self.action, self.kind = app, action, kind
        bg_ = c.text
        fg = c.bg
        tw = f.small_semi.measure(text)
        aw = f.small_semi.measure(action[0]) + px(20) if action else 0
        w = px(16) + px(18) + tw + aw + px(16)
        h = px(40)
        super().__init__(app, width=w, height=h, bg=c.bg, highlightthickness=0, bd=0)
        app.painter.round_rect(self, 0, 0, w, h, px(10), bg_, bg_, c.bg)
        dot = {"ok": c.ok, "warn": c.warn, "error": c.error}.get(kind, c.ok)
        if not c.dark:
            dot = {"ok": "#3DD68C", "warn": "#F5A524", "error": "#F87171"}.get(kind, "#3DD68C")
        app.painter.circle(self, px(16) + px(4), h / 2, px(8), dot, bg=bg_)
        self.create_text(px(34), h / 2, text=text, font=f.small_semi, fill=fg, anchor="w")
        if action:
            ax = px(34) + tw + px(16)
            color = readable_on(bg_, app.accent[0])
            self.create_text(ax, h / 2, text=action[0], font=f.small_semi, fill=color, anchor="w", tags="action")
            self.tag_bind("action", "<Enter>", lambda e: self.configure(cursor="hand2"))
            self.tag_bind("action", "<Leave>", lambda e: self.configure(cursor=""))
            self.tag_bind("action", "<ButtonRelease-1>", self._act)
        self.place(relx=0.5, rely=1.0, y=-bottom, anchor="s")
        tk.Misc.lift(self)
        self._job = self.after(duration, self.dismiss)

    def _act(self, e):
        cb = self.action[1]
        self.dismiss()
        cb()

    def dismiss(self):
        try:
            self.after_cancel(self._job)
        except Exception:
            log.debug("erreur ignorée", exc_info=True)
        try:
            self.destroy()
        except tk.TclError:
            pass
