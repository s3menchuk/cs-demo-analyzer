from copy import deepcopy
from app.map_analysis import analyze_maps
from app.spatial import balance_zones


def game(map_name="de_nuke",kills=10,deaths=1,damage=1000,rounds=10):
    return dict(map=map_name,schema_version=4,rounds=[dict(number=i+1,winner="CT") for i in range(rounds)],
        players=[dict(id="1",name="A",kills=kills,deaths=deaths,assists=2,headshots=2,damage=damage,rounds=rounds)],
        events=[dict(round=1,tick=10,enemy=True,attacker_id="1",victim_id="2",
            attacker_position=dict(x=-10,y=0,z=0),victim_position=dict(x=10,y=0,z=-600))],warnings=[])


def test_weighted_metrics_grouping_and_identity():
    one=game();two=game(kills=2,deaths=4,damage=100,rounds=2);two["players"][0]["name"]="Renamed"
    report=analyze_maps([("1","a",one),("2","b",two),("3","c",game("de_dust2"))])
    assert report["matches_count"]==3 and len(report["maps"])==2
    m=report["maps"][0]
    assert m["map"]=="de_nuke" and m["rounds"]==12 and m["ct_wins"]==12
    assert m["totals"]["kd"]==2.4 and m["totals"]["adr"]==91.7
    assert len(m["players"])==1 and m["players"][0]["matches"]==2
    assert m["totals"]["hs"]==33.3
    assert m["kills_with_position"]==2 and m["deaths_with_position"]==2
    assert {z["level"] for z in m["balance_zones"]}=={"default","lower"}


def test_player_filter_uses_shooter_origin_and_own_death_and_skips_other_games():
    one=game();two=game();two["players"][0]["id"]="other"
    report=analyze_maps([("a","one",one),("b","two",two)],"1")
    assert report["matches_count"]==1 and report["skipped_matches"]==1
    m=report["maps"][0]
    assert m["kills_with_position"]==1 and m["deaths_with_position"]==0
    assert m["balance_zones"][0]["min_x"]==-256 and m["balance_zones"][0]["delta"]==1


def test_grid_keeps_neutral_cells_and_does_not_merge_floors_or_negative_coordinates():
    p=dict(x=-1,y=-1,level="upper")
    cells=balance_zones([p,p,dict(p,level="lower")],[p,dict(x=1,y=1,level="upper")],256)
    assert [(c["min_x"],c["min_y"],c["level"],c["delta"]) for c in cells]==[
        (-256,-256,"lower",1),(-256,-256,"upper",1),(0,0,"upper",-1)]
    assert balance_zones([p],[p])[0]["delta"]==0
    assert balance_zones([dict(x=float("nan"),y=0)],[])==[]


def test_old_records_and_missing_coordinates_are_not_fabricated():
    one=game();one["schema_version"]=1;one["warnings"]=["Old record"]
    two=game();two["events"][0]["attacker_position"]=None
    original=deepcopy(one)
    report=analyze_maps([("a","old",one),("b","new",two)])
    m=report["maps"][0]
    assert m["spatial_matches"]==1 and m["kills_with_position"]==0
    assert m["warnings"]==["Old record"] and one==original
    assert analyze_maps([],"missing")["maps"]==[]
