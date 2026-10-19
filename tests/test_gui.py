"""Test de fumée de l'interface (ignoré sans écran ; sous Linux : xvfb-run -a python -m unittest tests.test_gui)."""
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
    HAVE_DISPLAY = False


class Dummy:
    """Connexion factice : rejoint aussitôt, n'écrit pas."""
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
