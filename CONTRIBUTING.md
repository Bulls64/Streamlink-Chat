# Contributing · Contribuer

## English

Thanks for helping! Bug reports, translations and pull requests are welcome.

1. **Open an issue first** for anything bigger than a small fix, so we can agree on the approach.
2. **Setup**: Python 3.10+ and nothing else (no third-party dependency). Tkinter is needed to run the interface.
3. **Run the checks** before opening a pull request:
   ```
   python -m unittest discover -s tests -v          # protocols (fake local servers), files, translations
   python -m pip install ruff && python -m ruff check .
   xvfb-run -a python -m unittest tests.test_gui    # GUI smoke test (Linux; skipped without a display)
   ```
4. **Translations** live in `lang/*.json`. Every language must have exactly the same keys (a test checks it).
5. **Rules of the code base**: network work runs in threads and talks to the interface only through the event queue (`ChatApp.events`); never touch Tk from another thread. Platform code (`twitch.py`, `kick.py`, `steam.py`) has no UI. Chat services change often: parse their data tolerantly and add a test with a fake server for each change.
6. **Changelog**: add a line under *Unreleased* in `CHANGELOG.md`, in both English and French.
7. Releases are cut by the maintainer (version in `chat/__init__.py` and `packaging/version_info.txt`, then a `vX.Y.Z` tag).

## Français

Merci d'aider ! Signalements de bugs, traductions et pull requests sont les bienvenus.

1. **Ouvrez d'abord un ticket** pour tout ce qui dépasse un petit correctif.
2. **Environnement** : Python 3.10+ et rien d'autre (aucune dépendance tierce). Tkinter est nécessaire pour l'interface.
3. **Lancez les vérifications** avant la pull request (commandes ci-dessus).
4. **Traductions** : `lang/*.json`, mêmes clés dans toutes les langues (un test le vérifie).
5. **Règles du code** : le réseau tourne dans des fils à part et ne parle à l'interface que par la file d'événements (`ChatApp.events`) ; jamais de Tk depuis un autre fil. Le code des plateformes (`twitch.py`, `kick.py`, `steam.py`) ne contient aucune interface. Les services de chat changent souvent : lisez leurs données avec tolérance et ajoutez un test avec un faux serveur à chaque changement.
6. **Journal des modifications** : une ligne sous *Unreleased* dans `CHANGELOG.md`, en anglais et en français.
7. Les versions sont publiées par le mainteneur (version dans `chat/__init__.py` et `packaging/version_info.txt`, puis un tag `vX.Y.Z`).
