"""Aggregate raw counters, never average K/D, ADR or HS percentages."""
from .maps import level_for
from .spatial import balance_zones

COUNTERS = ("kills", "deaths", "assists", "headshots", "damage", "rounds", "opening_kills", "opening_deaths")


def metrics(players):
    result = {key: sum(p.get(key, 0) for p in players) for key in COUNTERS}
    result.update(kd=round(result["kills"]/max(result["deaths"],1),2),
                  adr=round(result["damage"]/max(result["rounds"],1),1),
                  hs=round(100*result["headshots"]/max(result["kills"],1),1))
    return result


def analyze_maps(entries, player_id=None, cell_size=256):
    groups = {}
    skipped = 0
    for mid,name,match in entries:
        players = [p for p in match["players"] if not player_id or p["id"] == player_id]
        if not players:
            skipped += 1
            continue
        map_name = match["map"]
        g = groups.setdefault(map_name, dict(map=map_name, matches=[], rounds=0, ct_wins=0, t_wins=0,
            players={}, kill_points=[], death_points=[], spatial_matches=0, warnings=[]))
        rounds = [r for r in match["rounds"] if not r.get("is_knife")]
        g["matches"].append(dict(id=mid,name=name,rounds=len(rounds)))
        g["rounds"] += len(rounds)
        g["ct_wins"] += sum(r.get("winner")=="CT" for r in rounds)
        g["t_wins"] += sum(r.get("winner")=="T" for r in rounds)
        g["warnings"].extend(match.get("warnings", []))
        for p in players:
            target = g["players"].setdefault(p["id"],dict(id=p["id"],name=p["name"],matches=0,**{k:0 for k in COUNTERS}))
            target["matches"] += 1
            for k in COUNTERS: target[k] += p.get(k,0)
        if match.get("schema_version",1) < 2:
            continue
        g["spatial_matches"] += 1
        for e in match.get("events", []):
            for kind,role in (("kill","attacker"),("death","victim")):
                if kind=="kill" and not e.get("enemy"): continue
                if player_id and e.get(role+"_id") != player_id: continue
                point = e.get(role+"_position")
                if point:
                    g[kind+"_points"].append(dict(point,level=level_for(map_name,point.get("z"))))
    maps = []
    for g in groups.values():
        players = [dict(p,**metrics([p])) for p in g["players"].values()]
        players.sort(key=lambda p:(-p["kills"],-p["damage"],p["id"]))
        maps.append(dict(map=g["map"],matches=g["matches"],matches_count=len(g["matches"]),
            rounds=g["rounds"],ct_wins=g["ct_wins"],t_wins=g["t_wins"],players=players,
            totals=metrics(players),balance_zones=balance_zones(g["kill_points"],g["death_points"],cell_size),
            kills_with_position=len(g["kill_points"]),deaths_with_position=len(g["death_points"]),
            spatial_matches=g["spatial_matches"],warnings=list(dict.fromkeys(g["warnings"]))))
    return dict(player_id=player_id,cell_size=cell_size,matches_count=sum(m["matches_count"] for m in maps),
                skipped_matches=skipped,maps=sorted(maps,key=lambda m:(-m["matches_count"],m["map"])))
