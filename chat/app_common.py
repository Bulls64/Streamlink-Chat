"""Constantes partagées par les modules de l'application.

Constants shared by the application modules."""
import re
from pathlib import Path

# Mémoire des emotes : les images décodées coûtent cher (une emote GIF de 60 images ≈ 1 Mo), on les plafonne
# Emote memory: decoded images are expensive (a 60-frame GIF emote ≈ 1 MB), so they are capped
IMAGE_CACHE = 200   # emotes gardées en mémoire au-delà de celles affichées (les moins récentes partent d'abord)
                    # emotes kept in memory beyond the displayed ones (least recent go first)
MAX_FRAMES = 40     # images par emote animée ; au-delà, une image sur deux, trois…
                    # frames per animated emote; beyond that, one frame out of two, three…

ASSETS = Path(__file__).resolve().parent / "assets"
REPO_URL = "https://github.com/Bulls64/Streamlink-Chat"
GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")
