"""Vérification en conditions réelles : Streamlink Chat lit-il encore Twitch, Kick et Steam TV ?

Les tests du dépôt imitent les plateformes avec de faux serveurs locaux ; ce script, lui, se connecte aux vrais
services, en lecture seule et sans compte. Il sert à la vérification quotidienne de la CI (live-check.yml), pour
savoir qu'un protocole non documenté a changé avant que les utilisateurs ne le voient.

Pour chaque plateforme, il essaie quelques chaînes connues l'une après l'autre :
- Twitch et Kick réussissent si une chaîne se connecte et reçoit au moins un message ;
- Steam TV réussit si la page d'une chaîne donne son steamid et que l'API répond (diffusion ou hors ligne),
  car ses chaînes sont souvent hors ligne.
Code de sortie 0 si tout va bien, 1 sinon ; le résumé est écrit en Markdown (pour le ticket ouvert par la CI).

Real-world check: does Streamlink Chat still read Twitch, Kick and Steam TV?

The repository's tests imitate the platforms with local fake servers; this script connects to the real services,
read-only and without an account. It is used by the daily CI check (live-check.yml), to know that an undocumented
protocol has changed before users see it.

For each platform, it tries a few well-known channels one after the other:
- Twitch and Kick pass if a channel connects and receives at least one message;
- Steam TV passes if a channel's page gives its steamid and the API answers (broadcasting or offline),
  because its channels are often offline.
Exit code 0 if all is well, 1 otherwise; the summary is written in Markdown (for the issue opened by the CI).

Usage: python packaging/live_check.py [--platform twitch|kick|steamtv] [--summary FILE]
"""
import argparse
import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chat import kick, steam, twitch
from chat.common import HttpError, http

CHANNELS = {
    "twitch": ["kaicenat", "ibai", "xqc", "eslcs", "shroud"],
    "kick": ["xqc", "adinross", "trainwreckstv", "amouranth", "cuffem"],
    "steamtv": ["esl", "dota2", "csgo", "pgl", "steamtv"],
}
CONNECT_TIMEOUT = 45  # s
MESSAGE_TIMEOUT = 90  # s, après la connexion / after connecting


def _watch(events, channel, need_message, deadline_connect):
    """Lit les événements d'une connexion : (connectée, messages reçus, dernier état d'erreur).

    Reads a connection's events: (connected, messages received, last error state)."""
    connected, messages, error = False, 0, ""
    deadline = deadline_connect
    while time.time() < deadline:
        try:
            ev = events.get(timeout=1)
        except queue.Empty:
            continue
        if ev[0] == "message" and ev[1].channel.lower() == channel:
            messages += 1
            if connected and (messages or not need_message):
                break
        elif ev[0] == "status" and ev[2].lower() == channel:
            state, detail = ev[3], ev[4]
            if state == "connected" and not connected:
                connected = True
                if not need_message or messages:
                    break
                deadline = time.time() + MESSAGE_TIMEOUT
            elif state == "error":
                error = detail or "error"
                if not need_message and detail in ("offline", "not_found", "blocked"):
                    break
    return connected, messages, error


def check_twitch(channel):
    events = queue.Queue()
    conn = twitch.TwitchConnection(events.put).start()
    try:
        conn.join(channel)
        ok, n, err = _watch(events, channel, True, time.time() + CONNECT_TIMEOUT)
    finally:
        conn.stop()
    return ok and n > 0, f"connecté={ok}, messages={n}" + (f", erreur={err}" if err else "")


def check_kick(channel):
    events = queue.Queue()
    conn = kick.KickChannel(events.put, channel).start()
    try:
        ok, n, err = _watch(events, channel, True, time.time() + CONNECT_TIMEOUT)
    finally:
        conn.stop()
    return ok and n > 0, f"connecté={ok}, messages={n}" + (f", erreur={err}" if err else "")


def check_steamtv(channel):
    events = queue.Queue()
    conn = steam.SteamChannel(events.put, channel).start()
    try:
        ok, n, err = _watch(events, channel, False, time.time() + CONNECT_TIMEOUT)
        steamid = conn.steamid
    finally:
        conn.stop()
    # Hors ligne est une réponse normale de l'API, à condition que la page ait donné le steamid
    # Offline is a normal API answer, provided the page gave the steamid
    passed = bool(steamid) and (ok or err == "offline")
    return passed, f"steamid={steamid or '-'}, connecté={ok}, messages={n}" + (f", erreur={err}" if err else "")


def _step(label, func):
    """Une étape du diagnostic : « libellé : OK (aperçu) » ou « libellé : HTTP 403 … ».

    One diagnostic step: "label: OK (preview)" or "label: HTTP 403 …"."""
    try:
        result = func()
    except HttpError as e:
        return None, f"{label} : {e}"[:240]
    except Exception as e:  # réseau, JSON invalide… / network, invalid JSON…
        return None, f"{label} : {e!r}"[:240]
    return result, f"{label} : OK"


def diagnose_kick(channel):
    """Où Kick bloque-t-il ? Rejoue chaque étape de la connexion et dit laquelle échoue.

    Where does Kick block? Replays each connection step and says which one fails."""
    out = []
    info, line = _step("chaîne", lambda: kick.resolve_channel(channel))
    out.append(line)
    if not info:
        return " | ".join(out)
    body = {"client": {"type": "web", "id": "live-check"}, "accepted_providers": ["pusher", "centrifugo"]}
    data, line = _step("négociation", lambda: http(
        kick.NEGOTIATE_URL.format(channel_id=info["channel_id"]), data=body, headers=kick.HEADERS, method="POST"))
    found = kick.find_endpoints(data) if data is not None else []
    out.append(line + (f" ({', '.join(str(e.get('provider')) for e in found) or 'aucun point d accès'})"
                       if data is not None else ""))
    data, line = _step("jeton", lambda: http(kick.AUTH_URL, data={"client": body["client"]},
                                             headers=kick.HEADERS, method="POST"))
    out.append(line + (f" ({'jeton trouvé' if kick.find_token(data) else 'pas de jeton'}; "
                       f"clés : {', '.join(sorted(data)) if isinstance(data, dict) else type(data).__name__})"
                       if data is not None else ""))
    return " | ".join(out)


CHECKS = {"twitch": check_twitch, "kick": check_kick, "steamtv": check_steamtv}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--platform", choices=sorted(CHECKS), action="append")
    parser.add_argument("--summary", help="fichier Markdown du résumé / Markdown summary file")
    args = parser.parse_args(argv)
    platforms = args.platform or list(CHECKS)
    lines, failed = ["| Plateforme | Résultat | Détail |", "|---|---|---|"], []
    for platform in platforms:
        tried = []
        diagnosed = False
        for channel in CHANNELS[platform]:
            try:
                passed, detail = CHECKS[platform](channel)
            except Exception as e:  # le script doit toujours finir son résumé / the script must always finish
                passed, detail = False, f"exception : {e!r}"
            if not passed and platform == "kick" and not diagnosed:
                diagnosed = True
                try:
                    detail += f" ; diagnostic : {diagnose_kick(channel)}"
                except Exception as e:  # le diagnostic ne doit jamais casser le check / must never break the check
                    detail += f" ; diagnostic impossible : {e!r}"
            tried.append(f"{channel} ({detail})")
            print(f"{platform:8} {channel:15} {'OK' if passed else 'échec'} : {detail}", flush=True)
            if passed:
                break
        else:
            failed.append(platform)
        lines.append(f"| {platform} | {'échec' if platform in failed else 'OK'} | {'<br>'.join(tried)} |")
    summary = "\n".join(lines) + "\n"
    if args.summary:
        Path(args.summary).write_text(summary, encoding="utf-8")
    print("\n" + summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
