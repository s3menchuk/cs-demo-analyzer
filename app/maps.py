import json
from pathlib import Path
from functools import lru_cache

MANIFEST = Path(__file__).resolve().parents[1] / "static" / "maps" / "manifest.json"


@lru_cache(maxsize=1)
def catalog():
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def level_for(map_name, z):
    levels = catalog().get(map_name, {}).get("levels", [])
    if z is not None:
        for level in levels:
            if (level["min_z"] is None or z >= level["min_z"]) and (level["max_z"] is None or z < level["max_z"]):
                return level["id"]
    return "default"
