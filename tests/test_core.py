"""Tests des outils sans interface (chat/core.py), des traductions et de la version."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chat import __version__, config, core  # noqa: E402


class TestTranslations(unittest.TestCase):
    def setUp(self):
        self.files = sorted((ROOT / "lang").glob("*.json"))
        self.data = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in self.files}

    def test_five_languages_same_keys(self):
        self.assertEqual(set(self.data), {"fr", "en", "es", "de", "it"})
        ref = set(self.data["en"])
        for lang, strings in self.data.items():
            self.assertEqual(set(strings), ref, f"{lang}.json : {sorted(set(strings) ^ ref)}")

    def test_same_placeholders(self):
        for key, ref in self.data["en"].items():
            for lang, strings in self.data.items():
                self.assertEqual(sorted(re.findall(r"{\w+}", strings[key])), sorted(re.findall(r"{\w+}", ref)),
                                 f"{lang}.json : {key}")

    def test_no_unused_or_missing_translation(self):
        code = "".join(f.read_text(encoding="utf-8") for f in (ROOT / "chat").glob("*.py"))
        used = set(re.findall(r"""\bt\(\s*["']([a-z][a-z_]+)["']""", code))
        keys = {k for k in self.data["en"] if not k.startswith("_")}
        self.assertEqual(sorted(used - keys), [])
        self.assertEqual(sorted(k for k in keys if f'"{k}"' not in code and f"'{k}'" not in code), [])

    def test_i18n_fallback(self):
        t = core.I18n("xx")
        self.assertEqual(t("chat_title"), "Chats")
        self.assertEqual(t("unknown_key"), "unknown_key")
        self.assertIn("eslcs", core.I18n("fr")("chat_input_placeholder", channel="eslcs"))


class TestFiles(unittest.TestCase):
    def test_save_load_and_backup(self):
        d = Path(tempfile.mkdtemp())
        f = d / "x.json"
        self.assertTrue(core.save_json(f, {"a": 1}))
        self.assertTrue(core.save_json(f, {"a": 2}))
        self.assertEqual(core.load_json(f, {}), {"a": 2})
        f.write_text("{tronqué", encoding="utf-8")
        self.assertEqual(core.load_json(f, {}), {"a": 1})  # repli sur la sauvegarde .bak
        self.assertEqual(core.load_json(d / "absent.json", {"d": 0}), {"d": 0})

    def test_config_defaults(self):
        d = Path(tempfile.mkdtemp())
        (d / "chat.json").write_text(json.dumps({"theme": "pink", "quality": "8k"}), encoding="utf-8")
        with mock.patch.object(config, "CONFIG_FILE", d / "chat.json"):
            cfg = config.load()
        self.assertEqual((cfg["theme"], cfg["quality"]), ("auto", "best"))


class TestStreamlink(unittest.TestCase):
    def test_watch_command(self):
        self.assertEqual(core.watch_command("sl", "twitch", "https://www.twitch.tv/x", "720p"),
                         ["sl", "--twitch-disable-ads", "https://www.twitch.tv/x", "720p"])
        self.assertEqual(core.watch_command("sl", "kick", "https://kick.com/x", ""), ["sl", "https://kick.com/x", "best"])

    def test_find_streamlink(self):
        self.assertIsNone(core.find_streamlink("/nulle/part/streamlink"))
        with mock.patch.object(core.shutil, "which", return_value="/usr/bin/streamlink"):
            self.assertEqual(core.find_streamlink(), "/usr/bin/streamlink")


class TestVersion(unittest.TestCase):
    def test_version_everywhere(self):
        info = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
        self.assertIn(f"'FileVersion', '{__version__}'", info)
        self.assertIn(f"## [{__version__}]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
