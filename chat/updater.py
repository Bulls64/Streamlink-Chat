"""Mise à jour de Streamlink Chat depuis les releases GitHub (même mécanisme que Streamlink Launcher).

Seule une release publiée de ce dépôt est acceptée ; le fichier doit avoir la taille et l'empreinte SHA-256
publiées par GitHub et être un exécutable Windows. L'exécutable en cours est renommé en .old (Windows permet de
renommer un programme ouvert, pas de l'écraser), la nouvelle version prend sa place et redémarre.

Streamlink Chat update from the GitHub releases (same mechanism as Streamlink Launcher).

Only a published release of this repository is accepted; the file must have the size and SHA-256 digest
published by GitHub and be a Windows executable. The running executable is renamed to .old (Windows allows
renaming an open program, not overwriting it), the new version takes its place and restarts.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .core import FROZEN, log

REPO = "Bulls64/Streamlink-Chat"
REPO_URL = f"https://github.com/{REPO}"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "StreamlinkChat-{version}.exe"
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
MIN_BYTES, MAX_BYTES = 1_000_000, 100 * 1024 * 1024
OLD_SUFFIX = ".old"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StreamlinkChat"


class UpdateError(Exception):
    """Échec de mise à jour ; .key est la clé de traduction du message à afficher.

    Update failure; .key is the translation key of the message to show."""

    def __init__(self, key):
        super().__init__(key)
        self.key = key


def parse_version(text):
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(x or 0) for x in m.groups()) if m else (0, 0, 0)


def _http_get_json(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_release(data):
    """Réponse de l'API GitHub -> {version, tag, page, asset} ou None. asset = {name, url, size, sha256} ou None.
    Seules une release publiée (ni brouillon ni préversion) et l'adresse exacte attendue sur ce dépôt passent.

    GitHub API response -> {version, tag, page, asset} or None. asset = {name, url, size, sha256} or None.
    Only a published release (neither draft nor pre-release) and the exact address expected on this repository pass."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or "")
    m = TAG_RE.match(tag)
    if not m:
        return None
    version = m.group(1)
    release = {"version": version, "tag": tag, "page": f"{REPO_URL}/releases/tag/{tag}", "asset": None}
    name = ASSET_NAME.format(version=version)
    url = f"{REPO_URL}/releases/download/{tag}/{name}"
    for a in data.get("assets") or []:
        if not isinstance(a, dict) or a.get("name") != name:
            continue
        size, digest = a.get("size"), SHA256_RE.match(str(a.get("digest") or ""))
        if (a.get("browser_download_url") == url and digest and isinstance(size, int) and not isinstance(size, bool)
                and MIN_BYTES <= size <= MAX_BYTES):
            release["asset"] = {"name": name, "url": url, "size": size, "sha256": digest.group(1)}
    return release


def check_update(current=None):
    """{current, latest, update, release, error} ; 'update' vaut None si on ne peut pas conclure.

    {current, latest, update, release, error}; 'update' is None if no conclusion can be drawn."""
    if current is None:
        from . import __version__ as current
    result = {"current": current, "latest": None, "update": None, "release": None, "error": None}
    try:
        data = _http_get_json(RELEASES_API, 10)
    except Exception as e:
        log.warning("Recherche de mise à jour impossible : %s", e)
        result["error"] = "release" if getattr(e, "code", None) == 404 else "network"
        return result
    release = parse_release(data)
    if release is None:
        result["error"] = "release"
        return result
    result.update(latest=release["version"], release=release,
                  update=parse_version(release["version"]) > parse_version(current))
    return result


def can_self_update():
    """Vrai pour l'exécutable Windows dont le dossier est modifiable ; sinon, la page de la release s'ouvre.

    True for the Windows executable whose folder is writable; otherwise, the release page opens."""
    if not (FROZEN and os.name == "nt"):
        return False
    exe = Path(sys.executable)
    return os.access(exe.parent, os.W_OK) and os.access(exe, os.W_OK)


def should_auto_update(cfg, result, updated_from=None, can_update=None):
    """Installer sans demander ? Oui si l'option est active (avec la vérification au démarrage), si une version plus
    récente a un fichier téléchargeable, si l'exécutable peut se remplacer, et si l'on ne sort pas déjà d'une mise
    à jour (pas de boucle).

    Install without asking? Yes if the option is on (along with the start-up check), if a newer
    version has a downloadable file, if the executable can replace itself, and if we are not just coming out of an
    update (no loop)."""
    if can_update is None:
        can_update = can_self_update()
    release = (result or {}).get("release") or {}
    return bool(cfg.get("auto_update") and cfg.get("update_check") and (result or {}).get("update")
                and release.get("asset") and can_update and not updated_from)


def _safe_opener():
    """Ouvreur qui refuse toute redirection hors de GitHub ou en clair (http).

    Opener that refuses any redirect outside GitHub or in clear text (http)."""
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            u = urlparse(newurl)
            host = (u.hostname or "").lower()
            if u.scheme != "https" or not (host == "github.com"
                                           or host.endswith((".github.com", ".githubusercontent.com"))):
                raise urllib.error.URLError(f"redirection refusée : {u.scheme}://{host}")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    return urllib.request.build_opener(Redirect)


def _open_download(url, timeout=20):
    return _safe_opener().open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def download_update(release, dest_dir, progress=None, cancel=None, opener=None):
    """Télécharge et contrôle l'exécutable de la release (taille, SHA-256, en-tête « MZ »). Renvoie son chemin ;
    lève UpdateError (le fichier partiel est alors supprimé). progress(reçus, total) ; cancel : threading.Event.

    Downloads and checks the release's executable (size, SHA-256, "MZ" header). Returns its path;
    raises UpdateError (the partial file is then deleted). progress(received, total); cancel: threading.Event."""
    asset = (release or {}).get("asset")
    if not asset:
        raise UpdateError("app_err_release")
    dest = Path(dest_dir) / (asset["name"] + ".download")
    digest, done, ok = hashlib.sha256(), 0, False
    try:
        try:
            resp = (opener or _open_download)(asset["url"])
        except Exception as e:
            log.warning("Téléchargement impossible : %s", e)
            raise UpdateError("app_err_network") from e
        try:
            with resp, open(dest, "wb") as out:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise UpdateError("app_err_cancelled")
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > asset["size"]:
                        raise UpdateError("app_err_hash")
                    digest.update(chunk)
                    out.write(chunk)
                    if progress:
                        progress(done, asset["size"])
        except UpdateError:
            raise
        except Exception as e:
            log.warning("Téléchargement interrompu : %s", e)
            raise UpdateError("app_err_download") from e
        if done != asset["size"]:
            raise UpdateError("app_err_download")
        if digest.hexdigest() != asset["sha256"]:
            raise UpdateError("app_err_hash")
        with open(dest, "rb") as f:
            if f.read(2) != b"MZ":
                raise UpdateError("app_err_hash")
        ok = True
        return dest
    finally:
        if not ok:
            try:
                dest.unlink()
            except OSError:
                pass


def _parse_authenticode(text):
    lines = (text or "").strip().splitlines()
    status, _, subject = (lines[-1] if lines else "").partition("|")
    return (status.strip(), subject.strip() or None) if status.strip() else ("error", None)


def authenticode(path, timeout=40):
    """Signature Authenticode : (statut, signataire) ; 'error' si PowerShell est indisponible.

    Authenticode signature: (status, signer); 'error' if PowerShell is unavailable."""
    if os.name != "nt":
        return "error", None
    try:
        script = "$s = Get-AuthenticodeSignature -LiteralPath $env:SL_FILE; '{0}|{1}' -f $s.Status, $s.SignerCertificate.Subject"
        out = subprocess.run([shutil.which("powershell") or "powershell", "-NoProfile", "-NonInteractive",
                              "-ExecutionPolicy", "Bypass", "-Command", script],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             env=dict(os.environ, SL_FILE=str(path)), check=False)
        return _parse_authenticode(out.stdout)
    except Exception as e:
        log.warning("Lecture de la signature impossible : %s", e)
        return "error", None


def _common_name(subject):
    m = re.search(r"CN=([^,]+)", subject or "")
    return (m.group(1) if m else subject or "").strip()


def check_signature(current_file, new_file, probe=None):
    """None si la nouvelle version peut être installée, sinon la clé du message d'erreur. Un exécutable signé ne
    peut être remplacé que par un exécutable signé par le même éditeur ; sinon, seule une signature invalide
    (fichier modifié) est refusée.

    None if the new version can be installed, otherwise the key of the error message. A signed executable can
    only be replaced by an executable signed by the same publisher; otherwise, only an invalid signature
    (modified file) is refused."""
    probe = probe or authenticode
    cur_status, cur_subject = probe(current_file)
    new_status, new_subject = probe(new_file)
    if cur_status == "Valid":
        same = new_status == "Valid" and _common_name(new_subject) == _common_name(cur_subject)
        return None if same else "app_err_signature"
    return None if new_status in ("Valid", "NotSigned", "error") else "app_err_signature"


def target_exe(exe, old_version, new_version):
    """StreamlinkChat-0.1.0.exe mis à jour en 0.2.0 devient StreamlinkChat-0.2.0.exe (un nom sans version reste).

    StreamlinkChat-0.1.0.exe updated to 0.2.0 becomes StreamlinkChat-0.2.0.exe (a name without a version stays)."""
    exe = Path(exe)
    if not old_version or not new_version or old_version == new_version:
        return exe
    renamed = re.sub(r"(?<![\d.])" + re.escape(str(old_version)) + r"(?!\.?\d)", str(new_version), exe.name)
    target = exe.with_name(renamed)
    return target if renamed != exe.name and not target.exists() else exe


def install_update(new_file, exe=None, final=None):
    """Renomme l'exécutable en cours en .old, met la nouvelle version à sa place (ou sous `final`).
    En cas d'échec, l'ancien est remis.

    Renames the running executable to .old, puts the new version in its place (or under `final`).
    On failure, the old one is put back."""
    exe, new_file = Path(exe or sys.executable), Path(new_file)
    final = Path(final) if final else exe
    old = exe.with_name(exe.name + OLD_SUFFIX)
    try:
        old.unlink(missing_ok=True)
        os.replace(exe, old)
    except OSError as e:
        log.warning("Remplacement impossible : %s", e)
        raise UpdateError("app_err_install") from e
    try:
        os.replace(new_file, final)
    except OSError as e:
        log.warning("Remplacement impossible : %s", e)
        try:
            os.replace(old, exe)
        except OSError:
            log.error("L'ancien exécutable n'a pas pu être remis en place (%s)", old)
        raise UpdateError("app_err_install") from e
    return old


def cleanup_leftovers(exe=None, tries=30, delay=1.0):
    """Au démarrage : ancien exécutable (.old, l'ancienne instance peut mettre quelques secondes à se fermer)
    et téléchargements interrompus.

    At start-up: old executable (.old, the old instance may take a few seconds to close)
    and interrupted downloads."""
    exe = Path(exe or sys.executable)
    old = exe.with_name(exe.name + OLD_SUFFIX)
    for _i in range(tries):
        if not old.exists():
            break
        try:
            old.unlink()
            break
        except OSError:
            time.sleep(delay)
    for f in [*exe.parent.glob("StreamlinkChat-*.exe.download"), *exe.parent.glob("StreamlinkChat-*.exe" + OLD_SUFFIX)]:
        try:
            f.unlink()
        except OSError:
            pass


def relaunch(exe=None, old_version=None, extra_args=()):
    """Démarre la nouvelle version, détachée ; elle attend la fin de celle-ci (--wait-pid) avant de démarrer.
    PYINSTALLER_RESET_ENVIRONMENT : sinon l'exécutable réutiliserait le dossier temporaire de l'ancien.

    Starts the new version, detached; it waits for this one to end (--wait-pid) before starting.
    PYINSTALLER_RESET_ENVIRONMENT: otherwise the executable would reuse the old one's temporary folder."""
    exe = str(exe or sys.executable)
    args = [exe, "--wait-pid", str(os.getpid()), *extra_args]
    if old_version:
        args += ["--updated-from", str(old_version)]
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen(args, cwd=os.path.dirname(exe), close_fds=True, creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
        return True
    except OSError as e:
        log.error("Redémarrage impossible : %s", e)
        return False


def wait_for_pid(pid, timeout=20):
    """Attend la fin d'un processus (l'ancienne version, après une mise à jour). True s'il est terminé.

    Waits for a process to end (the old version, after an update). True if it has ended."""
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            handle = k32.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
            if not handle:
                return True
            try:
                return k32.WaitForSingleObject(handle, int(timeout * 1000)) == 0
            finally:
                k32.CloseHandle(handle)
        except Exception as e:
            log.warning("Attente de l'ancienne instance impossible : %s", e)
            return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(int(pid), 0)
        except (OSError, ValueError):
            return True
        time.sleep(0.2)
    return False


def arg_value(name, argv=None):
    argv = sys.argv if argv is None else argv
    for i, a in enumerate(argv[:-1]):
        if a == name:
            return argv[i + 1]
    return None
