"""Conservative, provider-independent detection and reversible round visibility."""


def detect_knife_rounds(match):
    rounds = match.get("rounds", [])
    if len(rounds) < 2 or match.get("source") == "synthetic":
        return []
    scan = match.get("knife_scan", {})
    first = rounds[0]
    if (scan.get("method") == "equipment-v1" and scan.get("status") == "knife"
            and scan.get("round") == first["number"]
            and scan.get("start") == first["start"]
            and scan.get("end") == first.get("decision_tick", first["end"])
            and scan.get("checked_frames", 0) > 0):
        return [first["number"]]
    return []


def visible_match(match, include_knife=False):
    hidden = detect_knife_rounds(match)
    result = dict(match, knife_rounds=hidden, include_knife=include_knife)
    result.pop("players_without_knife", None)
    numbered = []
    competitive_number = 0
    for r in match.get("rounds", []):
        knife = r["number"] in hidden
        if not knife:
            competitive_number += 1
        numbered.append(dict(r, display_number=None if knife else competitive_number, is_knife=knife))
    result["rounds"] = numbered
    if match.get("source") == "demo" and "knife_scan" not in match:
        result["warnings"] = [*match.get("warnings", []),
            "В этой записи нет проверки инвентарей и оружия на карте. Загрузите .dem повторно для распознавания ножевого раунда по составу оружия."]
    if not hidden or include_knife:
        return result
    result["rounds"] = [r for r in numbered if not r["is_knife"]]
    for field in ("events", "frames", "grenades", "utility_effects", "bombs", "bomb_events", "shots"):
        if field in match:
            result[field] = [e for e in match[field] if e["round"] not in hidden]
    if "players_without_knife" in match:
        result["players"] = match["players_without_knife"]
    else:
        # Old payloads did not retain per-round damage/assists/KAST inputs.
        result["warnings"] = [*match.get("warnings", []),
            "Ножевой раунд скрыт в просмотре и анализе событий. Общие ADR, KAST и таблица игроков старой записи включают его; загрузите .dem повторно для полного пересчёта."]
    return result
