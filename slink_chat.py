"""Streamlink Chat — point d'entrée.

Lancer avec :  pythonw slink_chat.py   (sans console)
          ou :  python slink_chat.py [lien de chaîne | --open twitch:chaîne …]
"""
import sys

from chat.app import main, targets_from_argv

if __name__ == "__main__":
    main(targets_from_argv(sys.argv[1:]))
