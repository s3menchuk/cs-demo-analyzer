from copy import deepcopy
import pytest
from app.knife_round import detect_knife_rounds, visible_match


def fixture():
    return dict(source="demo", knife_scan=dict(method="equipment-v1",status="knife",round=1,start=1,end=100,checked_frames=80), rounds=[dict(number=1,start=1,end=200,decision_tick=100),
                                      dict(number=2,start=201,end=400)],
        events=[dict(round=1,tick=10+i,weapon=w,enemy=True,victim_id=str(i))
                for i,w in enumerate(["knife", "knife_t", "knife_flip", "bayonet", "weapon_knife_karambit"])],
        shots=[], bomb_events=[], players=[dict(id="p",kills=5)], warnings=[])


@pytest.mark.parametrize("status", ["not_knife", "unknown", None])
def test_no_event_heuristic_when_equipment_does_not_confirm(status):
    m=fixture()
    if status is None: m.pop("knife_scan")
    else: m["knife_scan"]["status"]=status
    # Five knife kills alone must never hide an unverified round.
    assert detect_knife_rounds(m)==[]


def test_equipment_rule_needs_no_kills_and_allows_falling():
    m=fixture()
    m["events"]=[]
    assert detect_knife_rounds(m)==[1]
    m["events"]=[dict(round=1,tick=20,weapon="world",enemy=False)]
    assert detect_knife_rounds(m)==[1]


@pytest.mark.parametrize("field,value", [("method","old-heuristic"),("round",2),
    ("start",99),("end",200),("checked_frames",0)])
def test_incomplete_or_mismatched_proof_cannot_hide_round(field,value):
    m=fixture();m["knife_scan"][field]=value
    assert detect_knife_rounds(m)==[]


def test_view_is_reversible_without_changing_storage_and_filters_all_events():
    m=fixture(); m["players_without_knife"]=[dict(id="p",kills=0)]
    for field in ("frames", "grenades", "utility_effects", "bombs"):
        m[field]=[dict(round=1),dict(round=2)]
    original=deepcopy(m)
    view=visible_match(m)
    assert [r["number"] for r in view["rounds"]]==[2]
    assert view["rounds"][0]["display_number"]==1
    assert visible_match(m,True)["rounds"][0]["display_number"] is None
    assert visible_match(m,True)["rounds"][0]["is_knife"] is True
    assert visible_match(m,True)["rounds"][1]["display_number"]==1
    assert view["events"]==[] and view["players"][0]["kills"]==0
    assert all(e["round"]==2 for e in view["frames"])
    assert "players_without_knife" not in view
    assert m==original
    assert len(visible_match(m,True)["rounds"])==2
    del m["players_without_knife"]
    assert "ADR" in visible_match(m)["warnings"][0]
