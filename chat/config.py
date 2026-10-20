"""Réglages de Streamlink Chat (chat.json) et lecture des adresses de chaînes.

Streamlink Chat settings (chat.json) and parsing of channel addresses."""
import copy
import re
import urllib.parse

from . import core, vault

CONFIG_FILE = core.DATA_ROOT / "chat.json"
CACHE_DIR = core.DATA_ROOT / "cache" / "emotes"

PLATFORMS = {  # identifiant -> (nom, couleur, couleur du texte posé dessus)
               # id -> (name, color, color of the text on top of it)
    "twitch": ("Twitch", "#9146FF", "#FFFFFF"),
    "kick": ("Kick", "#53FC18", "#000000"),
    "steamtv": ("Steam TV", "#2A475E", "#C7D5E0"),   # bleu nuit de Steam
                                                     # Steam's navy blue
}
NEUTRAL = ("#6B7280", "#FFFFFF")

DEFAULT_CONFIG = {
    "language": "",            # vide : celle du système
                               # empty: the system's one
    "theme": "auto",           # auto (suit Windows), light, dark
                               # auto (follows Windows), light, dark
    "quality": "best",         # qualité demandée à Streamlink par le bouton ▶
                               # quality requested from Streamlink by the ▶ button
    "streamlink_path": "",     # vide : détecté automatiquement
                               # empty: detected automatically
    "update_check": True,      # cherche une nouvelle version au démarrage
                               # looks for a new version at start-up
    "auto_update": False,      # et l'installe sans demander (exécutable Windows seulement)
                               # and installs it without asking (Windows executable only)
    "tabs": [],                # [{"platform": "twitch", "channel": "eslcs"}]
    "selected": 0,
    "geometry": "",
    "default_platform": "twitch",
    "font_size": 14,
    "timestamps": True,
    "badges": True,
    "platform_colors": True,   # carte et onglets teintés de la couleur de la plateforme
                               # card and tabs tinted with the platform's color
    "animated": True,
    "providers": ["bttv", "ffz", "7tv"],
    "highlights": [],          # mots qui mettent un message en évidence (en plus de son propre pseudo)
                               # words that highlight a message (in addition to one's own username)
    "max_messages": 1000,
    "accounts": {"twitch": {}, "kick": {}},
}

FONT_SIZES = [12, 13, 14, 15, 16, 18]
MAX_MESSAGES = [500, 1000, 2000, 5000]


def load():
    data = core.load_json(CONFIG_FILE, {})
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if isinstance(data, dict):
        for k, v in data.items():
            if k in cfg and isinstance(v, type(cfg[k])):
                cfg[k] = v
    cfg["tabs"] = [t for t in cfg["tabs"] if isinstance(t, dict) and t.get("platform") in PLATFORMS
                   and isinstance(t.get("channel"), str) and t["channel"]]
    if cfg["theme"] not in ("auto", "light", "dark"):
        cfg["theme"] = "auto"
    if cfg["quality"] not in core.QUALITIES:
        cfg["quality"] = "best"
    if cfg["font_size"] not in FONT_SIZES:
        cfg["font_size"] = 14
    if cfg["max_messages"] not in MAX_MESSAGES:
        cfg["max_messages"] = 1000
    if cfg["default_platform"] not in PLATFORMS:
        cfg["default_platform"] = "twitch"
    for p in ("twitch", "kick"):
        if not isinstance(cfg["accounts"].get(p), dict):
            cfg["accounts"][p] = {}
    cfg["accounts"] = vault.unseal(cfg["accounts"])
    return cfg


def save(cfg):
    core.save_json(CONFIG_FILE, dict(cfg, accounts=vault.seal(cfg["accounts"])))


# ---------------------
# Adresses et noms de chaînes
# Channel addresses and names
# ---------------------
NAME_RE = {
    "twitch": re.compile(r"^[A-Za-z0-9_]{1,25}$"),
    "kick": re.compile(r"^[A-Za-z0-9_-]{1,40}$"),
    "steamtv": re.compile(r"^(?:[A-Za-z0-9_]{1,40}|7656119\d{10})$"),
}
RESERVED = {"twitch": {"directory", "videos", "settings", "subscriptions", "inventory", "wallet", "p", "search",
                       "downloads", "jobs", "turbo", "friends", "messages", "drops"},
            "kick": {"categories", "following", "browse", "search", "video", "dashboard"}}


def parse_target(text, default_platform="twitch"):
    """Nom de chaîne ou lien -> (plateforme, chaîne), ou None si ce n'est pas reconnu.

    Channel name or link -> (platform, channel), or None if it is not recognized."""
    text = (text or "").strip()
    if not text:
        return None
    m = re.match(r"^(twitch|kick|steam(?:tv)?)\s*[:/]\s*(\S+)$", text, re.I)
    if m:
        platform = "steamtv" if m.group(1).lower().startswith("steam") else m.group(1).lower()
        return _check(platform, m.group(2))
    if "/" in text or "." in text:
        url = text if "://" in text else "https://" + text
        u = urllib.parse.urlsplit(url)
        host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
        parts = [p for p in u.path.split("/") if p]
        if host.endswith("twitch.tv") and parts:
            if parts[0] == "popout" and len(parts) > 1:  # twitch.tv/popout/<chaîne>/chat
                parts = parts[1:]
            return _check("twitch", parts[0])
        if host.endswith("kick.com") and parts:
            if parts[0] == "popout" and len(parts) > 1:
                parts = parts[1:]
            return _check("kick", parts[0])
        if host == "steam.tv" and parts:
            return _check("steamtv", parts[0])
        if host == "steamcommunity.com" and len(parts) >= 3 and parts[:2] == ["broadcast", "watch"]:
            return _check("steamtv", parts[2])
        return None
    if text.startswith("#") or text.startswith("@"):
        text = text[1:]
    return _check(default_platform, text)


def _check(platform, channel):
    channel = channel.strip().split("?")[0].split("#")[0]
    if platform not in NAME_RE or not NAME_RE[platform].match(channel):
        return None
    if channel.lower() in RESERVED.get(platform, ()):
        return None
    if platform in ("twitch", "kick"):
        channel = channel.lower()
    return platform, channel


def channel_url(platform, channel):
    return {"twitch": "https://www.twitch.tv/{}", "kick": "https://kick.com/{}",
            "steamtv": "https://steamcommunity.com/broadcast/watch/{}" if channel.isdigit() else
            "https://steam.tv/{}"}[platform].format(channel)


def targets_from_argv(argv):
    """--open twitch:eslcs --open kick:xqc, ou des liens en arguments.

    --open twitch:eslcs --open kick:xqc, or links as arguments."""
    out = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--open" and args:
            a = args.pop(0)
        elif a in ("--wait-pid", "--updated-from"):
            if args:
                args.pop(0)  # valeur de l'option, pas une chaîne
                             # value of the option, not a channel
            continue
        elif a.startswith("--"):
            continue
        target = parse_target(a)
        if target:
            out.append(target)
    return out
