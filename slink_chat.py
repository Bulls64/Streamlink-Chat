"""Streamlink Chat — point d'entrée.

Lancer avec :  pythonw slink_chat.py   (sans console)
          ou :  python slink_chat.py [lien de chaîne | --open twitch:chaîne …]

Streamlink Chat — entry point.

Start with:  pythonw slink_chat.py   (without a console)
        or:  python slink_chat.py [channel link | --open twitch:channel …]
"""
import sys

from chat.app import main, targets_from_argv

if __name__ == "__main__":
    main(targets_from_argv(sys.argv[1:]))
