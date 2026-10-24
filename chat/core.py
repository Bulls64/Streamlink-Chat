"""Chemins, fichiers JSON, journal, langues et recherche de Streamlink (sans interface).

Paths, JSON files, log, languages and Streamlink lookup (without interface)."""
import json
import locale
import logging
import os
import shutil
import sys
from pathlib import Path

# ---------------------
# Chemins
# Paths
# ---------------------
FROZEN = bool(getattr(sys, "frozen", False))
BASE_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
RES_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))


def _is_writable(folder):
    probe = Path(folder) / f".write_test_{os.getpid()}"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def _user_data_dir():
    if os.name == "nt":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(root) / "Streamlink Chat"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "streamlink-chat"


# Version portable par défaut : les données restent à côté de l'application. Dossier en lecture seule (ou AppImage,
# extraite dans un dossier temporaire) : %APPDATA%\Streamlink Chat ou ~/.config/streamlink-chat.
# Portable version by default: the data stays next to the application. Read-only folder (or AppImage,
# extracted to a temporary folder): %APPDATA%\Streamlink Chat or ~/.config/streamlink-chat.
APPIMAGE = bool(os.environ.get("APPIMAGE")) and not FROZEN and os.name != "nt"
PORTABLE = not APPIMAGE and _is_writable(BASE_DIR)
DATA_ROOT = BASE_DIR if PORTABLE else _user_data_dir()
LANG_DIR = BASE_DIR / "lang" if (BASE_DIR / "lang").is_dir() else RES_DIR / "lang"
LOG_FILE = DATA_ROOT / "chat.log"

log = logging.getLogger("streamlink_launcher")  # même nom que le lanceur : un seul journal si les deux cohabitent
                                                # same name as the launcher: a single log if both live side by side
log.addHandler(logging.NullHandler())
_log_ready = False


def setup_logging():
    """Active l'écriture de chat.log (2 × 512 Ko maximum).

    Enables writing chat.log (2 × 512 KB maximum)."""
    global _log_ready
    if _log_ready:
        return
    _log_ready = True
    try:
        from logging.handlers import RotatingFileHandler
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=1, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    except OSError:
        pass


# ---------------------
# JSON
# ---------------------
def load_json(path, default):
    """Lit un fichier JSON ; absent ou illisible : default (la sauvegarde .bak est essayée en second).

    Reads a JSON file; missing or unreadable: default (the .bak backup is tried second)."""
    path = Path(path)
    for candidate in (path, path.with_name(path.name + ".bak")):
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as e:
            log.warning("Fichier illisible %s : %s", candidate, e)
    return default


def _private(path):
    """Hors Windows, réserve le fichier à son propriétaire (0600) : il peut contenir des jetons.

    Outside Windows, restricts the file to its owner (0600): it may hold tokens."""
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError as e:
            log.warning("Droits impossibles à restreindre sur %s : %s", path, e)


def save_json(path, data):
    """Écriture atomique (fichier temporaire puis remplacement) ; la version précédente est gardée en .bak.
    Hors Windows, le fichier et sa copie .bak sont lisibles par leur seul propriétaire.

    Atomic write (temporary file, then replacement); the previous version is kept as .bak.
    Outside Windows, the file and its .bak copy are readable by their owner only."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            try:
                bak = path.with_name(path.name + ".bak")
                shutil.copyfile(path, bak)
                _private(bak)
            except OSError as e:
                log.warning("Sauvegarde .bak impossible pour %s : %s", path.name, e)
        os.replace(tmp, path)
        _private(path)
        return True
    except (OSError, TypeError, ValueError) as e:
        log.error("Enregistrement impossible de %s : %s", path, e)
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


# ---------------------
# Langues
# Languages
# ---------------------
def detect_system_language():
    try:
        name = locale.getlocale()[0] or ""
        if os.name != "nt":  # Linux : la langue d'affichage, même si la locale n'est pas générée
                             # Linux: the display language, even if the locale is not generated
            name = next((os.environ[v] for v in ("LC_ALL", "LC_MESSAGES", "LANG")
                         if os.environ.get(v) and os.environ[v] not in ("C", "POSIX")), name)
        else:
            import ctypes
            name = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), name)
        code = name.lower()[:2]
        return code if code in ("fr", "es", "de", "it") else "en"
    except Exception:
        return "en"


def available_languages():
    """[(code, nom affiché)] d'après les fichiers de lang/.

    [(code, displayed name)] from the files in lang/."""
    langs = [(f.stem, load_json(f, {}).get("_language_name", f.stem)) for f in sorted(LANG_DIR.glob("*.json"))]
    return langs or [("en", "English")]


class I18n:
    def __init__(self, lang):
        self.lang = lang
        self.strings = load_json(LANG_DIR / f"{lang}.json", {})
        self.fallback = load_json(LANG_DIR / "en.json", {}) if lang != "en" else {}

    def get(self, key, default=None):
        return self.strings.get(key, self.fallback.get(key, default))

    def __call__(self, key, /, **kwargs):
        text = self.strings.get(key) or self.fallback.get(key) or key
        try:
            return text.format(**kwargs)
        except Exception:
            return text


# ---------------------
# Streamlink (bouton « Regarder »)
# Streamlink ("Watch" button)
# ---------------------
STREAMLINK_CANDIDATES = [
    "streamlink",
    r"C:\Program Files\Streamlink\bin\streamlink.exe",
    r"C:\Program Files (x86)\Streamlink\bin\streamlink.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Streamlink\bin\streamlink.exe"),
]
PLATFORM_ARGS = {"twitch": ["--twitch-disable-ads"]}
QUALITIES = ["best", "1080p60", "1080p", "720p60", "720p", "480p", "audio_only"]


def find_streamlink(configured=""):
    if configured:
        return configured if os.path.isfile(configured) or shutil.which(configured) else None
    for c in STREAMLINK_CANDIDATES:
        found = shutil.which(c) or (c if os.path.isfile(c) else None)
        if found:
            return found
    return None


def watch_command(streamlink, platform, url, quality):
    return [streamlink, *PLATFORM_ARGS.get(platform, []), url, quality or "best"]
