"""Tests des outils sans interface (chat/core.py), des traductions et de la version.

Tests of the tools without interface (chat/core.py), the translations and the version."""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chat import __version__, config, core, updater  # noqa: E402


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
                                                           # fallback to the .bak backup
        self.assertEqual(core.load_json(d / "absent.json", {"d": 0}), {"d": 0})

    @unittest.skipIf(os.name == "nt", "droits POSIX / POSIX permissions only")
    def test_saved_files_are_private(self):
        # Le fichier (jetons) et sa copie .bak ne sont lisibles que par leur propriétaire, même s'il existait déjà ouvert à tous.
        # The file (tokens) and its .bak copy are readable by their owner only, even if it already existed world-readable.
        d = Path(tempfile.mkdtemp())
        f = d / "chat.json"
        f.write_text("{}", encoding="utf-8")
        os.chmod(f, 0o644)
        self.assertTrue(core.save_json(f, {"a": 1}))
        self.assertTrue(core.save_json(f, {"a": 2}))
        for name in ("chat.json", "chat.json.bak"):
            self.assertEqual((d / name).stat().st_mode & 0o777, 0o600, name)

    def test_config_defaults(self):
        d = Path(tempfile.mkdtemp())
        (d / "chat.json").write_text(json.dumps({"theme": "pink", "quality": "8k"}), encoding="utf-8")
        with mock.patch.object(config, "CONFIG_FILE", d / "chat.json"):
            cfg = config.load()
        self.assertEqual((cfg["theme"], cfg["quality"]), ("auto", "best"))
        self.assertTrue(cfg["platform_colors"])

    def test_platform_colors(self):
        self.assertEqual(config.PLATFORMS["twitch"][1], "#9146FF")
        self.assertEqual(config.PLATFORMS["kick"][1], "#53FC18")
        self.assertEqual(config.PLATFORMS["steamtv"][1], "#2A475E")


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


class TestAppUpdate(unittest.TestCase):
    """Mise à jour depuis les releases GitHub (chat/updater.py).

    Update from the GitHub releases (chat/updater.py)."""
    SIZE = 1_500_000

    def api(self, **over):
        v = "9.9.9"
        data = {"tag_name": f"v{v}", "draft": False, "prerelease": False, "assets": [{
            "name": f"StreamlinkChat-{v}.exe", "size": self.SIZE, "digest": "sha256:" + "a" * 64,
            "browser_download_url": f"{updater.REPO_URL}/releases/download/v{v}/StreamlinkChat-{v}.exe"}]}
        data.update(over)
        return data

    def test_parse_release_ok(self):
        r = updater.parse_release(self.api())
        self.assertEqual(r["version"], "9.9.9")
        self.assertEqual(r["asset"]["sha256"], "a" * 64)
        self.assertTrue(r["page"].endswith("/releases/tag/v9.9.9"))

    def test_parse_release_rejects(self):
        self.assertIsNone(updater.parse_release(None))
        self.assertIsNone(updater.parse_release(self.api(draft=True)))
        self.assertIsNone(updater.parse_release(self.api(prerelease=True)))
        self.assertIsNone(updater.parse_release(self.api(tag_name="v9.9")))
        self.assertIsNone(updater.parse_release(self.api(tag_name="release-9")))

    def test_parse_release_asset_checks(self):
        def asset(**kw):
            d = self.api()
            d["assets"][0].update(kw)
            return updater.parse_release(d)["asset"]
        self.assertIsNone(asset(browser_download_url="https://evil.example/StreamlinkChat-9.9.9.exe"))
        self.assertIsNone(asset(digest=None))
        self.assertIsNone(asset(digest="sha1:" + "a" * 40))
        self.assertIsNone(asset(size=10))
        self.assertIsNone(asset(size=updater.MAX_BYTES + 1))
        self.assertIsNone(asset(size=True))
        self.assertIsNone(asset(name="Other.exe"))
        self.assertIsNotNone(asset())

    def test_check_app_update(self):
        with mock.patch.object(updater, "_http_get_json", return_value=self.api()):
            r = updater.check_update("1.0.0")
            self.assertTrue(r["update"])
            self.assertEqual(r["latest"], "9.9.9")
            self.assertFalse(updater.check_update("9.9.9")["update"])
            self.assertFalse(updater.check_update("10.0.0")["update"])

    def test_check_app_update_errors(self):
        import urllib.error
        e404 = urllib.error.HTTPError("u", 404, "nf", {}, None)
        with mock.patch.object(updater, "_http_get_json", side_effect=e404):
            self.assertEqual(updater.check_update("1.0.0")["error"], "release")
        with mock.patch.object(updater, "_http_get_json", side_effect=OSError("down")):
            r = updater.check_update("1.0.0")
            self.assertEqual((r["error"], r["update"]), ("network", None))
        with mock.patch.object(updater, "_http_get_json", return_value={"tag_name": "x"}):
            self.assertEqual(updater.check_update("1.0.0")["error"], "release")

    def test_safe_redirects(self):
        import urllib.error
        h = [x for x in updater._safe_opener().handlers if x.__class__.__name__ == "Redirect"][0]
        import urllib.request
        req = urllib.request.Request("https://github.com/x")
        for ok in ("https://objects.githubusercontent.com/a", "https://github.com/b", "https://api.github.com/c"):
            self.assertIsNotNone(h.redirect_request(req, None, 302, "", {}, ok))
        for bad in ("http://github.com/a", "https://evil.example/a", "https://github.com.evil.example/a",
                    "https://notgithub.com/a", "file:///etc/passwd"):
            with self.assertRaises(urllib.error.URLError):
                h.redirect_request(req, None, 302, "", {}, bad)

    # -- téléchargement
    # -- download
    def release(self, payload, size=None):
        import hashlib
        return {"asset": {"name": "StreamlinkChat-9.9.9.exe", "url": "https://x/y",
                          "size": len(payload) if size is None else size,
                          "sha256": hashlib.sha256(payload).hexdigest()}}

    class Resp:
        def __init__(self, data, fail_after=None):
            self.data, self.pos, self.fail_after = data, 0, fail_after

        def read(self, n):
            if self.fail_after is not None and self.pos >= self.fail_after:
                raise OSError("reset")
            chunk = self.data[self.pos:self.pos + n]
            self.pos += len(chunk)
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def dl(self, payload, release=None, **kw):
        d = Path(tempfile.mkdtemp())
        rel = release or self.release(payload)
        opener = kw.pop("opener", lambda url: self.Resp(payload))
        try:
            return d, updater.download_update(rel, d, opener=opener, **kw)
        except updater.UpdateError as e:
            return d, e

    def test_download_ok(self):
        payload = b"MZ" + b"\0" * 300_000
        seen = []
        d, r = self.dl(payload, progress=lambda a, b: seen.append((a, b)))
        self.assertEqual(r.read_bytes(), payload)
        self.assertEqual(seen[-1], (len(payload), len(payload)))

    def test_download_failures_leave_nothing(self):
        good = b"MZ" + b"\0" * 1000
        cases = {
            "app_err_hash": dict(release=dict(self.release(good), asset=dict(self.release(good)["asset"], sha256="0" * 64))),
            "app_err_download": dict(release=self.release(good, size=len(good) + 5)),
        }
        for key, kw in cases.items():
            d, e = self.dl(good, **kw)
            self.assertIsInstance(e, updater.UpdateError)
            self.assertEqual(e.key, key)
            self.assertEqual(list(d.iterdir()), [])
        d, e = self.dl(good, release=self.release(good, size=10))             # plus gros que annoncé
                                                                              # bigger than announced
        self.assertEqual(e.key, "app_err_hash")
        notpe = b"ZZ" + b"\0" * 1000
        d, e = self.dl(notpe)
        self.assertEqual(e.key, "app_err_hash")
        self.assertEqual(list(d.iterdir()), [])
        d, e = self.dl(good, opener=lambda url: self.Resp(good, fail_after=100))
        self.assertEqual(e.key, "app_err_download")
        self.assertEqual(list(d.iterdir()), [])

    def test_download_network_and_cancel(self):
        def boom(url):
            raise OSError("down")
        d, e = self.dl(b"MZ", opener=boom)
        self.assertEqual(e.key, "app_err_network")
        import threading
        ev = threading.Event()
        ev.set()
        d, e = self.dl(b"MZ" + b"\0" * 100, cancel=ev)
        self.assertEqual(e.key, "app_err_cancelled")
        self.assertEqual(list(d.iterdir()), [])
        with self.assertRaises(updater.UpdateError):
            updater.download_update({"asset": None}, tempfile.mkdtemp())

    # -- signature
    def test_parse_authenticode(self):
        self.assertEqual(updater._parse_authenticode("Valid|CN=SignPath Foundation, O=SignPath\n"),
                         ("Valid", "CN=SignPath Foundation, O=SignPath"))
        self.assertEqual(updater._parse_authenticode("NotSigned|"), ("NotSigned", None))
        self.assertEqual(updater._parse_authenticode(""), ("error", None))

    def test_check_signature(self):
        def run(cur, new):
            return updater.check_signature("c", "n", probe=lambda f: cur if f == "c" else new)
        v = ("Valid", "CN=Me, O=X")
        self.assertIsNone(run(v, ("Valid", "CN=Me, O=Y")))
        self.assertEqual(run(v, ("Valid", "CN=Other")), "app_err_signature")
        self.assertEqual(run(v, ("NotSigned", None)), "app_err_signature")      # pas de retour en arrière
                                                                                # no going back
        self.assertEqual(run(v, ("HashMismatch", "CN=Me")), "app_err_signature")
        self.assertEqual(run(v, ("error", None)), "app_err_signature")
        unsigned = ("NotSigned", None)
        self.assertIsNone(run(unsigned, ("NotSigned", None)))
        self.assertIsNone(run(unsigned, v))
        self.assertIsNone(run(unsigned, ("error", None)))
        self.assertEqual(run(unsigned, ("HashMismatch", "CN=Me")), "app_err_signature")

    # -- installation
    def test_install_update(self):
        d = Path(tempfile.mkdtemp())
        exe, new = d / "app.exe", d / "app.exe.download"
        exe.write_bytes(b"old")
        new.write_bytes(b"new")
        (d / "app.exe.old").write_bytes(b"stale")
        old = updater.install_update(new, exe)
        self.assertEqual(exe.read_bytes(), b"new")
        self.assertEqual(old.read_bytes(), b"old")
        self.assertFalse(new.exists())

    def test_target_exe(self):
        t = updater.target_exe
        self.assertEqual(t("C:/x/StreamlinkChat-1.4.1.exe", "1.4.1", "1.4.2"), Path("C:/x/StreamlinkChat-1.4.2.exe"))
        self.assertEqual(t("C:/x/slink.exe", "1.4.1", "1.4.2"), Path("C:/x/slink.exe"))
        self.assertEqual(t("C:/x/App-11.4.1.exe", "1.4.1", "1.4.2"), Path("C:/x/App-11.4.1.exe"))
        d = Path(tempfile.mkdtemp())
        (d / "StreamlinkChat-1.4.2.exe").write_bytes(b"x")  # déjà pris : on garde le nom actuel
                                                            # already taken: the current name is kept
        cur = d / "StreamlinkChat-1.4.1.exe"
        self.assertEqual(t(cur, "1.4.1", "1.4.2"), cur)

    def test_install_update_renamed(self):
        d = Path(tempfile.mkdtemp())
        exe, new, final = d / "app-1.exe", d / "app-1.exe.download", d / "app-2.exe"
        exe.write_bytes(b"old")
        new.write_bytes(b"new")
        old = updater.install_update(new, exe, final)
        self.assertEqual(final.read_bytes(), b"new")
        self.assertFalse(exe.exists())
        self.assertEqual(old, d / "app-1.exe.old")
        self.assertEqual(old.read_bytes(), b"old")

    def test_install_update_rollback(self):
        d = Path(tempfile.mkdtemp())
        exe = d / "app.exe"
        exe.write_bytes(b"old")
        with self.assertRaises(updater.UpdateError) as cm:
            updater.install_update(d / "missing", exe)
        self.assertEqual(cm.exception.key, "app_err_install")
        self.assertEqual(exe.read_bytes(), b"old")
        self.assertFalse((d / "app.exe.old").exists())

    def test_cleanup(self):
        d = Path(tempfile.mkdtemp())
        exe = d / "StreamlinkChat-1.exe"
        exe.write_bytes(b"x")
        (d / (exe.name + ".old")).write_bytes(b"o")
        (d / "StreamlinkChat-2.exe.download").write_bytes(b"p")
        (d / "keep.txt").write_bytes(b"k")
        updater.cleanup_leftovers(exe, tries=1)
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["StreamlinkChat-1.exe", "keep.txt"])

    def test_relaunch(self):
        with mock.patch.object(updater.subprocess, "Popen") as popen:
            self.assertTrue(updater.relaunch("/x/app.exe", "1.0.0"))
        args, kw = popen.call_args
        self.assertEqual(args[0][0], "/x/app.exe")
        self.assertEqual(args[0][1:3], ["--wait-pid", str(os.getpid())])
        self.assertEqual(args[0][3:], ["--updated-from", "1.0.0"])
        self.assertEqual(kw["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        with mock.patch.object(updater.subprocess, "Popen", side_effect=OSError):
            self.assertFalse(updater.relaunch("/x/app.exe"))

    def test_should_auto_update(self):
        res = {"update": True, "release": {"asset": {"name": "a"}}}
        cfg = {"auto_update": True, "update_check": True}
        ok = lambda c=cfg, r=res, u=None, can=True: updater.should_auto_update(c, r, u, can)
        self.assertTrue(ok())
        self.assertFalse(ok(c={**cfg, "auto_update": False}))
        self.assertFalse(ok(c={**cfg, "update_check": False}))
        self.assertFalse(ok(r={**res, "update": False}))
        self.assertFalse(ok(r={"update": True, "release": {"asset": None}}))
        self.assertFalse(ok(r=None))
        self.assertFalse(ok(can=False))
        self.assertFalse(ok(u="1.3.0"))               # vient d'être mis à jour : pas de boucle
                                                      # just updated: no loop
        self.assertFalse(config.DEFAULT_CONFIG["auto_update"])   # désactivé par défaut
                                                                 # disabled by default
        self.assertTrue(config.DEFAULT_CONFIG["update_check"])

    def test_arg_value(self):
        self.assertEqual(updater.arg_value("--a", ["p", "--a", "1"]), "1")
        self.assertIsNone(updater.arg_value("--a", ["p", "--a"]))
        self.assertIsNone(updater.arg_value("--b", ["p", "--a", "1"]))

    def test_self_update_needs_frozen_exe(self):
        self.assertFalse(updater.can_self_update())          # lancé depuis les sources
                                                             # started from the sources

    def test_wait_for_pid(self):
        if os.name != "nt":
            self.assertTrue(updater.wait_for_pid(99999999, timeout=0.5))   # processus inexistant
                                                                           # process that does not exist
            self.assertFalse(updater.wait_for_pid(os.getpid(), timeout=0.3))  # toujours en vie
                                                                              # still alive

    def test_restart_arguments_are_not_channels(self):
        self.assertEqual(config.targets_from_argv(["--wait-pid", "12345", "--updated-from", "0.1.0", "kick.com/xqc"]),
                         [("kick", "xqc")])

    def test_size_format_keys(self):
        for lang, sep in (("en", "."), ("fr", ",")):
            t = core.I18n(lang)
            self.assertIn(f"1{sep}5", t("size_mb", size=f"{1.5:.1f}".replace(".", t("decimal_sep"))))


if __name__ == "__main__":
    unittest.main()
