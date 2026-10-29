"""Shared world-aligned K-D cells; floors and maps must stay separate."""
from collections import defaultdict
from math import floor, isfinite


def balance_zones(kills, deaths, cell_size=256):
    cells = defaultdict(lambda: dict(kills=0, deaths=0))
    for kind, points in (("kills", kills), ("deaths", deaths)):
        for p in points:
            if not all(isinstance(p.get(a), (int, float)) and isfinite(p[a]) for a in ("x", "y")):
                continue
            key = (floor(p["x"] / cell_size), floor(p["y"] / cell_size), p.get("level", "default"))
            cells[key][kind] += 1
    return [dict(min_x=x*cell_size, min_y=y*cell_size, size=cell_size, level=level,
                 kills=v["kills"], deaths=v["deaths"], delta=v["kills"]-v["deaths"])
            for (x,y,level),v in sorted(cells.items())]
