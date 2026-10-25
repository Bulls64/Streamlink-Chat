"""Badges, infobulles, emotes et leurs images (cache, animation).

Badges, tooltips, emotes and their images (cache, animation)."""
import base64
import hashlib
import logging
import time
import tkinter as tk

from . import badges, config, emotes
from .app_common import IMAGE_CACHE, MAX_FRAMES

log = logging.getLogger("streamlink_launcher")


class MediaMixin:
    """Badges, infobulles, emotes et leurs images (cache, animation).

    Badges, tooltips, emotes and their images (cache, animation)."""

    # =====================================================
    # Badges et infobulles
    # Badges and tooltips
    # =====================================================
    def badge_image(self, kind, platform):
        size = self.px(18)
        key = (kind, platform if kind == "subscriber" else "", size)
        img = self.badge_images.get(key)
        if img is None:
            color, fg = (config.PLATFORMS[platform][1:] if kind == "subscriber" else (None, "#FFFFFF"))
            img = self.badge_images[key] = tk.PhotoImage(master=self, data=badges.badge_b64(kind, size, color, fg))
        return img

    def badge_label_tag(self, label):
        tag = self.badge_tags.get(label)
        if tag is None:
            tag = self.badge_tags[label] = f"bl{len(self.badge_tags)}"
            self.badge_labels[tag] = label
        return tag

    def show_tip(self, text, x_root, y_root):
        self.hide_tip()
        c, f = self.c, self.fonts
        tip = self._tip = tk.Label(self, text=text, font=f.tiny, bg=c.text, fg=c.bg, padx=self.px(8),
                                   pady=self.px(3))
        tip.place(x=x_root - self.winfo_rootx() + self.px(10), y=y_root - self.winfo_rooty() - self.px(30))
        tk.Misc.lift(tip)

    def hide_tip(self):
        tip = getattr(self, "_tip", None)
        if tip is not None:
            tip.destroy()
            self._tip = None

    # =====================================================
    # Emotes
    # =====================================================
    def emote_tag(self, url):
        return "em_" + hashlib.md5(url.encode()).hexdigest()[:12]

    def emote_image(self, url):
        """PhotoImage si prête, None si en cours de chargement, False si illisible.

        PhotoImage if ready, None if loading, False if unreadable."""
        if url in self.images:
            self.images.move_to_end(url)
            return self.images[url]
        self.images[url] = None
        self.loader.request(url, lambda u, data: self.events.put(("call", self._image_loaded, (u, data))))
        return None

    def _image_loaded(self, payload):
        url, data = payload
        if self.images.get(url):
            return  # déjà chargée (deux demandes simultanées)
                    # already loaded (two simultaneous requests)
        img = False
        if data:
            try:
                kind = emotes.image_kind(data)
                img = tk.PhotoImage(master=self, data=base64.b64encode(data), format=kind)
                if kind == "gif":
                    delays = emotes.gif_frames(data)
                    if len(delays) > 1:
                        # images décodées plus tard, seulement si l'emote est dans le chat affiché
                        # frames decoded later, only if the emote is in the displayed chat
                        self.gifs[url] = (data, delays)
                        self._anims_dirty = True
            except tk.TclError:
                img = False
        self.images[url] = img
        for tab in self.tabs:
            if tab.view:
                tab.view.image_ready(url, img or None)
        self._evict_images()

    def _in_use(self):
        """Emotes présentes dans un chat ouvert : jamais retirées de la mémoire (Tk les affiche).

        Emotes present in an open chat: never removed from memory (Tk displays them)."""
        used = set()
        for tab in self.tabs:
            if tab.view:
                used.update(tab.view.emote_urls)
        return used

    def _evict_images(self):
        """Retire les emotes les moins récemment vues au-delà de IMAGE_CACHE, sauf celles encore affichées.

        Removes the least recently seen emotes beyond IMAGE_CACHE, except those still displayed."""
        extra = len(self.images) - IMAGE_CACHE
        if extra <= 0:
            return
        used = self._in_use()
        for url in list(self.images):
            if extra <= 0:
                break
            if url in used or self.images[url] is None:  # affichée, ou en cours de chargement
                continue                                 # displayed, or loading
            del self.images[url]
            self.gifs.pop(url, None)
            self.anims.pop(url, None)
            extra -= 1

    def _gif_decode(self, url):
        """Images d'une emote animée, au plus MAX_FRAMES (les délais des images sautées s'additionnent).

        Frames of an animated emote, at most MAX_FRAMES (the delays of skipped frames add up)."""
        data, delays = self.gifs[url]
        step = -(-len(delays) // MAX_FRAMES)
        b64 = base64.b64encode(data)
        frames = []
        for i in range(0, len(delays), step):
            img = tk.PhotoImage(master=self, data=b64, format=f"gif -index {i}")
            frames.append((img, sum(delays[i:i + step])))
        return frames

    def _sync_anims(self):
        """Anime seulement les emotes du chat affiché : les images des autres sont libérées.

        Animates only the emotes of the displayed chat: the frames of the others are freed."""
        self._anims_dirty = False
        view = self.current.view if self.current else None
        wanted = set()
        if self.cfg["animated"] and view:
            wanted = {u for u in view.emote_urls if u in self.gifs and self.images.get(u)}
        for url in list(self.anims):
            if url not in wanted:
                img, frames = self.anims.pop(url)[:2]
                try:  # l'emote reste sur sa première image
                      # the emote stays on its first frame
                    img.tk.call(img, "copy", frames[0][0], "-compositingrule", "set")
                except tk.TclError:
                    pass
        now = time.time()
        for url in wanted - self.anims.keys():
            try:
                frames = self._gif_decode(url)
            except tk.TclError:
                self.gifs.pop(url, None)
                continue
            self.anims[url] = [self.images[url], frames, 0, now + frames[0][1] / 1000]

    def _animate(self):
        if self._anims_dirty:
            self._sync_anims()
        if self.anims:
            now = time.time()
            for anim in self.anims.values():
                if now >= anim[3]:
                    anim[2] = (anim[2] + 1) % len(anim[1])
                    frame, delay = anim[1][anim[2]]
                    try:
                        anim[0].tk.call(anim[0], "copy", frame, "-compositingrule", "set")
                    except tk.TclError:
                        pass
                    anim[3] = now + delay / 1000
        self.after(40, self._animate)

    def _load_global_emotes(self):
        providers = tuple(self.cfg["providers"])
        if not providers:
            return
        self.run_in_thread(lambda: emotes.fetch_global(providers), self._global_emotes_loaded)

    def _global_emotes_loaded(self, result):
        if isinstance(result, dict):
            self.global_emotes = result
            self._rebuild_emote_maps()

    def _load_channel_emotes(self, tab):
        providers = tuple(self.cfg["providers"])
        uid = tab.info.get("room_id") or (tab.info.get("user_id") if tab.platform == "kick" else None)
        if not providers or not uid or tab.platform == "steamtv":
            return
        key = tab.key
        self.run_in_thread(lambda: emotes.fetch_channel(tab.platform, uid, providers),
                           lambda r: self._channel_emotes_loaded(key, r))

    def _channel_emotes_loaded(self, key, result):
        if isinstance(result, dict):
            self.channel_emotes[key] = result
            self._rebuild_emote_maps()

    def _rebuild_emote_maps(self):
        maps = {}
        for tab in self.tabs:
            base = self.global_emotes if tab.platform == "twitch" else {}
            maps[tab.key] = {**base, **self.channel_emotes.get(tab.key, {})}
        self.emote_maps = maps
        self.emote_names = {url: name for m in maps.values() for name, url in m.items()}

    # =====================================================
