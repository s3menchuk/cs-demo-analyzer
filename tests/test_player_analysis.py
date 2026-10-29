from app.analytics import analyze
from app.player_analysis import analyze_player
from app.maps import catalog, level_for


def match():
    # Nearby kills from one spot, victims far away. One kill occurs on a lower floor.
    events=[]
    for tick,x,z,side,rid in [(1,-100,0,'CT',1),(2,-110,0,'CT',1),(3,-100,-600,'T',2)]:
        events.append(dict(tick=tick,round=rid,attacker='A',attacker_id='1',victim='B',victim_id='2',
            side=side,victim_side='T' if side=='CT' else 'CT',enemy=True,weapon='ak47',headshot=False,
            attacker_position=dict(x=x,y=100,z=z),victim_position=dict(x=2000,y=2000,z=z)))
    events.append(dict(tick=4,round=2,attacker='B',attacker_id='2',victim='A',victim_id='1',
        side='CT',victim_side='T',enemy=True,weapon='awp',headshot=True,
        attacker_position=dict(x=500,y=500,z=0),victim_position=dict(x=-50,y=120,z=0)))
    return dict(map='de_nuke',schema_version=2,players=[dict(id='1',name='A'),dict(id='2',name='B')],
                rounds=[dict(number=1),dict(number=2)],events=events)


def test_killer_origin_and_death_location_are_distinct():
    report=analyze_player(match(),'1')
    assert report['kills']==3 and report['deaths']==1
    assert report['kill_points'][0]['x']==-100
    assert report['death_points'][0]['x']==-50
    assert report['kill_zones'][0]['count']==2
    assert report['kill_zones'][0]['min_x']==-256  # Correct floor for negative world coordinates.
    assert report['kill_zones'][0]['min_y']==0
    assert report['kill_zones'][0]['rounds']==[1]
    assert report['kill_zones'][0]['share']==66.7
    assert len(report['kill_zones'])==2  # Floors must not be merged.
    assert report['kill_points'][-1]['level']=='lower'


def test_filters_apply_to_selected_players_side_and_round():
    report=analyze_player(match(),'1',round_number=2,side_name='T')
    assert report['kills']==1 and report['deaths']==1
    assert report['weapons']==[dict(name='ak47',kills=1)]
    assert report['rounds']==[dict(number=2,kills=1,deaths=1)]
    report=analyze_player(match(),'1',side_name='CT')
    assert report['kills']==2 and report['deaths']==0
    assert analyze_player(match(),'missing') is None


def test_round_kill_series_includes_zeroes_and_survives_round_selection():
    data=match()
    data['rounds'].append(dict(number=3))
    report=analyze_player(data,'1',round_number=2)
    assert report['kills']==1
    assert report['round_kills']==[dict(number=1,kills=2),dict(number=2,kills=1),dict(number=3,kills=0)]
    ct=analyze_player(data,'1',side_name='CT')
    assert ct['round_kills']==[dict(number=1,kills=2),dict(number=2,kills=0),dict(number=3,kills=0)]
    assert sum(r['kills'] for r in ct['round_kills'])==ct['kills']
    # Missing coordinates must not remove kills from the round breakdown.
    data['events'][0]['attacker_position']=None
    assert analyze_player(data,'1')['round_kills'][0]['kills']==2
    data.pop('schema_version')
    assert analyze_player(data,'1')['round_kills']==[]


def test_missing_coordinates_not_replaced_by_snapshots():
    data=match()
    data['events'][0]['attacker_position']=None
    report=analyze_player(data,'1')
    assert report['kills']==3 and report['kills_with_position']==2
    assert len(report['kill_points'])==2
    data.pop('schema_version')
    report=analyze_player(data,'1')
    assert report['available'] is False and 'повторно' in report['warning']


def test_teamkill_and_world_deaths_excluded_from_kills_but_in_deaths():
    data=match()
    data['events'][0]['enemy']=False
    data['events'][3]['attacker_id']=None
    report=analyze_player(data,'1')
    assert report['kills']==2 and report['deaths']==1


def test_analyzer_preserves_event_coordinates_and_ids():
    death=dict(tick=10,round=1,attacker_steamid='76561198000000001',user_steamid='2',
        attacker_name='a',user_name='b',attacker_team_num=3,user_team_num=2,
        attacker_X=0,attacker_Y=-10,attacker_Z=20,user_X=100,user_Y=200,user_Z=-600)
    _,events=analyze([dict(number=1,start=0,end=100)],[death],[],[])
    assert events[0]['attacker_id']=='76561198000000001'
    assert events[0]['attacker_position']==dict(x=0,y=-10,z=20)
    assert events[0]['victim_position']==dict(x=100,y=200,z=-600)


def test_bundled_maps_calibration_and_assets():
    from pathlib import Path
    assert len(catalog())==9
    for meta in catalog().values():
        assert meta['scale']>0
        assert len({l['id'] for l in meta['levels']})==len(meta['levels'])
        for level in meta['levels']:
            path=Path(__file__).resolve().parents[1]/level['image'].lstrip('/')
            assert path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert level_for('de_nuke',-496)=='lower'
    assert level_for('de_nuke',-495)=='default'
    assert catalog()['de_mirage']['pos_x']==-3230


def test_balance_zones_respect_round_side_and_killer_coordinates():
    report=analyze_player(match(),'1')
    assert sum(z['delta'] for z in report['balance_zones'])==2
    assert sum(z['kills'] for z in report['balance_zones'])==3
    assert sum(z['deaths'] for z in report['balance_zones'])==1
    filtered=analyze_player(match(),'1',round_number=1,side_name='CT')
    assert len(filtered['balance_zones'])==1
    assert filtered['balance_zones'][0]['delta']==2
