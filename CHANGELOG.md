# Changelog

**[English](#english) · [Français](#français)**

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## English

## [Unreleased]

## [0.4.0] - 2026-11-17

### Added
- **macOS app** for Apple Silicon Macs (macOS 11 or newer): `StreamlinkChat-<version>-macOS-arm64.dmg`, with `Streamlink Chat.app` (embedded Python and Tcl/Tk, ad-hoc signed, not notarized: allow it once in *System Settings › Privacy & Security*). Built by `packaging/macos/build_dmg.sh`; the CI builds it on macOS 15, starts the app, mounts the image to check it, then attaches it to the release.
- On macOS: data in `~/Library/Application Support/Streamlink Chat` (never inside the app bundle), Homebrew's and pipx's folders added to the `PATH` for the ▶ button, language and light/dark theme read from System Settings. Streamlink Launcher 1.8.0 finds `Streamlink Chat.app` for *Open the chat*.

### Changed
- **Code clean-up**: unused code removed (`app_icon` and its helper, `set_text`, `set_options`, `Popover.move`, two unused regular expressions, attributes written but never read, the unused `own_name` parameter); the luminance and hex-to-RGB color helpers exist once, in `chat/common.py`, instead of twice. No change in behavior.

## [0.3.2] - 2026-11-16

### Added
- **Linux packages**: `streamlink-chat_<version>_amd64.deb` (Debian, Ubuntu, Linux Mint) and `streamlink-chat-<version>-1.x86_64.rpm` (Fedora, openSUSE), made from the AppImage (same embedded Python and Tcl/Tk), installed in `/opt/streamlink-chat` with a menu entry, the icon and the `streamlink-chat` command, which Streamlink Launcher 1.7.1 finds for *Open the chat*. The CI installs and starts the `.deb` on Ubuntu 22.04 and the `.rpm` on Fedora, then attaches both to the release, with their SHA-256.

### Fixed
- Installed in a system folder and started by root (who can write there), the chat kept its data next to itself: a package install always uses `~/.config/streamlink-chat`, like the AppImage.

### Changed
- CI: apt packages are installed by `packaging/ci_apt.sh` (only the missing ones, with retries and a fallback mirror), as in Streamlink Launcher. A Twitch login test waits for the saved account (up to 10 s) instead of a fixed number of rounds, which was not always enough on Windows runners.

## [0.3.1] - 2026-11-16

### Fixed
- **Kick chats stayed in error** ("Repeated failures: the site may have changed"). Kick now refuses the old format of the two requests that open a chat (HTTP 400), so no guest token was obtained and the real-time server closed the connection (3501). The negotiation now sends `capabilities.accepted_providers` and the token request `client_id`, as kick.com does; the old formats are only tried after a 400. The guest token (about 45 minutes) is renewed before it expires, instead of a reconnection.

### Removed
- The old Pusher connection used as a last resort: Kick retired its key (`4001 App key … not in this cluster`). Pusher is still used if Kick's negotiation offers it.

## [0.3.0] - 2026-11-07

### Added
- **Twitch login without creating an application.** *Log in to Twitch* now uses Streamlink Chat's own Twitch application (a public client: no secret is shipped). The *Client ID* field becomes optional, for those who prefer their own application.
- **Open from Streamlink Launcher.** Launcher 1.6.0 opens a Twitch or Kick favorite's chat here (right-click › *Open the chat*), or opens it with the stream; a chat already open gets the channel as a new tab.
- **Daily check against the real platforms** (`packaging/live_check.py`, *Live check* workflow): connects read-only to Twitch, Kick and Steam TV, opens an issue when one no longer answers as expected and closes it once everything passes again.

### Changed
- **Tests**: 81 → 96, with interface flows beyond start-up (tabs, sending, history, completion, menus, settings, Twitch login and logout); coverage is measured in the CI and must stay at 65% or more (69% today).

## [0.2.3] - 2026-11-07

### Added
- **Links from the chat ask before opening.** Clicking a link shows the site's name first, with *Open*, *Always open links from this site*, *Copy link* and *Cancel*. A long name is cut at its start, so the end that says whom the site belongs to stays visible. Links from Twitch, Kick and Steam, and from approved sites, open directly. *Settings › Links* turns the question off or forgets the approved sites.
- **Warning when Kick or Steam TV keep failing.** After five unexpected failures in a row, the chat header says the site may have changed, and a message offers to check for updates (*Settings › Updates*). The automatic reconnection is unchanged; an offline channel does not count as a failure.

### Fixed
- A notification too long for the window is now shortened instead of overflowing it.
- The version links at the end of this CHANGELOG now include 0.2.2.

## [0.2.2] - 2026-10-25

### Changed
- **`chat/app.py` split into smaller modules** (2,063 → about 390 lines): channel tabs and chat view (`app_view.py`), tabs, connections and events, badges and emotes, sending and menus, settings, app updates and accounts, each in an `app_*.py` mixin of `ChatApp`; shared constants in `app_common.py`. The methods are moved unchanged; no change in behavior.

## [0.2.1] - 2026-10-24

### Added
- **Code of conduct** (`CODE_OF_CONDUCT.md`, English and French).

### Changed
- **Platform pills**, as in Streamlink Launcher: the *Twitch ▾* list next to the add field is replaced by Twitch, Kick and Steam TV pills. The selected one is filled with its platform's color, the add field takes that color and names the platform (*Add a Kick chat: channel or link*), and pasting a link selects its platform by itself.

### Fixed
- **Much lower memory use with animated emotes and several chats.** Measured with 6 chats and 50 animated emotes each: about 1 GB before, about 140 MB now. Animated emotes only play in the displayed chat (the frames of the other chats are freed, and nothing is decoded when *Animated emotes* is off), an emote keeps at most 40 frames, and emote images no longer pile up: beyond 200, the least recently seen ones are dropped (those still on screen stay).
- Chats now keep 500 messages by default instead of 1000 (*Settings › Display*). Existing settings are kept.
- **Settings file readable by you only (Linux).** `chat.json`, which holds the account tokens, and its `.bak` copy are now saved with owner-only permissions (0600), including when an older file was readable by other users: it is fixed at the next save. No change on Windows, where the tokens stay encrypted with DPAPI.
- **Kick sign-in when port 48125 is already used** by another program: the message now says so, instead of a generic failure.
- **Fewer silent errors.** Failures that were swallowed without a trace (reading the Windows theme, the system language, the proxy, a message from a second instance, files that can't be deleted after an update, saving on exit...) are now recorded in the log (debug level), which makes problems easier to diagnose.

## [0.2.0] - 2026-10-20

### Added
- **Platform colors**, as in Streamlink Launcher: the chat card, its header (with a colored dot before the channel name) and the tabs take the color of their platform: purple for Twitch, lime green for Kick, navy blue for Steam TV (previously Steam blue). Can be turned off in *Settings › Display*.
- **Updates from GitHub**, as in Streamlink Launcher: *Settings › Updates* shows the installed version, checks the latest release (at start-up, on by default, or with *Check*) and, for the Windows executable, downloads it, checks its size and SHA-256 (and signature if the current one is signed), replaces the running file and restarts with your open chats. *Automatic updates* (off by default) does it by itself at start-up. From the sources or with the AppImage, the release page opens instead. A badge on the settings button shows when an update is available.

## [0.1.0] - 2026-10-17

### Added
- First release: Twitch, Kick and Steam TV chats in one window, in the style of Streamlink Launcher. Tabs (restored at start-up), badges, readable username colors, emotes as images (Twitch, BetterTTV, FrankerFaceZ, 7TV; animated GIFs), links, replies and events, mentions and chosen words highlighted, deleted messages struck out, scroll pause with *New messages*, username and emote completion, user, message and tab menus, ▶ to watch with Streamlink.
- Reading without an account. Writing on Twitch (device-code login with your own application) and Kick (official API, OAuth with PKCE). Tokens encrypted with DPAPI on Windows.
- Kick follows Kick's new real-time chat (Centrifugo, since 13 October 2026), with the old Pusher connection as a fallback: **experimental**, the protocol is undocumented.
- Steam TV chats, read-only (Steam's internal broadcast API).
- Single instance (a second start sends its chats to the open window), five languages, light/dark/automatic theme.
- Windows executable and Linux AppImage built by GitHub Actions; protocol tests against local fake servers.

---

## Français

## [Non publié]

## [0.4.0] - 2026-11-17

### Ajouté
- **Application macOS** pour les Mac à puce Apple (macOS 11 ou plus récent) : `StreamlinkChat-<version>-macOS-arm64.dmg`, avec `Streamlink Chat.app` (Python et Tcl/Tk embarqués, signée ad hoc, non notarisée : à autoriser une fois dans *Réglages Système › Confidentialité et sécurité*). Construite par `packaging/macos/build_dmg.sh` ; la CI la construit sous macOS 15, lance l'app, monte l'image pour la vérifier, puis la joint à la release.
- Sous macOS : données dans `~/Library/Application Support/Streamlink Chat` (jamais dans le bundle de l'app), dossiers de Homebrew et de pipx ajoutés au `PATH` pour le bouton ▶, langue et thème clair/sombre lus dans Réglages Système. Streamlink Launcher 1.8.0 trouve `Streamlink Chat.app` pour *Ouvrir le chat*.

### Modifié
- **Nettoyage du code** : code inutilisé supprimé (`app_icon` et sa fonction d'aide, `set_text`, `set_options`, `Popover.move`, deux expressions régulières inutilisées, des attributs écrits mais jamais lus, le paramètre inutilisé `own_name`) ; les fonctions de couleur (luminance, hexadécimal vers RVB) n'existent plus qu'une fois, dans `chat/common.py`, au lieu de deux. Aucun changement de comportement.

## [0.3.2] - 2026-11-16

### Ajouté
- **Paquets Linux** : `streamlink-chat_<version>_amd64.deb` (Debian, Ubuntu, Linux Mint) et `streamlink-chat-<version>-1.x86_64.rpm` (Fedora, openSUSE), faits à partir de l'AppImage (même Python et Tcl/Tk embarqués), installés dans `/opt/streamlink-chat` avec une entrée de menu, l'icône et la commande `streamlink-chat`, que Streamlink Launcher 1.7.1 trouve pour *Ouvrir le chat*. La CI installe et lance le `.deb` sous Ubuntu 22.04 et le `.rpm` sous Fedora, puis les joint à la release avec leur SHA-256.

### Corrigé
- Installé dans un dossier système et lancé par root (qui peut y écrire), le chat gardait ses données à côté de lui : une installation par paquet utilise toujours `~/.config/streamlink-chat`, comme l'AppImage.

### Modifié
- CI : les paquets apt sont installés par `packaging/ci_apt.sh` (seulement ceux qui manquent, avec reprises et miroir de secours), comme dans Streamlink Launcher. Un test de connexion Twitch attend le compte enregistré (jusqu'à 10 s) au lieu d'un nombre fixe de tours, pas toujours suffisant sur les runners Windows.

## [0.3.1] - 2026-11-16

### Corrigé
- **Les chats Kick restaient en erreur** (« Échecs répétés : le site a peut-être changé »). Kick refuse maintenant l'ancien format des deux requêtes qui ouvrent un chat (HTTP 400) : aucun jeton invité n'était obtenu et le serveur temps réel fermait la connexion (3501). La négociation envoie désormais `capabilities.accepted_providers` et la demande de jeton `client_id`, comme kick.com ; les anciens formats ne sont essayés qu'après un refus 400. Le jeton invité (environ 45 minutes) est renouvelé avant d'expirer, au lieu d'une reconnexion.

### Supprimé
- L'ancienne connexion Pusher de dernier recours : Kick a retiré sa clé (`4001 App key … not in this cluster`). Pusher reste utilisé si la négociation de Kick le propose.

## [0.3.0] - 2026-11-07

### Ajouté
- **Connexion à Twitch sans créer d'application.** *Se connecter à Twitch* utilise maintenant l'application Twitch de Streamlink Chat (un client public : aucun secret n'est livré). Le champ *Client ID* devient facultatif, pour qui préfère sa propre application.
- **Ouverture depuis Streamlink Launcher.** Launcher 1.6.0 ouvre ici le chat d'un favori Twitch ou Kick (clic droit › *Ouvrir le chat*), ou l'ouvre avec le stream ; un chat déjà ouvert reçoit la chaîne en nouvel onglet.
- **Vérification quotidienne contre les vraies plateformes** (`packaging/live_check.py`, workflow *Live check*) : connexion en lecture seule à Twitch, Kick et Steam TV, ticket ouvert quand l'une ne répond plus comme prévu, refermé quand tout repasse.

### Modifié
- **Tests** : 81 → 96, avec des parcours de l'interface au-delà du démarrage (onglets, envoi, historique, complétion, menus, paramètres, connexion et déconnexion Twitch) ; la couverture est mesurée en CI et doit rester à 65 % ou plus (69 % aujourd'hui).

## [0.2.3] - 2026-11-07

### Ajouté
- **Les liens du chat demandent avant de s'ouvrir.** Un clic sur un lien montre d'abord le nom du site, avec *Ouvrir*, *Toujours ouvrir les liens de ce site*, *Copier le lien* et *Annuler*. Un nom trop long est coupé au début, pour garder visible la fin, qui dit à qui appartient le site. Les liens de Twitch, Kick et Steam, et ceux des sites approuvés, s'ouvrent directement. *Paramètres › Liens* désactive la question ou oublie les sites approuvés.
- **Avertissement quand Kick ou Steam TV échouent sans arrêt.** Après cinq échecs inattendus de suite, l'en-tête du chat indique que le site a peut-être changé, et un message propose de chercher une mise à jour (*Paramètres › Mises à jour*). La reconnexion automatique ne change pas ; une chaîne hors ligne ne compte pas comme un échec.

### Corrigé
- Une notification trop longue pour la fenêtre est maintenant raccourcie au lieu de déborder.
- Les liens de versions en fin de CHANGELOG comprennent maintenant la 0.2.2.

## [0.2.2] - 2026-10-25

### Modifié
- **`chat/app.py` découpé en modules plus petits** (2 063 → environ 390 lignes) : onglets de chaîne et vue d'un chat (`app_view.py`), onglets, connexions et événements, badges et emotes, envoi et menus, paramètres, mises à jour de l'appli et comptes, chacun dans un mixin `app_*.py` de `ChatApp` ; constantes communes dans `app_common.py`. Les méthodes sont déplacées sans modification ; aucun changement de comportement.

## [0.2.1] - 2026-10-24

### Ajouté
- **Code de conduite** (`CODE_OF_CONDUCT.md`, anglais et français).

### Modifié
- **Pastilles des plateformes**, comme dans Streamlink Launcher : la liste *Twitch ▾* à côté du champ d'ajout est remplacée par des pastilles Twitch, Kick et Steam TV. La pastille choisie est pleine de la couleur de sa plateforme, le champ d'ajout prend cette couleur et nomme la plateforme (*Ajouter un chat Kick : chaîne ou lien*), et coller un lien sélectionne sa plateforme tout seul.

### Corrigé
- **Mémoire bien plus basse avec les emotes animées et plusieurs chats.** Mesuré avec 6 chats et 50 emotes animées chacun : environ 1 Go avant, environ 140 Mo maintenant. Les emotes animées ne s'animent que dans le chat affiché (les images des autres chats sont libérées, et rien n'est décodé si *Emotes animées* est désactivé), une emote garde au plus 40 images, et les images d'emotes ne s'accumulent plus : au-delà de 200, les moins récemment vues sont retirées (celles encore à l'écran restent).
- Les chats gardent maintenant 500 messages par défaut au lieu de 1000 (*Paramètres › Affichage*). Les réglages existants sont conservés.
- **Fichier de réglages lisible par toi seul (Linux).** `chat.json`, qui contient les jetons des comptes, et sa copie `.bak` sont maintenant enregistrés avec les droits du seul propriétaire (0600), y compris quand un ancien fichier était lisible par les autres utilisateurs : corrigé à la prochaine sauvegarde. Rien ne change sous Windows, où les jetons restent chiffrés par DPAPI.
- **Connexion à Kick quand le port 48125 est déjà utilisé** par un autre programme : le message le dit maintenant, au lieu d'un échec générique.
- **Moins d'erreurs silencieuses.** Des échecs avalés sans trace (lecture du thème de Windows, de la langue du système, du proxy, d'un message d'une seconde instance, fichiers impossibles à supprimer après une mise à jour, enregistrement à la fermeture...) sont maintenant écrits dans le journal (niveau debug), ce qui facilite le diagnostic.

## [0.2.0] - 2026-10-20

### Ajouté
- **Couleurs par plateforme**, comme dans Streamlink Launcher : la carte du chat, son en-tête (avec une pastille de couleur devant le nom de la chaîne) et les onglets prennent la couleur de leur plateforme : violet pour Twitch, vert citron pour Kick, bleu nuit pour Steam TV (auparavant bleu Steam). Désactivable dans *Paramètres › Affichage*.
- **Mises à jour depuis GitHub**, comme dans Streamlink Launcher : *Paramètres › Mises à jour* affiche la version installée, consulte la dernière release (au démarrage, activé par défaut, ou avec *Vérifier*) et, pour l'exécutable Windows, la télécharge, contrôle sa taille et son SHA-256 (et sa signature si l'actuel est signé), remplace le fichier en cours et redémarre avec tes chats ouverts. *Mises à jour automatiques* (désactivé par défaut) le fait tout seul au démarrage. Depuis les sources ou avec l'AppImage, la page de la release s'ouvre à la place. Une pastille sur le bouton des paramètres signale une mise à jour disponible.

## [0.1.0] - 2026-10-17

### Ajouté
- Première version : les chats Twitch, Kick et Steam TV dans une fenêtre, dans le style de Streamlink Launcher. Onglets (rouverts au démarrage), badges, couleurs de pseudo lisibles, emotes en images (Twitch, BetterTTV, FrankerFaceZ, 7TV ; GIF animés), liens, réponses et événements, mentions et mots choisis surlignés, messages supprimés barrés, défilement en pause avec *Nouveaux messages*, complétion des pseudos et emotes, menus pseudo, message et onglet, ▶ pour regarder avec Streamlink.
- Lecture sans compte. Écriture sur Twitch (connexion par code avec ta propre application) et Kick (API officielle, OAuth avec PKCE). Jetons chiffrés par DPAPI sous Windows.
- Kick suit le nouveau chat temps réel de Kick (Centrifugo, depuis le 13 octobre 2026), avec l'ancienne connexion Pusher en secours : **expérimental**, le protocole n'est pas documenté.
- Chats Steam TV en lecture seule (API interne des diffusions Steam).
- Instance unique (une seconde ouverture envoie ses chats à la fenêtre déjà ouverte), cinq langues, thème clair / sombre / automatique.
- Exécutable Windows et AppImage Linux compilés par GitHub Actions ; tests des protocoles contre de faux serveurs locaux.

[Unreleased]: https://github.com/Bulls64/Streamlink-Chat/compare/v0.3.0...HEAD
[Non publié]: https://github.com/Bulls64/Streamlink-Chat/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Bulls64/Streamlink-Chat/compare/v0.2.3...v0.3.0
[0.2.3]: https://github.com/Bulls64/Streamlink-Chat/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Bulls64/Streamlink-Chat/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Bulls64/Streamlink-Chat/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Bulls64/Streamlink-Chat/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Bulls64/Streamlink-Chat/releases/tag/v0.1.0
