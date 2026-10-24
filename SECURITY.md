# Security policy · Politique de sécurité

## English

**Supported versions.** Only the [latest release](https://github.com/Bulls64/Streamlink-Chat/releases/latest) receives fixes.

**Reporting a vulnerability.** Please do **not** open a public issue. Use the private form:
[Report a vulnerability](https://github.com/Bulls64/Streamlink-Chat/security/advisories/new)
(Security tab → *Report a vulnerability*). Include the version, the steps to reproduce and the impact.

**Good to know.**
- The executables are **not code-signed**. Check the SHA-256 given in `SHA256SUMS.txt` and in the release.
- Account tokens are stored in `chat.json`: encrypted with Windows DPAPI on Windows (readable only by your Windows account on this PC), in plain text on Linux (in your home folder, in a file only your user can read).
- Logging in uses your own Twitch / Kick application; no secret is shipped with the program.

## Français

**Versions prises en charge.** Seule la [dernière version](https://github.com/Bulls64/Streamlink-Chat/releases/latest) reçoit des correctifs.

**Signaler une faille.** N'ouvrez **pas** de ticket public. Utilisez le formulaire privé :
[Signaler une vulnérabilité](https://github.com/Bulls64/Streamlink-Chat/security/advisories/new)
(onglet Security → *Report a vulnerability*). Indiquez la version, les étapes pour reproduire et l'impact.

**À savoir.**
- Les exécutables ne sont **pas signés**. Vérifiez l'empreinte SHA-256 de `SHA256SUMS.txt` et de la release.
- Les jetons des comptes sont enregistrés dans `chat.json` : chiffrés par DPAPI sous Windows (lisibles seulement par votre compte Windows sur ce PC), en clair sous Linux (dans votre dossier personnel, dans un fichier lisible par votre seul utilisateur).
- La connexion passe par votre propre application Twitch / Kick ; aucun secret n'est livré avec le programme.
