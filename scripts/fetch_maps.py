"""Download a pinned set of CS2 radar textures and their matching calibration."""
import json
import re
from pathlib import Path
from urllib.request import urlopen

REVISION = "9a77417b108eab6ee8c10d1140d62c0b77f54174"
BASE = f"https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/{REVISION}/"
MAPS = ["de_mirage", "de_dust2", "de_inferno", "de_nuke", "de_ancient",
        "de_anubis", "de_overpass", "de_train", "de_vertigo"]
OUT = Path(__file__).resolve().parents[1] / "static" / "maps"


def fetch(relative):
    with urlopen(BASE + relative, timeout=60) as response:
        return response.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(fetch("data/available.json"))["maps"]
    manifest = {}
    for name in MAPS:
        entry = catalog[name]
        info = entry["radar_info"]
        levels = []
        for url in entry["radar_paths"]:
            filename = url.rsplit("/", 1)[-1]
            if filename not in (name + "_radar_psd.png", name + "_lower_radar_psd.png"):
                continue
            level = "lower" if "_lower_" in filename else "default"
            texture = fetch("images/radars/" + filename)
            if not texture.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError(f"Not a PNG: {filename}")
            (OUT / filename).write_bytes(texture)
            section = info.get("verticalsections", {}).get(level, {})
            levels.append(dict(id=level, label="Нижний этаж" if level == "lower" else "Основной этаж",
                               image="/static/maps/" + filename,
                               min_z=section.get("AltitudeMin"), max_z=section.get("AltitudeMax")))
        if not levels:
            raise ValueError(f"No radar for {name}")
        manifest[name] = dict(name=entry.get("display_name", name), pos_x=info["pos_x"],
                              pos_y=info["pos_y"], scale=info["scale"],
                              levels=sorted(levels, key=lambda v: v["id"]), revision=REVISION)
        overview = fetch(f"data/radar_info/{name}.txt").decode("utf-8-sig")
        sites = []
        for site in ("A", "B"):
            values = [re.search(r'"bomb'+site+'_'+axis+r'"\s*"([\d.]+)"', overview) for axis in ("x", "y")]
            if all(values):
                x, y = [float(v.group(1)) for v in values]
                sites.append(dict(name=site, x=info["pos_x"]+x*1024*info["scale"],
                                  y=info["pos_y"]-y*1024*info["scale"],
                                  level="lower" if name == "de_nuke" and site == "B" else "default"))
        manifest[name]["sites"] = sites
        print(name, len(levels), "levels")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
