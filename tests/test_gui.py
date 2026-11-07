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
        from chat import app_connections, config, emotes, instance
        tmp = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(config, "CONFIG_FILE", tmp / "chat.json"),
                        mock.patch.object(config, "CACHE_DIR", tmp / "cache"),
                        mock.patch.object(instance, "serve", lambda *a, **k: None),
                        mock.patch.object(emotes, "fetch_global", lambda *a, **k: {}),
                        mock.patch.object(app_connections, "TwitchConnection", Dummy)]
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
        from chat import app_common
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
        self.assertLessEqual(len(app.anims["7tv://anim"][1]), app_common.MAX_FRAMES)
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
        from chat import app_media, badges
        app = self.app
        app.add_var.set("eslcs")
        app._add_from_field()
        app._image_loaded(("7tv://shown", badges.badge_png("sub", 16)))
        app.events.put(("message", self._emote_msg("eslcs", "7tv://shown")))
        self.pump()
        with mock.patch.object(app_media, "IMAGE_CACHE", 3):
            for i in range(10):
                app._image_loaded((f"7tv://old{i}", badges.badge_png("sub", 16)))
        self.assertLessEqual(len(app.images), 3)
        self.assertIn("7tv://shown", app.images)  # encore affichée : gardée / still displayed: kept


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestLinksAndStatus(TestGuiSmoke):
    """Liens du chat (confirmation, sites approuvés) et avertissement après des échecs répétés.

    Chat links (confirmation, approved sites) and the warning after repeated failures."""

    def test_open_chat_show_messages_settings_theme(self):  # déjà couvert par TestGuiSmoke / covered above
        pass

    def _event(self):
        from types import SimpleNamespace
        app = self.app
        return SimpleNamespace(x_root=app.winfo_rootx() + 40, y_root=app.winfo_rooty() + 40)

    def test_link_confirmation(self):
        app = self.app
        opened = []
        # toast remplacé : le tearDown annule les tâches « after » avant de détruire la fenêtre
        # toast replaced: tearDown cancels the "after" jobs before destroying the window
        with mock.patch.object(app, "open_url", opened.append), mock.patch.object(app, "toast") as toast:
            app.open_chat_link(self._event(), "https://clips.twitch.tv/abc")
            self.assertEqual(opened, ["https://clips.twitch.tv/abc"])  # site d'une plateforme : direct
            self.assertFalse(app.popover.is_open)                      # a platform's site: direct
            app.open_chat_link(self._event(), "https://www.example.com/x")
            self.assertTrue(app.popover.is_open)
            values = [i["value"] for i in app.popover.items]
            self.assertEqual(values, ["open", "trust", "copy", "cancel"])
            self.assertIn("example.com", app.popover.items[0]["label"])
            app.popover.pick(values.index("cancel"))
            self.assertEqual(len(opened), 1)
            app.open_chat_link(self._event(), "https://www.example.com/x")
            app.popover.pick(1)                                        # toujours ouvrir / always open
            self.assertEqual(app.cfg["trusted_links"], ["example.com"])
            toast.assert_called_once()
            self.assertEqual(opened[-1], "https://www.example.com/x")
            app.open_chat_link(self._event(), "https://img.example.com/y")
            self.assertFalse(app.popover.is_open)
            self.assertEqual(opened[-1], "https://img.example.com/y")
            long_host = "paypal.com." + "x" * 60 + ".example.net"
            app.open_chat_link(self._event(), f"https://{long_host}/")
            label = app.popover.items[0]["label"]
            self.assertTrue(label.endswith("example.net"), label)     # la fin du nom reste visible
            app.popover.close()                                        # the end of the name stays visible
            app.cfg["link_confirm"] = False
            app.open_chat_link(self._event(), "https://other.example.org/")
            self.assertEqual(opened[-1], "https://other.example.org/")
        app.open_settings()
        app.update()
        self.assertEqual(app.panel_kind, "settings")

    def test_maybe_changed_warning(self):
        app = self.app
        app.add_var.set("eslcs")
        app._add_from_field()
        self.pump()
        tab = app.current
        with mock.patch.object(app, "toast") as toast:
            for _ in range(3):
                app.events.put(("status", "twitch", "eslcs", "connecting", ""))
                app.events.put(("status", "twitch", "eslcs", "reconnecting", "maybe_changed"))
                self.pump()
            self.assertEqual(toast.call_count, 1)                      # un seul avertissement / a single warning
            self.assertIn(app.t("chat_status_maybe_changed"), app.header_status.cget("text"))
            app.events.put(("status", "twitch", "eslcs", "connected", "ro"))
            app.events.put(("status", "twitch", "eslcs", "reconnecting", "maybe_changed"))
            self.pump()
            self.assertEqual(toast.call_count, 2)                      # de nouveau après une reconnexion réussie
        self.assertEqual(tab.detail, "maybe_changed")                  # again after a successful reconnection


class Writer(Dummy):
    """Connexion factice connectée à un compte : garde les messages envoyés et les renvoie en écho.

    Fake connection logged in to an account: keeps the sent messages and echoes them back."""
    can_send = True

    def __init__(self, emit, *a, **k):
        super().__init__(emit)
        self.sent = []

    def join(self, ch):
        self.emit(("status", "twitch", ch, "connected", "rw"))

    def send_message(self, channel, text):
        from chat.common import ChatMessage, split_words
        self.sent.append((channel, text))
        return ChatMessage("twitch", channel, text=text, user="me", display_name="Me", fragments=split_words(text))


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestGuiFlows(TestGuiSmoke):
    """Parcours de l'interface au-delà du démarrage : onglets, envoi, complétion, menus, paramètres.

    Interface flows beyond start-up: tabs, sending, completion, menus, settings."""

    def test_open_chat_show_messages_settings_theme(self):  # déjà couvert par TestGuiSmoke / covered above
        pass

    def _event(self):
        from types import SimpleNamespace
        app = self.app
        return SimpleNamespace(x_root=app.winfo_rootx() + 40, y_root=app.winfo_rooty() + 40, keysym="a")

    def test_tabs_cycle_close_and_persist(self):
        from chat import config
        app = self.app
        for ch in ("eslcs", "gotaga", "ibai"):
            app.open_tab("twitch", ch)
        self.pump()
        self.assertEqual(app.current.channel, "ibai")
        app.cycle_tab(1)                      # après le dernier, on revient au premier / after the last, back to first
        self.assertEqual(app.current.channel, "eslcs")
        app.cycle_tab(-1)
        self.assertEqual(app.current.channel, "ibai")
        app.close_tab(app.current)
        self.pump()
        self.assertEqual([t.channel for t in app.tabs], ["eslcs", "gotaga"])
        self.assertEqual(app.current.channel, "gotaga")
        saved = [t["channel"] for t in config.load()["tabs"]]
        self.assertEqual(saved, ["eslcs", "gotaga"])
        app.open_tab("twitch", "eslcs")       # déjà ouvert : sélectionné, pas dupliqué / already open: selected, not duplicated
        self.assertEqual(len(app.tabs), 2)
        self.assertEqual(app.current.channel, "eslcs")
        for tab in list(app.tabs):
            app.close_tab(tab)
        self.pump()
        self.assertIsNone(app.current)
        self.assertEqual(config.load()["tabs"], [])

    def test_send_recall_and_complete(self):
        app = self.app
        writer = Writer(app.events.put)
        app.conns["twitch"] = writer
        tab = app.open_tab("twitch", "eslcs")
        self.pump()
        self.assertEqual(tab.status, "connected")
        app.input_var.set("  bonjour le chat  ")
        app.send()
        self.pump()
        self.assertEqual(writer.sent, [("eslcs", "bonjour le chat")])
        self.assertEqual(app.input_var.get(), "")
        self.assertIn("Me: bonjour le chat", tab.view.text.get("1.0", "end"))
        app.input_var.set("")
        app.send()                            # message vide : rien n'est envoyé / empty message: nothing is sent
        self.assertEqual(len(writer.sent), 1)
        app._recall(-1)
        self.assertEqual(app.input_var.get(), "bonjour le chat")
        app._recall(1)
        self.assertEqual(app.input_var.get(), "")
        tab.chatters.update({"annie": "Annie", "anna": "Anna", "bob": "Bob"})
        app.input_var.set("salut @an")
        app.input.entry.icursor("end")
        app._tab_complete(None)
        self.assertEqual(app.input_var.get(), "salut @Anna ")
        app._tab_complete(None)               # Tab de nouveau : candidat suivant / Tab again: next candidate
        self.assertEqual(app.input_var.get(), "salut @Annie ")
        app._reset_complete(self._event())

    def test_send_without_account_opens_settings(self):
        app = self.app
        app.open_tab("twitch", "eslcs")
        self.pump()
        app.input_var.set("hello")
        app.send()
        app.update()
        self.assertEqual(app.panel_kind, "settings")
        self.assertEqual(app.input_var.get(), "hello")  # le texte n'est pas perdu / the text is not lost

    def test_user_and_message_menus(self):
        from chat.common import ChatMessage
        app = self.app
        app.conns["twitch"] = Writer(app.events.put)
        tab = app.open_tab("twitch", "eslcs")
        self.pump()
        msg = ChatMessage("twitch", "eslcs", text="gg", user="ann", display_name="Ann")
        app.user_menu(tab.view, self._event(), "Ann", msg)
        values = [i["value"] for i in app.popover.items]
        self.assertEqual(values, ["mention", "copy", "open", "profile"])
        app.popover.pick(values.index("mention"))
        self.assertEqual(app.input_var.get(), "@Ann ")
        app.user_menu(tab.view, self._event(), "Ann", msg)
        app.popover.pick([i["value"] for i in app.popover.items].index("open"))
        self.assertEqual(app.current.key, ("twitch", "ann"))
        with mock.patch.object(app, "toast"):
            app.message_menu(tab.view, self._event(), msg)
            app.popover.pick(0)
        self.assertEqual(app.clipboard_get(), "gg")

    def test_settings_saved_and_applied(self):
        from chat import config
        app = self.app
        app.open_tab("twitch", "eslcs")
        self.pump()
        app.open_settings()
        app.update()
        s = app.settings_state
        s.update(font_size=16, timestamps=False, max_messages=1000, theme="dark")
        s["_highlights_var"].set("gg, wp ,  , clutch")
        with mock.patch.object(app, "toast"):
            app.save_settings()
        self.pump()
        self.assertIsNone(app.panel_kind)
        cfg = config.load()
        self.assertEqual((cfg["font_size"], cfg["timestamps"], cfg["max_messages"]), (16, False, 1000))
        self.assertEqual(cfg["highlights"], ["gg", "wp", "clutch"])
        self.assertEqual(app.mode, "dark")
        self.assertEqual(app.current.history.maxlen, 1000)


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestAccounts(TestGuiSmoke):
    """Connexion Twitch par code d'appareil, avec l'application intégrée ou son propre Client ID ; déconnexion.

    Twitch login with a device code, with the built-in application or one's own Client ID; logout."""

    def test_open_chat_show_messages_settings_theme(self):  # déjà couvert par TestGuiSmoke / covered above
        pass

    def _login(self, client_id):
        from chat import auth, config
        app, started = self.app, []
        device = {"device_code": "d", "user_code": "ABCD-EFGH", "verification_uri": "https://www.twitch.tv/activate",
                  "interval": 1}
        token = {"access_token": "tok", "refresh_token": "ref", "login": "chris", "user_id": "1"}
        with mock.patch.object(auth, "TWITCH_CLIENT_ID", "pub123"), \
                mock.patch.object(auth, "twitch_device_start", lambda cid: started.append(cid) or device), \
                mock.patch.object(auth, "twitch_device_poll", lambda cid, dev, cancel: dict(token)), \
                mock.patch.object(app, "open_url"), mock.patch.object(app, "toast"), \
                mock.patch.object(app, "restart_connection") as restart:
            app.login("twitch", client_id)
            for _ in range(20):
                self.pump()
                if app.cfg["accounts"]["twitch"].get("access_token"):
                    break
            restart.assert_called_with("twitch")
        return started, config.load()["accounts"]["twitch"]

    def test_builtin_application(self):
        started, acc = self._login("")
        self.assertEqual(started, ["pub123"])            # application de Streamlink Chat / built-in application
        self.assertEqual((acc["client_id"], acc["access_token"], acc["login"]), ("pub123", "tok", "chris"))
        self.assertNotEqual(self.app.panel_kind, "login")
        with mock.patch.object(self.app, "restart_connection"):
            self.app.logout("twitch")
        self.assertEqual(self.app.cfg["accounts"]["twitch"], {"client_id": "pub123"})

    def test_own_client_id(self):
        started, acc = self._login("mine456")
        self.assertEqual(started, ["mine456"])
        self.assertEqual(acc["client_id"], "mine456")

    def test_no_client_id_without_builtin(self):
        from chat import auth
        app = self.app
        with mock.patch.object(auth, "TWITCH_CLIENT_ID", ""), mock.patch.object(app, "toast") as toast, \
                mock.patch.object(auth, "twitch_device_start") as start:
            app.login("twitch", "")
        start.assert_not_called()
        toast.assert_called_once_with(app.t("chat_need_client_id"), "warn")
        with mock.patch.object(auth, "TWITCH_CLIENT_ID", "pub123"):
            app.open_settings(section="accounts")      # réglages avec le Client ID facultatif / optional Client ID
            app.update()
        self.assertEqual(app.panel_kind, "settings")

