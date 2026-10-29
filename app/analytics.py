"""Pure match aggregation. IDs are strings to preserve SteamID64 in JavaScript."""
from collections import defaultdict
import math


def position(event, prefix):
    coordinates = [event.get(f"{prefix}_{axis}") for axis in ("X", "Y", "Z")]
    if any(v is None or not isinstance(v, (int, float)) or not math.isfinite(v) for v in coordinates[:2]):
        return None
    return dict(x=round(coordinates[0], 1), y=round(coordinates[1], 1),
                z=round(coordinates[2], 1) if isinstance(coordinates[2], (int, float)) and math.isfinite(coordinates[2]) else None)


def side(value):
    return {2: "T", 3: "CT", "2": "T", "3": "CT", "TERRORIST": "T", "T": "T", "CT": "CT"}.get(value, "?")


def identity(row, prefix="user"):
    value = row.get(f"{prefix}_steamid")
    if value and str(value) != "0":
        return str(value)
    name = row.get(f"{prefix}_name")
    return f"bot:{name}" if name else None


def analyze(rounds, deaths, hurts, frames, tickrate=64):
    players = {}
    participation = defaultdict(set)
    # Snapshots establish participation and changing sides even for zero-kill players.
    for f in frames:
        for p in f["players"]:
            pid = p["id"]
            if p["side"] not in ("CT", "T"):
                continue
            players.setdefault(pid, dict(id=pid, name=p["name"], side=p["side"], kills=0,
                deaths=0, assists=0, headshots=0, damage=0, opening_kills=0, opening_deaths=0))
            participation[pid].add(f["round"])

    def register(e, prefix):
        pid = identity(e, prefix)
        if pid:
            players.setdefault(pid, dict(id=pid, name=e.get(f"{prefix}_name", "Unknown"),
                side=side(e.get(f"{prefix}_team_num")), kills=0, deaths=0, assists=0,
                headshots=0, damage=0, opening_kills=0, opening_deaths=0))
            participation[pid].add(e["round"])
        return pid

    for e in deaths + hurts:
        for role in ("user", "attacker", "assister"):
            register(e, role)
    valid = {r["number"] for r in rounds}
    deaths = sorted((e for e in deaths if e["round"] in valid), key=lambda e: e["tick"])
    kills_by_round = defaultdict(list)
    kast = defaultdict(set)
    dead = defaultdict(set)
    feed = []
    for e in deaths:
        rid = e["round"]
        a, v, assist = (identity(e, role) for role in ("attacker", "user", "assister"))
        if v in players:
            players[v]["deaths"] += 1
            dead[rid].add(v)
        enemy = a in players and a != v and side(e.get("attacker_team_num")) != side(e.get("user_team_num")) and side(e.get("attacker_team_num")) != "?"
        if enemy:
            players[a]["kills"] += 1
            players[a]["headshots"] += int(bool(e.get("headshot")))
            kast[a].add(rid)
            if not kills_by_round[rid]:
                players[a]["opening_kills"] += 1
                if v in players:
                    players[v]["opening_deaths"] += 1
            # A victim is traded only if a teammate kills their killer within five seconds.
            for old in kills_by_round[rid]:
                if old["attacker"] == v and old["victim_side"] == side(e.get("attacker_team_num")) and e["tick"] - old["tick"] <= 5 * tickrate:
                    kast[old["victim"]].add(rid)
            kills_by_round[rid].append(dict(attacker=a, victim=v, tick=e["tick"], victim_side=side(e.get("user_team_num"))))
            if assist in players and assist not in (a, v):
                players[assist]["assists"] += 1
                kast[assist].add(rid)
        feed.append(dict(tick=e["tick"], round=rid, attacker=players.get(a, {}).get("name", "Мир"),
            victim=players.get(v, {}).get("name", "Unknown"), weapon=e.get("weapon", "?"),
            headshot=bool(e.get("headshot")), side=side(e.get("attacker_team_num")),
            attacker_id=a, victim_id=v, victim_side=side(e.get("user_team_num")), enemy=bool(enemy),
            attacker_position=position(e, "attacker"), victim_position=position(e, "user")))
    remaining = defaultdict(lambda: 100)
    for e in sorted(hurts, key=lambda e: e["tick"]):
        a, v = identity(e, "attacker"), identity(e)
        key = (e["round"], v)
        damage = min(max(0, int(e.get("dmg_health") or 0)), remaining[key])
        remaining[key] -= damage
        if a in players and a != v and side(e.get("attacker_team_num")) in ("CT", "T") and side(e.get("attacker_team_num")) != side(e.get("user_team_num")):
            players[a]["damage"] += damage
    for pid, p in players.items():
        played = participation[pid] & valid
        for rid in played:
            if pid not in dead[rid]:
                kast[pid].add(rid)
        p.update(rounds=len(played), kd=round(p["kills"] / max(p["deaths"], 1), 2),
            adr=round(p["damage"] / max(len(played), 1), 1),
            hs=round(100 * p["headshots"] / max(p["kills"], 1), 1),
            kast=round(100 * len(kast[pid] & played) / max(len(played), 1), 1))
    for r in rounds:
        r["kills"] = len(kills_by_round[r["number"]])
    return sorted(players.values(), key=lambda p: (-p["kills"], -p["damage"])), feed
