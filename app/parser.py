import math
from bisect import bisect_right
from .analytics import analyze, identity, side
from .knife_round import detect_knife_rounds
from .equipment_scan import scan_equipment
from .utility import build_utility, EVENTS
from .tactical import CLOCK_PROPS, EVENTS as TACTICAL_EVENTS, clock, build_tactical


def records(df):
    if df is None or len(df) == 0:
        return []
    return [{k: (None if isinstance(v, float) and not math.isfinite(v) else v)
             for k, v in row.items()} for row in df.to_dict("records")]


SAMPLE_RATES = (1, 8, 16, 32, 64)
DEFAULT_SAMPLE_RATE = 16


def parse_demo(path, sample_rate=DEFAULT_SAMPLE_RATE, on_progress=None):
    report = on_progress or (lambda percent, stage: None)
    if type(sample_rate) is not int or sample_rate not in SAMPLE_RATES:
        raise ValueError("Частота снимков должна быть 1, 8, 16, 32 или 64 Гц.")
    from demoparser2 import DemoParser
    parser = DemoParser(str(path))
    report(2, "Чтение заголовка и раундов")
    header = parser.parse_header()
    tickrate = 64  # CS2 simulation tick rate; subtick events are displayed at parser tick precision.
    common = ["is_warmup_period"]
    starts = records(parser.parse_event("round_start", other=common))
    ends = records(parser.parse_event("round_end", other=common))
    official_ticks = sorted(e["tick"] for e in records(parser.parse_event("round_officially_ended")))
    starts = sorted((e for e in starts if not e.get("is_warmup_period")), key=lambda e: e["tick"])
    start_ticks = [e["tick"] for e in starts]
    rounds, used = [], set()
    for e in sorted(ends, key=lambda e: e["tick"]):
        if e.get("is_warmup_period") or side(e.get("winner")) not in ("CT", "T"):
            continue
        idx = bisect_right(start_ticks, e["tick"]) - 1
        if idx < 0 or idx in used:
            continue
        used.add(idx)
        # Kills during the round-end delay still belong to the round that just ended.
        official_idx = bisect_right(official_ticks, e["tick"])
        next_start = start_ticks[idx+1] if idx+1 < len(start_ticks) else None
        official = official_ticks[official_idx] if official_idx < len(official_ticks) else None
        end_tick = int(e["tick"])
        if official is not None and (next_start is None or official <= next_start):
            end_tick = int(official)-1
        elif next_start is not None:
            end_tick = int(next_start)-1
        rounds.append(dict(number=len(rounds)+1, start=start_ticks[idx], end=end_tick, decision_tick=int(e["tick"]),
                           winner=side(e.get("winner")), reason=str(e.get("reason", ""))))
    if not rounds:
        raise ValueError("В demo нет завершённых игровых раундов. Записи разминки и POV могут не поддерживаться.")
    bounds = [r["start"] for r in rounds]

    def round_for(tick):
        idx = bisect_right(bounds, tick)-1
        return rounds[idx]["number"] if idx >= 0 and tick <= rounds[idx]["end"] else None

    report(12, "Извлечение убийств и урона")
    events = {}
    for name in ("player_death", "player_hurt"):
        rows = records(parser.parse_event(name, player=["team_num", "X", "Y", "Z"]))
        events[name] = [dict(e, round=round_for(e["tick"])) for e in rows if round_for(e["tick"]) is not None]
    sample_step = tickrate // sample_rate
    wanted_ticks = [t for r in rounds for t in range(r["start"], r["end"]+1, sample_step)]
    report(25, "Извлечение позиций игроков")
    df = parser.parse_ticks(["X", "Y", "Z", "health", "team_num", "is_alive", "yaw", "pitch", *CLOCK_PROPS], ticks=wanted_ticks)
    report(45, "Обработка снимков позиций")
    grouped = {}
    for e in records(df):
        tick = int(e["tick"])
        rid = round_for(tick)
        team = side(e.get("team_num"))
        if rid is None or team == "?" or e.get("X") is None or e.get("Y") is None:
            continue
        pid = identity(dict(user_steamid=e.get("steamid"), user_name=e.get("name")))
        if not pid:
            continue
        frame = grouped.setdefault(tick, dict(tick=tick, round=rid, players=[], clock=clock(e)))
        frame["players"].append(dict(id=pid, name=e.get("name") or "Unknown", side=team,
            x=round(float(e["X"]), 1), y=round(float(e["Y"]), 1), z=e.get("Z") or 0,
            hp=int(e.get("health") or 0), alive=bool(e.get("is_alive")),
            yaw=e.get("yaw"), pitch=e.get("pitch")))
    frames = sorted(grouped.values(), key=lambda e: e["tick"])
    for previous, current in zip(frames, frames[1:]):
        a, b = previous.get("clock"), current.get("clock")
        if a and b and a["paused"] and b["paused"] and previous["round"] == current["round"] and a["freeze"] == b["freeze"]:
            b["seconds"] = a["seconds"]
    for r in rounds:
        r["player_sides"] = {}
    sides_by_round = {r["number"]: r["player_sides"] for r in rounds}
    for f in frames:
        for p in f["players"]:
            sides_by_round[f["round"]].setdefault(p["id"], p["side"])
    report(60, "Расчёт статистики игроков")
    players, feed = analyze(rounds, events["player_death"], events["player_hurt"], frames, tickrate)
    warnings = [] if frames else ["Парсер не извлёк позиции игроков."]
    teams = {(f["round"], p["id"]): p["side"] for f in frames for p in f["players"]}
    report(68, "Анализ гранат")
    grenades, effects, utility_ok = [], [], False
    try:
        grenade_rows = records(parser.parse_grenades(grenades=False))
        utility_events = {name: records(df) for name, df in parser.parse_events(list(EVENTS), player=["team_num"])}
        grenades, effects = build_utility(grenade_rows, utility_events, rounds, teams, sample_step, tickrate)
        utility_ok = True
    except Exception as exc:
        warnings.append(f"Не удалось извлечь гранаты: {str(exc)[:200]}")
    view_ok = any(p["yaw"] is not None for f in frames for p in f["players"])
    report(78, "Анализ бомбы и стрельбы")
    bombs, bomb_events, shots, tactical_ok = [], [], [], False
    try:
        tactical_events = {name: records(df) for name, df in parser.parse_events(TACTICAL_EVENTS,
                           player=["X", "Y", "Z", "yaw", "pitch", "team_num"])}
        bombs, bomb_events, shots = build_tactical(tactical_events, rounds, header.get("map_name", "unknown"), tickrate, frames)
        tactical_ok = True
    except Exception as exc:
        warnings.append(f"Не удалось извлечь события бомбы и стрельбу: {str(exc)[:200]}")
    result = dict(map=header.get("map_name", "unknown"), tickrate=tickrate,
        sample_rate=sample_rate, sample_seconds=1/sample_rate,
        rounds=rounds, players=players, events=feed, frames=frames, grenades=grenades, utility_effects=effects,
        bombs=bombs, bomb_events=bomb_events, shots=shots,
        capabilities=dict(view_angles=view_ok, grenades=utility_ok, bomb_events=tactical_ok, shots=tactical_ok,
                          round_clock=any(f.get("clock") for f in frames)),
        source="demo", schema_version=4, warnings=warnings)

    report(88, "Проверка ножевого раунда")
    result["knife_scan"] = scan_equipment(path, rounds[0])
    if result["knife_scan"]["status"] == "unknown":
        result["warnings"].append("Не удалось полностью проверить инвентари и оружие на карте. Ножевой раунд не скрывается автоматически.")
    hidden = detect_knife_rounds(result)
    if hidden:
        visible = [r for r in rounds if r["number"] not in hidden]
        result["players_without_knife"], _ = analyze(visible,
            [e for e in events["player_death"] if e["round"] not in hidden],
            [e for e in events["player_hurt"] if e["round"] not in hidden],
            [f for f in frames if f["round"] not in hidden], tickrate)
    return result
