"""Mise à jour de l'application depuis les releases GitHub.

Application update from GitHub releases."""
import logging
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox

from . import __version__, updater

log = logging.getLogger("streamlink_launcher")


class UpdatesMixin:
    """Mise à jour de l'application depuis les releases GitHub.

    Application update from GitHub releases."""

    # Mise à jour de l'application (releases GitHub)
    # Application update (GitHub releases)
    # =====================================================
    def format_size(self, nbytes):
        return self.t("size_mb", size=f"{max(0, nbytes) / 1048576:.1f}".replace(".", self.t("decimal_sep")))

    def _update_app_card(self):
        t = self.t
        try:
            if not hasattr(self, "app_card") or not self.app_card.winfo_exists():
                return
        except tk.TclError:
            return
        card, state, r = self.app_card, self._app_state, self.app_update
        title = t("app_card_title", version=__version__)
        if state == "checking":
            card.set_state(True, t("app_checking"), title, button=t("btn_check"), level="busy")
        elif state == "downloading":
            done, total = self._app_dl
            card.set_state(True, t("app_downloading", percent=int(done * 100 / total) if total else 0),
                           f"{self.format_size(done)} / {self.format_size(total)}", button=t("btn_cancel"),
                           level="busy")
        elif state == "verifying":
            card.set_state(True, t("app_verifying"), t("app_verifying_detail"), button="", level="busy")
        elif state == "restart":
            card.set_state(True, t("app_restart_title"), t("app_restart_detail", latest=(r or {}).get("latest", "")),
                           button="", level="ok")
        elif state == "error":
            card.set_state(False, t("app_error_title"), t(self._app_error or "app_err_network"),
                           button=t("btn_retry"), level="warn")
        elif r and r.get("update"):
            asset = (r.get("release") or {}).get("asset")
            direct = bool(asset) and updater.can_self_update()
            detail = (t("app_update_detail", installed=__version__, size=self.format_size(asset["size"])) if direct
                      else t("app_update_manual", installed=__version__))
            card.set_state(False, t("app_update_title", latest=r["latest"]), detail,
                           button=t("btn_update") if direct else t("btn_open_release"), level="update", primary=True)
        elif r and r.get("update") is False:
            card.set_state(True, title, t("app_up_to_date"), button=t("btn_check"))
        else:
            card.set_state(True, title, updater.REPO_URL.split("//", 1)[1], button=t("btn_check"))

    def _app_card_action(self):
        state, r = self._app_state, self.app_update
        if state == "downloading":
            self._app_cancel.set()
        elif state == "idle" and r and r.get("update"):
            self.install_app_update()
        elif state in ("idle", "error"):
            self.check_app_update(manual=True)

    def _open_release_notes(self):
        rel = (self.app_update or {}).get("release")
        self.open_url(rel["page"] if rel else updater.REPO_URL + "/releases")

    def check_app_update(self, manual=False):
        """Cherche une release plus récente sur GitHub (hors de l'interface).

        Looks for a newer release on GitHub (outside the interface)."""
        if self._app_state in ("checking", "downloading", "verifying", "restart"):
            return
        self._app_state, self._app_error = "checking", None
        self._update_app_card()
        self.run_in_thread(updater.check_update, lambda result: self._app_update_checked(result, manual))

    def _app_update_checked(self, result, manual):
        t = self.t
        self._app_state = "idle"
        if isinstance(result, Exception):
            result = {"error": "network", "update": None}
        self.app_update = None if result.get("error") else result
        if result.get("error") and manual:
            self._app_state = "error"
            self._app_error = {"network": "app_err_network", "release": "app_err_release"}.get(
                result["error"], "app_err_network")
        self._update_app_card()
        self._refresh_update_badge()
        if not manual and updater.should_auto_update(self.cfg, result, self._updated_from):
            log.info("Mise à jour automatique : %s -> %s", result["current"], result["latest"])
            self.toast(t("toast_app_auto_update", latest=result["latest"]), duration=6000)
            self.install_app_update(auto=True)
            return
        if result.get("update"):
            log.info("Mise à jour disponible : %s -> %s", result["current"], result["latest"])
            self.toast(t("toast_app_update", latest=result["latest"]), "warn",
                       action=(t("btn_update"), self.open_settings), duration=8000)
        elif result.get("update") is False and manual:
            self.toast(t("toast_app_up_to_date"))

    def _refresh_update_badge(self):
        btn = getattr(self, "settings_btn", None)
        if btn is not None:
            try:
                btn.set_badge(self.c.warn if (self.app_update or {}).get("update") else None)
            except tk.TclError:
                pass

    def install_app_update(self, auto=False):
        """Télécharge la release, la contrôle, remplace l'exécutable et redémarre. Sans exécutable remplaçable
        (lancé depuis les sources, AppImage, dossier protégé…), ouvre la page de la release.

        Downloads the release, checks it, replaces the executable and restarts. Without a replaceable executable
        (started from the sources, AppImage, protected folder…), opens the release page."""
        t = self.t
        rel = (self.app_update or {}).get("release")
        if not rel:
            return
        if not (rel.get("asset") and updater.can_self_update()):
            self.open_url(rel["page"])
            self.toast(t("toast_update_page_opened"))
            return
        if not auto and not messagebox.askyesno(t("title_confirm"), t("confirm_app_update", latest=rel["version"]),
                                                parent=self):
            return
        self._app_state, self._app_error = "downloading", None
        self._app_dl = (0, rel["asset"]["size"])
        self._app_cancel = cancel = threading.Event()
        folder, exe = os.path.dirname(sys.executable), sys.executable

        def progress(done, total):
            self._app_dl = (done, total)

        def work():
            path = updater.download_update(rel, folder, progress, cancel)
            self._app_state = "verifying"
            key = updater.check_signature(exe, path)
            if key:
                try:
                    os.remove(path)
                except OSError:
                    log.debug("Fichier %s non supprimé", path, exc_info=True)
                raise updater.UpdateError(key)
            return path

        self._update_app_card()
        self.after(200, self._poll_app_update)
        self.run_in_thread(work, lambda result: self._app_downloaded(result, rel))

    def _poll_app_update(self):
        if self._app_state in ("downloading", "verifying"):
            self._update_app_card()
            self.after(200, self._poll_app_update)

    def _app_downloaded(self, result, rel):
        t = self.t
        if isinstance(result, Exception):
            key = result.key if isinstance(result, updater.UpdateError) else "app_err_download"
            if key == "app_err_cancelled":
                self._app_state = "idle"
            else:
                self._app_state, self._app_error = "error", key
                log.warning("Mise à jour échouée : %r", result)
                self.toast(t("app_error_title") + " — " + t(key), "error")
            self._update_app_card()
            return
        final = updater.target_exe(sys.executable, __version__, rel["version"])
        try:
            updater.install_update(result, final=final)
        except updater.UpdateError as e:
            try:
                os.remove(result)
            except OSError:
                log.debug("Fichier %s non supprimé", result, exc_info=True)
            self._app_state, self._app_error = "error", e.key
            self._update_app_card()
            return
        log.info("Mise à jour installée : %s -> %s", __version__, rel["version"])
        self.on_close(relaunching=True)
        if not updater.relaunch(final, old_version=__version__):
            log.error("Nouvelle version installée mais pas redémarrée : %s", final)
