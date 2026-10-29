from fastapi.testclient import TestClient
import pytest
from app import main


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DATA',tmp_path)
    monkeypatch.setattr(main,'DB',tmp_path/'test.sqlite3')
    with TestClient(main.app) as c:
        yield c


def test_sample_round_export_and_persistence(client):
    assert client.get('/').status_code==200
    mid=client.post('/api/sample').json()['id']
    assert client.post('/api/sample').json()['id']==mid
    summary=client.get(f'/api/matches/{mid}').json()
    assert summary['source']=='synthetic' and len(summary['rounds'])==18
    assert len(summary['players'])==10 and 'frames' not in summary
    frames=client.get(f'/api/matches/{mid}/rounds/1').json()
    assert len(frames)==91 and len(frames[0]['players'])==10
    assert client.get(f'/api/matches/{mid}/rounds/999').status_code==404
    assert client.get(f'/api/matches/{mid}/export?format=csv').text.startswith('\ufeffid,')
    assert len(client.get(f'/api/matches/{mid}/export').json()['frames'])==1638
    assert client.get(f'/api/matches/{mid}/export?format=bad').status_code==400
    assert client.get('/api/matches').json()[0]['status']=='ready'


def test_upload_rejects_invalid_and_cleans_file(client):
    assert client.post('/api/upload?name=test.txt',content=b'abc').status_code==400
    response=client.post('/api/upload?name=test.dem',content=b'bad demo')
    assert response.status_code==400
    assert not list(main.DATA.glob('*.dem'))
    assert client.get('/api/matches/missing').status_code==404


def test_upload_limit(client,monkeypatch):
    monkeypatch.setattr(main,'MAX_UPLOAD',10)
    assert client.post('/api/upload?name=test.dem',content=b'PBDEMS2\x001234').status_code==413
    assert not list(main.DATA.glob('*.dem'))


def test_csv_escapes_formula(client):
    mid=client.post('/api/sample').json()['id']
    result=main.storage.load(main.DB,mid)
    result['players'][0]['name']='=1+1'
    main.storage.save(main.DB,mid,result)
    csv=client.get(f'/api/matches/{mid}/export?format=csv').text
    assert "'=1+1" in csv


def test_player_analysis_filters_and_validation(client):
    mid=client.post('/api/sample').json()['id']
    summary=client.get(f'/api/matches/{mid}').json()
    pid=summary['players'][0]['id']
    url=f'/api/matches/{mid}/players/{pid}/analysis'
    report=client.get(url).json()
    assert report['available'] is True
    assert report['kills']==summary['players'][0]['kills']
    assert report['deaths']==summary['players'][0]['deaths']
    assert report['kills_with_position']==report['kills']
    assert len(report['round_kills'])==18
    assert sum(r['kills'] for r in report['round_kills'])==report['kills']
    filtered=client.get(url+'?round_number=1&side=CT&cell_size=128').json()
    assert filtered['cell_size']==128
    assert len(filtered['round_kills'])==18
    assert all(p['round']==1 for p in filtered['kill_points']+filtered['death_points'])
    assert client.get(url+'?side=invalid').status_code==422
    assert client.get(url+'?cell_size=0').status_code==422
    assert client.get(url+'?round_number=999').status_code==404
    assert client.get(f'/api/matches/{mid}/players/missing/analysis').status_code==404
    assert 'de_mirage' in client.get('/api/maps').json()


@pytest.mark.parametrize('rate', [1, 8, 16, 32, 64, None])
def test_upload_passes_sampling_to_worker(client, monkeypatch, rate):
    from concurrent.futures import Future
    calls=[]
    def submit(*args):
        calls.append(args)
        future=Future()
        future.set_result(None)
        return future
    monkeypatch.setattr(main.app.state.pool,'submit',submit)
    url='/api/upload?name=sampling.dem'+(f'&sample_rate={rate}' if rate else '')
    response=client.post(url,content=b'PBDEMS2\x00dummy')
    assert response.status_code==202
    assert response.json()['sample_rate']==(rate or 16)
    assert calls[0][-1]==(rate or 16)


@pytest.mark.parametrize('rate', ['0','2','7','65','invalid'])
def test_upload_rejects_invalid_sampling(client,rate):
    assert client.post('/api/upload?name=test.dem&sample_rate='+rate,content=b'PBDEMS2\x00').status_code==422
    assert not list(main.DATA.glob('*.dem'))


def test_delete_match_removes_all_saved_data_and_keeps_other_matches(client):
    mid=client.post('/api/sample').json()['id']
    main.storage.create(main.DB,'other','other.dem')
    main.storage.status(main.DB,'other','error','Test error')
    response=client.delete(f'/api/matches/{mid}')
    assert response.status_code==200 and response.json()['deleted'] is True
    assert client.get(f'/api/matches/{mid}').status_code==404
    assert client.get(f'/api/matches/{mid}/rounds/1').status_code==404
    assert client.get(f'/api/matches/{mid}/export').status_code==404
    assert [m['id'] for m in client.get('/api/matches').json()]==['other']
    with main.storage.connect(main.DB) as db:
        assert db.execute('SELECT count(*) FROM round_frames WHERE match_id=?',(mid,)).fetchone()[0]==0
    assert client.delete(f'/api/matches/{mid}').status_code==404
    assert client.delete('/api/matches/other').status_code==200
    assert client.get('/api/matches').json()==[]


@pytest.mark.parametrize('state',['queued','parsing'])
def test_delete_active_job_rejected(client,state):
    main.storage.create(main.DB,'active','active.dem')
    main.storage.status(main.DB,'active',state)
    assert client.delete('/api/matches/active').status_code==409
    assert client.get('/api/matches').json()[0]['status']==state


def test_sample_has_view_angles_and_utility(client):
    mid=client.post('/api/sample').json()['id']
    match=client.get(f'/api/matches/{mid}').json()
    assert match['capabilities']==dict(view_angles=True,grenades=True,bomb_events=True,shots=True,round_clock=True)
    assert match['grenades'] and match['utility_effects']
    assert 'grenades' not in client.get('/api/matches').json()[0]['summary']
    assert client.get(f'/api/matches/{mid}/rounds/1').json()[0]['players'][0]['yaw'] is not None


def test_sample_tactical_data_and_small_summary(client):
    mid=client.post('/api/sample').json()['id']
    match=client.get(f'/api/matches/{mid}').json()
    assert match['bombs'] and match['shots'] and match['bomb_events']
    frame=client.get(f'/api/matches/{mid}/rounds/1').json()[0]
    assert frame['clock']['freeze'] is True
    summary=client.get('/api/matches').json()[0]['summary']
    assert all(k not in summary for k in ('shots','bombs','bomb_events','frames'))


def test_rename_persists_and_does_not_change_analysis(client):
    mid=client.post('/api/sample').json()['id']
    before=main.storage.load(main.DB,mid)
    created=client.get('/api/matches').json()[0]['created']
    response=client.patch(f'/api/matches/{mid}',json={'name':'  Финал • Mirage <team>  '})
    assert response.status_code==200
    assert response.json()==dict(id=mid,name='Финал • Mirage <team>')
    # A fresh SQLite connection must see the name after the request completes.
    row=main.storage.listing(main.DB)[0]
    assert row['name']=='Финал • Mirage <team>' and row['created']==created and row['status']=='ready'
    assert main.storage.load(main.DB,mid)==before
    assert client.patch('/api/matches/missing',json={'name':'Матч'}).status_code==404


@pytest.mark.parametrize('name',['','   ','x'*241,'line\nbreak','tab\tinside'])
def test_rename_rejects_invalid_names(client,name):
    main.storage.create(main.DB,'m','original.dem')
    assert client.patch('/api/matches/m',json={'name':name}).status_code==422
    assert main.storage.listing(main.DB)[0]['name']=='original.dem'


def test_rename_during_processing_survives_save(client):
    main.storage.create(main.DB,'active','original.dem')
    main.storage.status(main.DB,'active','parsing')
    assert client.patch('/api/matches/active',json={'name':'Мой матч'}).status_code==200
    assert main.storage.listing(main.DB)[0]['status']=='parsing'
    main.storage.save(main.DB,'active',dict(rounds=[],players=[],events=[],frames=[]))
    assert main.storage.listing(main.DB)[0]['name']=='Мой матч'


def test_knife_round_default_and_explicit_opt_in(client):
    m=dict(source="demo",knife_scan=dict(method="equipment-v1",status="knife",round=1,start=1,end=100,checked_frames=50),rounds=[dict(number=1,start=1,end=100),dict(number=2,start=101,end=200)],
           events=[dict(round=1,tick=10+i,weapon="knife",enemy=True,victim_id=str(i)) for i in range(5)],
           players=[dict(id="p",kills=5)],warnings=[])
    m.update(map="de_mirage",tickrate=64,schema_version=4,frames=[],
             players_without_knife=[dict(id="p",kills=0)])
    main.storage.create(main.DB,"knife","faceit.dem")
    main.storage.save(main.DB,"knife",m)
    assert [r['number'] for r in client.get('/api/matches/knife').json()['rounds']]==[2]
    assert len(client.get('/api/matches/knife?include_knife=true').json()['rounds'])==2
    assert client.get('/api/matches/knife').json()['players'][0]['kills']==0
    assert len(client.get('/api/matches/knife/export').json()['rounds'])==1
    assert len(client.get('/api/matches/knife/export?include_knife=true').json()['rounds'])==2
    assert len(main.storage.load_details(main.DB,"knife")['rounds'])==2

    report=client.get('/api/matches/knife/players/p/analysis').json()
    assert [r['number'] for r in report['round_kills']]==[2]
    assert len(client.get('/api/matches/knife/players/p/analysis?include_knife=true').json()['round_kills'])==2
    assert client.get('/api/matches/knife/players/p/analysis?round_number=1').status_code==404

    shown=client.get('/api/matches/knife?include_knife=true').json()['rounds']
    assert [(r['number'],r['display_number']) for r in shown]==[(1,None),(2,1)]
    assert client.get('/api/matches/knife').json()['rounds'][0]['display_number']==1
    assert client.get('/api/matches/knife/export?include_knife=true').json()['rounds'][0]['display_number'] is None


def test_map_summary_selection_validation_and_duplicate_ids(client):
    mid=client.post('/api/sample').json()['id']
    response=client.post('/api/analysis/maps',json={'match_ids':[mid,mid]})
    assert response.status_code==200
    report=response.json()
    assert report['matches_count']==1 and len(report['maps'])==1
    data=client.get(f'/api/matches/{mid}').json()
    player=data['players'][0]
    own=client.post('/api/analysis/maps',json={'match_ids':[mid],'player_id':player['id']}).json()['maps'][0]
    assert own['totals']['kills']==player['kills']
    assert own['totals']['adr']==player['adr']
    assert sum(z['delta'] for z in own['balance_zones'])==own['kills_with_position']-own['deaths_with_position']
    assert client.post('/api/analysis/maps',json={'match_ids':[]}).status_code==422
    assert client.post('/api/analysis/maps',json={'match_ids':[mid],'cell_size':0}).status_code==422
    assert client.post('/api/analysis/maps',json={'match_ids':['missing']}).status_code==404
    main.storage.create(main.DB,'busy','busy.dem')
    assert client.post('/api/analysis/maps',json={'match_ids':['busy']}).status_code==409


def test_automatic_map_groups_include_every_ready_demo_and_refresh(client):
    from copy import deepcopy
    mid=client.post('/api/sample').json()['id']
    template=main.storage.load(main.DB,mid)
    for ident,map_name in [('a','de_mirage'),('b','de_mirage'),('c','de_dust2')]:
        value=deepcopy(template);value.update(map=map_name,source='demo')
        main.storage.create(main.DB,ident,'same.dem')
        main.storage.save(main.DB,ident,value)
    main.storage.create(main.DB,'queued','new.dem')
    report=client.get('/api/analysis/maps').json()
    assert report['automatic'] is True and report['matches_count']==3
    assert [(m['map'],m['matches_count']) for m in report['maps']]==[('de_mirage',2),('de_dust2',1)]
    mirage=client.get('/api/analysis/maps?map_name=de_mirage').json()['maps'][0]
    assert {m['id'] for m in mirage['matches']}=={'a','b'}
    assert mirage['totals']['kills']==sum(p['kills'] for p in template['players'])*2
    assert mirage['totals']['adr']==client.get('/api/analysis/maps?map_name=de_dust2').json()['maps'][0]['totals']['adr']
    value=deepcopy(template);value.update(map='de_mirage',source='demo')
    main.storage.save(main.DB,'queued',value)
    assert client.get('/api/analysis/maps?map_name=de_mirage').json()['maps'][0]['matches_count']==3
    assert client.get('/api/analysis/maps?map_name=unknown').json()['maps']==[]
    assert len(client.get('/api/analysis/maps?include_synthetic=true').json()['maps'])==3
