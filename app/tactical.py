"""Round clock snapshots, bomb sessions, and firearm events."""
from bisect import bisect_right
from math import isfinite, hypot
from statistics import median
from .analytics import identity, side, position
from .maps import catalog, level_for

RULES = "CCSGameRulesProxy.CCSGameRules."
CLOCK_PROPS = ["game_time", "round_start_time", "is_freeze_period", RULES+"m_iRoundTime",
               RULES+"m_bGamePaused", RULES+"m_bServerPaused"]
EVENTS = ["round_freeze_end", "server_cvar", "bomb_beginplant", "bomb_abortplant", "bomb_planted",
          "bomb_begindefuse", "bomb_abortdefuse", "bomb_defused", "bomb_exploded", "weapon_fire"]


def number(value):
    return float(value) if isinstance(value, (int, float)) and isfinite(value) else None


def clock(row):
    now, start, duration = (number(row.get(k)) for k in ("game_time", "round_start_time", RULES+"m_iRoundTime"))
    if now is None or start is None or duration is None:
        return None
    freeze = bool(row.get("is_freeze_period"))
    return dict(seconds=max(0, start-now if freeze else duration-max(0, now-start)),
                freeze=freeze, paused=bool(row.get(RULES+"m_bGamePaused") or row.get(RULES+"m_bServerPaused")),
                duration=duration, game_time=now, round_start_time=start)


def site_label(map_name, point):
    sites = catalog().get(map_name, {}).get("sites", [])
    if not sites or not point:
        return None
    same_level = [s for s in sites if s.get("level", "default") == level_for(map_name, point.get("z"))]
    candidates = same_level or sites
    return min(candidates, key=lambda s:hypot(point["x"]-s["x"], point["y"]-s["y"]))["name"]


def build_tactical(events, rounds, map_name, tickrate=64, frames=None):
    starts = [r["start"] for r in rounds]
    frames = frames or []
    ticks = [f["tick"] for f in frames]
    def game_time_at(tick):
        i = bisect_right(ticks, tick)-1
        if i < 0 or not frames[i].get("clock"):
            return None
        a = frames[i]
        if a["clock"]["paused"]:
            return a["clock"]["game_time"]
        if i+1 < len(frames) and frames[i+1]["round"] == a["round"] and frames[i+1].get("clock"):
            b = frames[i+1]
            ratio = (tick-a["tick"])/(b["tick"]-a["tick"])
            return a["clock"]["game_time"]+(b["clock"]["game_time"]-a["clock"]["game_time"])*ratio
        return a["clock"]["game_time"]+(tick-a["tick"])/tickrate
    def round_for(tick):
        i = bisect_right(starts, tick)-1
        return rounds[i] if i >= 0 and tick <= rounds[i]["end"] else None
    bomb_events, shots, bombs = [], [], []
    for e in events.get("round_freeze_end", []):
        r = round_for(e["tick"])
        if r:
            r["freeze_end"] = int(e["tick"])
    for name in EVENTS:
        if not name.startswith("bomb_"):
            continue
        for e in events.get(name, []):
            r = round_for(e["tick"])
            if not r:
                continue
            point = position(e, "user")
            bomb_events.append(dict(type=name, tick=int(e["tick"]), round=r["number"],
                actor_id=identity(e), actor=e.get("user_name") or "Unknown", position=point,
                raw_site=e.get("site"), site=site_label(map_name, point) if e.get("site") is not None else None,
                has_kit=bool(e.get("haskit"))))
    bomb_events.sort(key=lambda e:(e["tick"], e["type"]))
    cvars = []
    for e in events.get("server_cvar", []):
        if e.get("name") != "mp_c4timer":
            continue
        try:
            value = float(e["value"])
        except (TypeError, ValueError):
            continue
        if isfinite(value) and 0 < value <= 3600:
            cvars.append((e["tick"], value))
    cvars.sort(key=lambda e:e[0])
    for r in rounds:
        selected = [e for e in bomb_events if e["round"] == r["number"]]
        for plant in [e for e in selected if e["type"] == "bomb_planted"]:
            resolved = next((e for e in selected if e["type"] in ("bomb_defused", "bomb_exploded") and e["tick"] >= plant["tick"]), None)
            settings = [value for tick, value in cvars if tick <= plant["tick"]]
            fuse = settings[-1] if settings else None
            source = "server_cvar" if fuse is not None else "unknown"
            if resolved and resolved["type"] == "bomb_exploded":
                fuse = (resolved["tick"]-plant["tick"])/tickrate
                plant_time, exploded_time = game_time_at(plant["tick"]), game_time_at(resolved["tick"])
                if plant_time is not None and exploded_time is not None:
                    fuse = max(0, exploded_time-plant_time)
                source = "recorded_explosion"
            bombs.append(dict(round=r["number"], planted_tick=plant["tick"], position=plant["position"],
                position_source="planter_position", site=plant["site"], raw_site=plant["raw_site"],
                planter=plant["actor"], planter_id=plant["actor_id"],
                planted_game_time=game_time_at(plant["tick"]),
                resolved_tick=resolved["tick"] if resolved else None,
                outcome=resolved["type"].removeprefix("bomb_") if resolved else None,
                fuse_seconds=fuse, fuse_source=source))
    measured = [b["fuse_seconds"] for b in bombs if b["fuse_source"] == "recorded_explosion"]
    # Only infer from other rounds when the observed durations agree to one simulation tick.
    if measured and max(measured)-min(measured) <= 1/tickrate:
        for b in bombs:
            if b["fuse_seconds"] is None:
                b.update(fuse_seconds=median(measured), fuse_source="measured_other_rounds")
    excluded = {"c4", "hegrenade", "smokegrenade", "flashbang", "molotov", "incgrenade", "decoy"}
    for i, e in enumerate(events.get("weapon_fire", [])):
        r = round_for(e["tick"])
        weapon = str(e.get("weapon") or "").removeprefix("weapon_")
        if not r or not weapon or weapon in excluded or "knife" in weapon or "bayonet" in weapon:
            continue
        shots.append(dict(id=f"shot:{e['tick']}:{i}", tick=int(e["tick"]), round=r["number"],
            shooter_id=identity(e), shooter=e.get("user_name") or "Unknown", side=side(e.get("user_team_num")),
            weapon=weapon, silenced=bool(e.get("silenced")), position=position(e, "user"),
            yaw=number(e.get("user_yaw")), pitch=number(e.get("user_pitch"))))
    return bombs, bomb_events, sorted(shots, key=lambda e:e["tick"])
