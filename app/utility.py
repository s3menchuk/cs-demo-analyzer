"""Normalize native projectile tracks and event-based grenade lifetimes."""
from bisect import bisect_right
from collections import defaultdict
from math import isfinite
from .analytics import identity, side

EVENTS = ("smokegrenade_detonate", "smokegrenade_expired", "hegrenade_detonate",
          "flashbang_detonate", "inferno_startburn", "inferno_expire", "decoy_started", "decoy_detonate")
PROJECTILES = {"CSmokeGrenadeProjectile": "smoke", "CHEGrenadeProjectile": "he",
               "CFlashbangProjectile": "flash", "CMolotovProjectile": "fire", "CDecoyProjectile": "decoy"}


def coords(row):
    values = [row.get(axis, row.get(axis.upper())) for axis in ("x", "y", "z")]
    if not all(isinstance(v, (float, int)) and isfinite(v) for v in values):
        return None
    return dict(zip(("x", "y", "z"), (round(v, 1) for v in values)))


def build_utility(rows, events, rounds, teams, sample_step=4, tickrate=64):
    starts = [r["start"] for r in rounds]
    def round_for(tick):
        i = bisect_right(starts, tick)-1
        return rounds[i] if i >= 0 and tick <= rounds[i]["end"] else None

    detonation = defaultdict(list)
    for name in ("smokegrenade_detonate", "hegrenade_detonate", "flashbang_detonate"):
        for event in events.get(name, []):
            detonation[str(event.get("entityid"))].append(event)
    grouped = defaultdict(list)
    for row in rows:
        kind = PROJECTILES.get(row.get("grenade_type"))
        point = coords(row)
        tick = int(row["tick"])
        r = round_for(tick)
        if not kind or not point or not r:
            continue
        owner = identity(dict(user_steamid=row.get("steamid"), user_name=row.get("name")))
        entity = str(row.get("grenade_entity_id", row.get("entity_id")))
        grouped[(r["number"], entity, kind, owner, row.get("name"))].append(dict(point, tick=tick))
    tracks = []
    for (rid, entity, kind, owner, name), points in grouped.items():
        # Entity indexes are reused; a gap must start a fresh trajectory.
        segments = []
        for p in sorted({p["tick"]: p for p in points}.values(), key=lambda p:p["tick"]):
            if not segments or p["tick"]-segments[-1][-1]["tick"] > 2:
                segments.append([])
            segments[-1].append(p)
        for segment in segments:
            first, last = segment[0]["tick"], segment[-1]["tick"]
            end_event = next((e for e in sorted(detonation[entity], key=lambda e:e["tick"])
                              if first <= e["tick"] <= last+2 and round_for(e["tick"]) and round_for(e["tick"])["number"] == rid), None)
            if kind == "smoke":
                # Smoke projectile entities remain after detonation; do not call that flight.
                prior = [e for e in detonation[entity] if e["tick"] < first and round_for(e["tick"]) and round_for(e["tick"])["number"] == rid]
                if prior and not end_event:
                    continue
            if end_event:
                segment = [p for p in segment if p["tick"] <= end_event["tick"]]
                end_point = coords(end_event)
                if end_point:
                    segment.append(dict(end_point, tick=int(end_event["tick"])))
            sampled = [segment[0]]
            for p in segment[1:-1]:
                if p["tick"]-sampled[-1]["tick"] >= sample_step:
                    sampled.append(p)
            if segment[-1]["tick"] != sampled[-1]["tick"]:
                sampled.append(segment[-1])
            tracks.append(dict(id=f"{rid}:{entity}:{first}", round=rid, kind=kind,
                owner_id=owner, owner_name=name or "Unknown", side=teams.get((rid, owner), "?"),
                start=sampled[0]["tick"], end=sampled[-1]["tick"], points=sampled))
    effects = []
    definitions = [("smokegrenade_detonate", "smokegrenade_expired", "smoke"),
                   ("inferno_startburn", "inferno_expire", "fire"),
                   ("decoy_started", "decoy_detonate", "decoy"),
                   ("hegrenade_detonate", None, "he"), ("flashbang_detonate", None, "flash")]
    for begin_name, end_name, kind in definitions:
        for e in events.get(begin_name, []):
            r, point = round_for(e["tick"]), coords(e)
            if not r or not point:
                continue
            expiry = next((end for end in sorted(events.get(end_name, []), key=lambda x:x["tick"])
                           if str(end.get("entityid")) == str(e.get("entityid")) and e["tick"] <= end["tick"] <= r["end"]), None)
            end = expiry["tick"] if expiry else (r["end"] if end_name else e["tick"]+int(.8*tickrate))
            owner = identity(e)
            effects.append(dict(point, id=f"{kind}:{e.get('entityid')}:{e['tick']}", round=r["number"],
                kind=kind, start=int(e["tick"]), end=min(int(end), r["end"]),
                owner_id=owner, owner_name=e.get("user_name") or "Unknown",
                side=side(e.get("user_team_num")) if e.get("user_team_num") is not None else teams.get((r["number"], owner), "?"),
                end_confirmed=expiry is not None or end_name is None))
    return sorted(tracks, key=lambda g:g["start"]), sorted(effects, key=lambda g:g["start"])
