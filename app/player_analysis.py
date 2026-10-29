"""Event-based player analysis. Never substitute sampled movement for kill coordinates."""
from collections import Counter, defaultdict
from math import floor
from .maps import level_for
from .spatial import balance_zones


def analyze_player(match, pid, round_number=None, side_name=None, cell_size=256):
    player = next((p for p in match["players"] if p["id"] == pid), None)
    if player is None:
        return None
    available = match.get("schema_version", 1) >= 2
    kills_per_round = Counter(e["round"] for e in match["events"] if e.get("enemy") and e.get("attacker_id") == pid
                              and (not side_name or e["side"] == side_name))
    # Keep the full match series when a single round is selected for the spatial analysis.
    round_kills = [dict(number=r["number"], kills=kills_per_round[r["number"]]) for r in match["rounds"]] if available else []
    selected = [e for e in match["events"] if round_number is None or e["round"] == round_number]
    kills = [e for e in selected if e.get("enemy") and e.get("attacker_id") == pid
             and (not side_name or e["side"] == side_name)]
    deaths = [e for e in selected if e.get("victim_id") == pid
              and (not side_name or e.get("victim_side") == side_name)]

    def locations(events, field):
        return [dict(e[field], tick=e["tick"], round=e["round"], weapon=e["weapon"],
                     opponent=e["victim"] if field == "attacker_position" else e["attacker"],
                     headshot=e["headshot"], level=level_for(match["map"], e[field].get("z")))
                for e in events if e.get(field)]

    def zones(points):
        cells = defaultdict(list)
        for point in points:
            cells[(floor(point["x"]/cell_size), floor(point["y"]/cell_size), point["level"])].append(point)
        result = []
        for (x, y, level), items in cells.items():
            result.append(dict(x=sum(p["x"] for p in items)/len(items),
                               y=sum(p["y"] for p in items)/len(items), level=level,
                               min_x=x*cell_size, min_y=y*cell_size, size=cell_size,
                               count=len(items), share=round(len(items)*100/max(len(points), 1), 1),
                               rounds=sorted({p["round"] for p in items})))
        return sorted(result, key=lambda v: (-v["count"], v["level"], v["min_x"], v["min_y"]))

    kill_points, death_points = locations(kills, "attacker_position"), locations(deaths, "victim_position")
    round_stats = [dict(number=r["number"], kills=sum(e["round"] == r["number"] for e in kills),
                        deaths=sum(e["round"] == r["number"] for e in deaths))
                   for r in match["rounds"] if round_number is None or r["number"] == round_number]
    weapons = Counter(e["weapon"] for e in kills)
    return dict(player=player, available=available, round_number=round_number, side=side_name,
                cell_size=cell_size, kills=len(kills), deaths=len(deaths),
                kills_with_position=len(kill_points), deaths_with_position=len(death_points),
                kill_points=kill_points, death_points=death_points,
                kill_zones=zones(kill_points), death_zones=zones(death_points),
                balance_zones=balance_zones(kill_points, death_points, cell_size),
                weapons=[dict(name=name, kills=count) for name, count in weapons.most_common()],
                rounds=round_stats,
                round_kills=round_kills,
                warning=None if available else "Этот матч сохранён старой версией без координат событий. Загрузите .dem повторно для анализа зон убийств и смертей.")
