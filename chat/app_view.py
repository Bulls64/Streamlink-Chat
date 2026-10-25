"""Onglets de chaîne et vue d'un chat (zone de messages).

Channel tabs and chat view (message area)."""
import logging
import time
import tkinter as tk
from collections import Counter, deque

from . import config
from .common import default_color, readable_color
from .ui.theme import mix
from .ui.widgets import ThinScrollbar, Widget

log = logging.getLogger("streamlink_launcher")


class Tab:
    def __init__(self, platform, channel):
        self.platform, self.channel = platform, channel
        self.title = channel
        self.status, self.detail = "connecting", ""
        self.unread, self.mentioned = 0, False
        self.info = {}
        self.view = None
        self.history = deque(maxlen=1000)
        self.chatters = {}          # pseudo en minuscules -> pseudo affiché (complétion avec Tab)
                                    # lowercase username -> displayed username (completion with Tab)

    @property
    def key(self):
        return (self.platform, self.channel)


# =====================================================
# Composants
# Components
# =====================================================
class ChannelTab(Widget):
    """Onglet d'un chat : pastille de plateforme, nom, compteur de messages non lus, croix au survol.

    Tab of a chat: platform dot, name, unread message counter, cross on hover."""

    zone_cursor = True

    def __init__(self, parent, app, tab, selected, on_select, on_close, on_menu):
        self.tab, self.selected = tab, selected
        self.on_select, self.on_close = on_select, on_close
        super().__init__(parent, app, width=self._width(app), height=app.px(34), command=on_select)
        self.bind("<ButtonRelease-3>", lambda e: on_menu(self))
        self.bind("<ButtonRelease-2>", lambda e: on_close())

    def _badge_text(self):
        t = self.tab
        if self.selected or not t.unread:
            return ""
        return "99+" if t.unread > 99 else str(t.unread)

    def _width(self, app):
        f = app.fonts
        w = app.px(12) + app.px(16) + f.small_semi.measure(self.tab.title) + app.px(10) + app.px(22)
        badge = self._badge_text()
        if badge:
            w += f.tiny.measure(badge) + app.px(14)
        return w

    def refresh(self, selected=None):
        if selected is not None:
            self.selected = selected
        self.configure(width=self._width(self.app))
        self.redraw()

    def zone_at(self, x, y):
        w = self.winfo_width()
        return "close" if x >= w - self.px(26) else "tab"

    def on_click(self, e):
        if self.zone_at(e.x, e.y) == "close":
            self.on_close()
        else:
            self.on_select()

    def draw(self, w, h):
        c, bg, px, t = self.c, self.cget("bg"), self.px, self.tab
        color, on = config.PLATFORMS[t.platform][1:]
        r = h // 2
        if self.selected:
            self.P.round_rect(self, 0, 0, w, h, r, color, color, bg)
            fill, fg, dot = color, on, on
        else:
            fill = c.hover(bg) if self.hover else bg
            border = c.warn if t.mentioned else (c.border_strong if self.hover else c.border)
            if not t.mentioned and self.app.cfg["platform_colors"]:
                border = mix(border, color, 0.65 if self.hover else 0.45)
            self.P.round_rect(self, 0, 0, w, h, r, fill, border, bg)
            fg, dot = (c.text if t.unread or self.hover else c.muted), color
            if t.status in ("error", "reconnecting"):
                dot = c.error if t.status == "error" else c.warn
        x = px(12)
        self.P.circle(self, x + px(4), h / 2, px(8), dot, bg=fill)
        x += px(16)
        font = self.app.fonts.small_semi
        self.create_text(x, h / 2, text=t.title, font=font, fill=fg, anchor="w")
        x += font.measure(t.title) + px(8)
        badge = self._badge_text()
        if badge:
            bw = self.app.fonts.tiny.measure(badge) + px(10)
            bc = c.warn if t.mentioned else mix(fill, c.text, 0.18)
            self.P.round_rect(self, x, h / 2 - px(9), x + bw, h / 2 + px(9), px(9), bc, bc, fill)
            self.create_text(x + bw / 2, h / 2, text=badge, font=self.app.fonts.tiny,
                             fill="#000000" if t.mentioned else c.text)
        close_color = fg if (self.hover and self.zone == "close") else mix(fg, fill, 0.45)
        self.icon("close", w - px(15), h / 2, px(10), close_color)


class ChatView:
    """Un tk.Text par onglet : lignes de messages, badges, emotes en images, liens, mentions.

    One tk.Text per tab: message lines, badges, emotes as images, links, mentions."""

    def __init__(self, app, parent, tab):
        self.app, self.tab = app, tab
        c, px = app.c, app.px
        self.bg = bg = app.card_colors(tab.platform)[0]
        self.frame = tk.Frame(parent, bg=bg)
        self.text = tk.Text(self.frame, bg=bg, fg=c.text, font=app.chat_font, wrap="word", bd=0, highlightthickness=0,
                            padx=px(14), pady=px(10), spacing1=px(3), spacing3=px(3), cursor="arrow",
                            insertwidth=0, takefocus=0, selectbackground=mix(bg, app.accent[0], 0.40),
                            inactiveselectbackground=mix(bg, app.accent[0], 0.30), selectforeground=c.text,
                            exportselection=True, undo=False, height=1, width=1)
        self.bar = ThinScrollbar(self.frame, app, self.text)
        self.text.configure(yscrollcommand=self._yscroll)
        self.bar.pack(side="right", fill="y", padx=(0, px(3)), pady=px(6))
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<Key>", lambda e: None if (e.state & 0x4 and e.keysym.lower() in ("c", "a")) else "break")
        self.text.bind("<Button-3>", self._context)
        self.text.bind("<Button-1>", lambda e: self.text.focus_set(), add="+")
        self.first_n = 1          # numéro du message affiché sur la ligne 1
                                  # number of the message shown on line 1
        self.next_n = 1
        self.emote_urls = Counter()  # url -> nombre d'apparitions dans ce chat (emotes à garder en mémoire)
                                     # url -> occurrences in this chat (emotes to keep in memory)
        self.lines = deque()      # messages affichés, dans l'ordre des lignes
                                  # displayed messages, in line order
        self.by_id = {}
        self.by_user = {}
        self.at_bottom = True
        self._setup_tags()

    # --- apparence
    # --- appearance
    def _setup_tags(self):
        app, c = self.app, self.app.c
        t, bg = self.text, self.bg
        t.tag_configure("time", foreground=c.faint, font=app.chat_small)
        t.tag_configure("name", font=app.chat_bold)
        t.tag_configure("mention", font=app.chat_bold)
        t.tag_configure("link", foreground="#8AB4F8" if c.dark else "#1A56DB", underline=True)
        t.tag_configure("reply", foreground=c.faint, font=app.chat_small)
        t.tag_configure("notice", foreground=c.muted, font=app.chat_small)
        t.tag_configure("event", background=mix(bg, app.accent[0], 0.12), foreground=c.text)
        t.tag_configure("mention_line", background=mix(bg, c.warn, 0.16))
        t.tag_configure("first_line", background=mix(bg, c.ok, 0.10))
        t.tag_configure("highlight_line", background=mix(bg, "#9146FF", 0.16))
        t.tag_configure("own_line", background=mix(bg, c.text, 0.035))
        t.tag_configure("deleted", overstrike=True, foreground=c.faint)
        t.tag_bind("badge", "<Enter>", self._badge_enter)
        t.tag_bind("badge", "<Leave>", lambda e: self.app.hide_tip())
        t.tag_configure("emote_text", foreground=c.muted)
        t.tag_raise("deleted")
        t.tag_raise("sel")
        for tag in ("name", "mention"):
            t.tag_bind(tag, "<Enter>", lambda e: t.configure(cursor="hand2"))
            t.tag_bind(tag, "<Leave>", lambda e: t.configure(cursor="arrow"))
            t.tag_bind(tag, "<ButtonRelease-1>", self._user_click)
        t.tag_bind("link", "<Enter>", lambda e: t.configure(cursor="hand2"))
        t.tag_bind("link", "<Leave>", lambda e: t.configure(cursor="arrow"))
        t.tag_bind("link", "<ButtonRelease-1>", self._link_click)

    def color_tag(self, color):
        tag = "c" + color[1:]
        if tag not in self.text.tag_names():
            self.text.tag_configure(tag, foreground=color)
            self.text.tag_lower(tag, "deleted")
        return tag

    # --- défilement
    # --- scrolling
    def _yscroll(self, first, last):
        self.bar.set(first, last)
        self.at_bottom = float(last) >= 0.999
        self.app.update_more_button(self)

    def scroll_to_end(self):
        self.text.yview_moveto(1.0)
        self.at_bottom = True
        self.app.update_more_button(self)

    # --- messages
    # --- messages
    def add(self, messages):
        t = self.text
        stick = self.at_bottom
        t.configure(state="normal")
        try:
            for msg in messages:
                self._insert(msg)
            self._trim(stick)
        finally:
            t.configure(state="disabled")
        if stick:
            t.yview_moveto(1.0)

    def _trim(self, stick):
        limit = self.app.cfg["max_messages"]
        excess = len(self.lines) - limit
        if excess <= 0 or (not stick and len(self.lines) < limit * 1.5):
            return
        self.text.delete("1.0", f"{excess + 1}.0")
        for _ in range(excess):
            msg = self.lines.popleft()
            if msg.id:
                self.by_id.pop(msg.id, None)
            for frag in msg.fragments or ():
                if frag[0] == "emote":
                    self.emote_urls[frag[2]] -= 1
                    if self.emote_urls[frag[2]] <= 0:
                        del self.emote_urls[frag[2]]
                        self.app._anims_dirty = True
        self.first_n += excess

    def _insert(self, msg):
        app, t, cfg = self.app, self.text, self.app.cfg
        start = t.index("end-1c")
        base = ()
        if cfg["timestamps"]:
            t.insert("end", time.strftime("%H:%M", time.localtime(msg.ts)) + " ", ("time",))
        if msg.reply_to:
            t.insert("end", f"↪ @{msg.reply_to} ", ("reply",))
        if msg.kind in ("notice",):
            base = ("notice",)
        elif msg.kind != "event":
            if cfg["badges"]:
                for kind, label in msg.badges:
                    idx = t.index("end-1c")
                    t.image_create("end", image=app.badge_image(kind, msg.platform), padx=1, align="center")
                    t.tag_add("badge", idx)
                    t.tag_add(app.badge_label_tag(label), idx)
                if msg.badges:
                    t.insert("end", " ")
            color = readable_color(msg.color or default_color(msg.user or msg.display_name), self.bg) \
                or app.c.text
            ctag = self.color_tag(color)
            name = msg.display_name
            if msg.user and not msg.display_name.isascii() and msg.platform == "twitch":
                name = f"{msg.display_name} ({msg.user})"  # pseudo affiché dans une autre écriture
                                                           # display name in another script
            t.insert("end", name, ("name", ctag), " " if msg.kind == "action" else ": ", ())
            if msg.kind == "action":
                base = (ctag,)
        for frag in msg.fragments or [("text", msg.text)]:
            kind = frag[0]
            if kind == "text":
                t.insert("end", frag[1], base)
            elif kind == "link":
                t.insert("end", frag[1], ("link",) + base)
            elif kind == "mention":
                t.insert("end", frag[1], ("mention",) + base)
            elif kind == "emote":
                self._emote(frag[1], frag[2], base)
        t.insert("end", "\n")
        line_tag = None
        if msg.kind == "event":
            line_tag = "event"
        elif msg.highlight:
            line_tag = "highlight_line"
        elif msg.kind == "msg" and app.is_mention(self.tab, msg):
            line_tag = "mention_line"
        elif msg.first:
            line_tag = "first_line"
        elif msg.own:
            line_tag = "own_line"
        if line_tag:
            t.tag_add(line_tag, start, "end-1c")
        if msg.deleted:
            t.tag_add("deleted", start, "end-1c")
        n = self.next_n
        self.next_n += 1
        self.lines.append(msg)
        if msg.id:
            self.by_id[msg.id] = n
        if msg.user:
            self.tab.chatters[msg.user] = msg.display_name

    def _emote(self, name, url, base):
        app, t = self.app, self.text
        if not self.emote_urls[url]:
            app._anims_dirty = True
        self.emote_urls[url] += 1
        img = app.emote_image(url)
        if img:
            t.image_create("end", image=img, padx=1, align="center")
        elif img is None:  # en cours de chargement
                           # loading
            t.insert("end", name, (app.emote_tag(url), "emote_text") + base)
        else:  # image illisible : le nom reste en texte
               # unreadable image: the name stays as text
            t.insert("end", name, base)

    def image_ready(self, url, img):
        tag = self.app.emote_tag(url)
        ranges = self.text.tag_ranges(tag)
        if not ranges:
            return
        self.text.configure(state="normal")
        try:
            for i in range(len(ranges) - 2, -1, -2):
                a, b = ranges[i], ranges[i + 1]
                if img:
                    self.text.delete(a, b)
                    self.text.image_create(a, image=img, padx=1, align="center")
                else:  # illisible : le nom reste, en texte normal
                       # unreadable: the name stays, as normal text
                    self.text.tag_remove(tag, a, b)
                    self.text.tag_remove("emote_text", a, b)
        finally:
            self.text.configure(state="disabled")
        if self.at_bottom:
            self.text.yview_moveto(1.0)

    def _badge_enter(self, e):
        idx = self.text.index(f"@{e.x},{e.y}")
        label = next((self.app.badge_labels[t] for t in self.text.tag_names(idx) if t in self.app.badge_labels), "")
        if label:
            self.app.show_tip(label, e.x_root, e.y_root)

    def _line_of(self, n):
        line = n - self.first_n + 1
        return line if 1 <= line <= len(self.lines) else None

    def delete_message(self, mid):
        n = self.by_id.get(mid)
        line = self._line_of(n) if n else None
        if line:
            self.lines[line - 1].deleted = True
            self.text.tag_add("deleted", f"{line}.0", f"{line}.end")

    def clear_user(self, user):
        for i, msg in enumerate(self.lines):
            if msg.user == user and not msg.deleted:
                msg.deleted = True
                self.text.tag_add("deleted", f"{i + 1}.0", f"{i + 1}.end")

    # --- interactions
    # --- interactions
    def _message_at(self, e):
        idx = self.text.index(f"@{e.x},{e.y}")
        line = int(idx.split(".")[0])
        return self.lines[line - 1] if 1 <= line <= len(self.lines) else None

    def _user_click(self, e):
        msg = self._message_at(e)
        if not msg:
            return
        word = None
        idx = self.text.index(f"@{e.x},{e.y}")
        if "mention" in self.text.tag_names(idx):
            r = self.text.tag_prevrange("mention", idx + "+1c")
            word = self.text.get(*r).lstrip("@").rstrip(",.:!?") if r else None
        self.app.user_menu(self, e, word or msg.display_name, None if word else msg)

    def _link_click(self, e):
        idx = self.text.index(f"@{e.x},{e.y}")
        r = self.text.tag_prevrange("link", idx + "+1c")
        if r:
            url = self.text.get(*r)
            self.app.open_url(url if "://" in url else "https://" + url)

    def _context(self, e):
        msg = self._message_at(e)
        if msg:
            self.app.message_menu(self, e, msg)

    def destroy(self):
        self.frame.destroy()
