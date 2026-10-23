"""Test de fumée de l'interface (ignoré sans écran ; sous Linux : xvfb-run -a python -m unittest tests.test_gui).

Interface smoke test (skipped without a screen; on Linux: xvfb-run -a python -m unittest tests.test_gui)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_DISPLAY = True
except Exception:  # pas de Tk ou pas d'écran
                   # no Tk or no screen
    HAVE_DISPLAY = False


class Dummy:
    """Connexion factice : rejoint aussitôt, n'écrit pas.

    Fake connection: joins at once, does not write."""
    can_send = False

    def __init__(self, emit, *a, **k):
        self.emit = emit

    def start(self):
        return self

    def join(self, ch):
        self.emit(("status", "twitch", ch, "connected", "ro"))

    def part(self, ch):
        pass

    def stop(self):
        pass


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestGuiSmoke(unittest.TestCase):
    def setUp(self):
        from chat import app as chat_app
        from chat import config, instance
        tmp = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(config, "CONFIG_FILE", tmp / "chat.json"),
                        mock.patch.object(config, "CACHE_DIR", tmp / "cache"),
                        mock.patch.object(instance, "serve", lambda *a, **k: None),
                        mock.patch.object(chat_app.emotes, "fetch_global", lambda *a, **k: {}),
                        mock.patch.object(chat_app, "TwitchConnection", Dummy)]
        for p in self.patches:
            p.start()
        self.app = chat_app.ChatApp()
        self.app.update()

    def tearDown(self):
        try:
            for job in self.app.tk.splitlist(self.app.tk.call("after", "info")):
                self.app.after_cancel(job)  # plusieurs fenêtres dans un même test / several windows in one run
            self.app.on_close()
        finally:
            for p in self.patches:
                p.stop()

    def pump(self):
        for _ in range(10):
            self.app.update()
            self.app.after(30)

    def test_open_chat_show_messages_settings_theme(self):
        from chat.common import ChatMessage, split_words
        self.app.add_var.set("https://www.twitch.tv/eslcs")
        self.app._add_from_field()
        self.assertEqual([t.key for t in self.app.tabs], [("twitch", "eslcs")])
        msg = ChatMessage("twitch", "eslcs", text="salut @tous", user="ann", display_name="Ann",
                          badges=[("moderator", "Mod")], fragments=split_words("salut @tous"))
        self.app.events.put(("message", msg))
        self.pump()
        view = self.app.current.view
        self.assertIn("Ann: salut @tous", view.text.get("1.0", "end"))
        self.assertEqual(self.app.current.status, "connected")
        fill, _ = self.app.card_colors("twitch")
        self.assertNotEqual(fill, self.app.c.surface)
        self.assertEqual(view.bg, fill)
        self.app.cfg["platform_colors"] = False
        self.assertEqual(self.app.card_colors("twitch")[0], self.app.c.surface)
        self.app.cfg["platform_colors"] = True
        self.app.add_var.set("kick.com/xqc")
        self.assertEqual(self.app.cfg["default_platform"], "kick")
        self.assertTrue(self.app.pills["kick"].selected)
        self.assertFalse(self.app.pills["twitch"].selected)
        self.app.add_var.set("")
        self.app.select_platform("twitch")
        from chat import config
        self.assertEqual(self.app.add_field.accent, config.PLATFORMS["twitch"][1:])
        self.app.open_settings()
        self.app.update()
        self.assertEqual(self.app.panel_kind, "settings")
        for theme in ("light", "dark"):
            self.app.cfg["theme"] = theme
            self.app.build()
            self.pump()
            self.assertEqual(self.app.mode, theme)
            self.assertIn("Ann: salut @tous", self.app.current.view.text.get("1.0", "end"))


if __name__ == "__main__":
    unittest.main()


def tiny_gif(frames):
    """GIF animé 1×1 de `frames` images, sans dépendance.

    1×1 animated GIF with `frames` frames, without dependencies."""
    head = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    frame = b"\x21\xf9\x04\x00\x0a\x00\x00\x00" + b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00" + b"\x02\x02\x44\x01\x00"
    return head + frame * frames + b"\x3b"


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestEmoteMemory(TestGuiSmoke):
    """Emotes : animées seulement dans le chat affiché, images plafonnées, cache limité.

    Emotes: animated only in the displayed chat, capped frames, bounded cache."""

    def _emote_msg(self, channel, url):
        from chat.common import ChatMessage
        return ChatMessage("twitch", channel, text="E", user="ann", display_name="Ann",
                           fragments=[("emote", "E", url)])

    def test_open_chat_show_messages_settings_theme(self):  # déjà couvert par TestGuiSmoke / covered above
        pass

    def test_animations_follow_displayed_chat(self):
        from chat import app as chat_app
        app = self.app
        app.cfg["animated"] = True
        app._image_loaded(("7tv://anim", tiny_gif(100)))
        for ch in ("eslcs", "gotaga"):
            app.add_var.set(ch)
            app._add_from_field()
        a, b = app.tabs
        app.select_tab(a)
        app.events.put(("message", self._emote_msg("eslcs", "7tv://anim")))
        self.pump()
        self.assertIn("7tv://anim", app.anims)
        self.assertLessEqual(len(app.anims["7tv://anim"][1]), chat_app.MAX_FRAMES)
        app.select_tab(b)  # l'emote n'est pas dans ce chat : ses images sont libérées
        self.pump()        # the emote is not in this chat: its frames are freed
        self.assertNotIn("7tv://anim", app.anims)
        app.select_tab(a)
        self.pump()
        self.assertIn("7tv://anim", app.anims)
        app.cfg["animated"] = False
        app._anims_dirty = True
        self.pump()
        self.assertEqual(app.anims, {})

    def test_image_cache_is_bounded(self):
        from chat import app as chat_app
        from chat import badges
        app = self.app
        app.add_var.set("eslcs")
        app._add_from_field()
        app._image_loaded(("7tv://shown", badges.badge_png("sub", 16)))
        app.events.put(("message", self._emote_msg("eslcs", "7tv://shown")))
        self.pump()
        with mock.patch.object(chat_app, "IMAGE_CACHE", 3):
            for i in range(10):
                app._image_loaded((f"7tv://old{i}", badges.badge_png("sub", 16)))
        self.assertLessEqual(len(app.images), 3)
        self.assertIn("7tv://shown", app.images)  # encore affichée : gardée / still displayed: kept
