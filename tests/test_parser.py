import os
import pytest
from app.parser import parse_demo


@pytest.fixture(autouse=True)
def fake_equipment_scanner(monkeypatch):
    monkeypatch.setattr("app.parser.scan_equipment", lambda path, first:
        dict(method="equipment-v1",status="unknown",reason="test_no_equipment"))


@pytest.mark.parametrize('sample_rate', [1, 8, 16, 32, 64])
def test_post_round_kill_is_assigned_before_next_start(monkeypatch, sample_rate):
    import pandas as pd
    import demoparser2

    wanted_ticks=[]

    class Parser:
        def __init__(self, path):
            pass

        def parse_header(self):
            return {'map_name':'test'}

        def parse_event(self, name, **kwargs):
            return pd.DataFrame({
                'round_start':[{'tick':0,'is_warmup_period':True},{'tick':100,'is_warmup_period':False},{'tick':250,'is_warmup_period':False}],
                'round_end':[{'tick':200,'winner':3},{'tick':400,'winner':2}],
                'round_officially_ended':[{'tick':250}],
                'player_death':[{'tick':240,'attacker_steamid':'1','user_steamid':'2','attacker_name':'a','user_name':'b','attacker_team_num':3,'user_team_num':2}],
                'player_hurt':[],
            }[name])

        def parse_ticks(self, props, **kwargs):
            wanted_ticks.extend(kwargs['ticks'])
            return pd.DataFrame([dict(tick=100,steamid='1',name='a',team_num=3,X=0,Y=0,Z=0,health=100,is_alive=True)])

        def parse_grenades(self, **kwargs):
            return []

        def parse_events(self, *args, **kwargs):
            return []

    monkeypatch.setattr(demoparser2,'DemoParser',Parser)
    progress=[]
    result=parse_demo('test.dem', sample_rate=sample_rate,
                      on_progress=lambda percent, stage: progress.append((percent, stage)))
    assert [percent for percent, _ in progress] == [2, 12, 25, 45, 60, 68, 78, 88]
    assert all(stage for _, stage in progress)
    assert result['rounds'][0]['end']==249
    assert result['events'][0]['round']==1
    assert result['players'][0]['kills']==1
    assert result['sample_rate']==sample_rate
    assert result['sample_seconds']==1/sample_rate
    step=64//sample_rate
    assert wanted_ticks==list(range(100,250,step))+list(range(250,401,step))


@pytest.mark.parametrize('sample_rate', [0, 2, 7, 15, 65, True, None, '16'])
def test_invalid_sampling_rejected_before_file_open(sample_rate):
    with pytest.raises(ValueError, match='Частота'):
        parse_demo('missing.dem', sample_rate=sample_rate)


@pytest.mark.skipif(not os.environ.get('CS2_TEST_DEMO'),reason='Set CS2_TEST_DEMO to a real demo path')
def test_real_demo(monkeypatch):
    from app.equipment_scan import scan_equipment
    monkeypatch.setattr("app.parser.scan_equipment", scan_equipment)
    result=parse_demo(os.environ['CS2_TEST_DEMO'])
    assert result['source']=='demo'
    assert result["knife_scan"]["status"] == "not_knife"
    assert result['rounds'] and result['frames'] and result['players']
    assert all(p['side'] in ('CT','T') for f in result['frames'] for p in f['players'])
    assert all(isinstance(p['id'],str) for p in result['players'])
    assert all(0<=p['kast']<=100 for p in result['players'])
    assert result['schema_version']==4
    assert result['capabilities']==dict(view_angles=True,grenades=True,bomb_events=True,shots=True,round_clock=True)
    assert result['bombs'] and result['shots']
    assert result['frames'][0]['clock']['duration']>0
    assert result['grenades'] and result['utility_effects']
    assert any(p['yaw'] is not None for f in result['frames'] for p in f['players'])
    assert all(e['victim_position'] is not None for e in result['events'])
    assert any(e['attacker_position'] for e in result['events'])
    assert result['sample_rate']==16 and result['sample_seconds']==1/16
    assert any(b['tick']-a['tick']==4 for a,b in zip(result['frames'],result['frames'][1:]) if a['round']==b['round'])


def test_knife_round_keeps_original_and_saves_exact_competitive_totals(monkeypatch):
    import pandas as pd
    import demoparser2
    from app.knife_round import visible_match
    class Parser:
        def __init__(self,path): pass
        def parse_header(self): return {'map_name':'test'}
        def parse_event(self,name,**kwargs):
            deaths=[dict(tick=110+i,weapon='knife',attacker_steamid='1',user_steamid=str(2+i),
                attacker_name='a',user_name=str(2+i),attacker_team_num=3,user_team_num=2) for i in range(5)]
            return pd.DataFrame({'round_start':[dict(tick=100),dict(tick=250)],
                'round_end':[dict(tick=200,winner=3),dict(tick=400,winner=2)],
                'round_officially_ended':[], 'player_death':deaths,
                'player_hurt':[dict(deaths[0],dmg_health=80)]}[name])
        def parse_ticks(self,*args,**kwargs):
            return pd.DataFrame([dict(tick=t,steamid='1',name='a',team_num=3,X=0,Y=0,Z=0,
                health=100,is_alive=True) for t in (100,250)])
        def parse_grenades(self,**kwargs): return []
        def parse_events(self,*args,**kwargs): return []
    monkeypatch.setattr(demoparser2,'DemoParser',Parser)
    monkeypatch.setattr("app.parser.scan_equipment", lambda path, first:
        dict(method="equipment-v1",status="knife",round=1,start=100,end=200,checked_frames=80))
    match=parse_demo('knife.dem')
    assert match['players'][0]['kills']==5 and match['players'][0]['damage']==80
    view=visible_match(match)
    assert len(view['rounds'])==1 and view['rounds'][0]['number']==2
    p=next(p for p in view['players'] if p['id']=='1')
    assert p['kills']==0 and p['damage']==0 and p['adr']==0 and p['rounds']==1
    assert p['kast']==100
    assert len(visible_match(match,True)['rounds'])==2
