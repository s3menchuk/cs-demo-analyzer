from app.utility import build_utility

ROUNDS=[dict(number=1,start=100,end=400),dict(number=2,start=500,end=800)]


def projectile(tick,x=0,kind='CSmokeGrenadeProjectile',owner='1'):
    return dict(tick=tick,x=x,y=0,z=0,grenade_type=kind,grenade_entity_id=7,steamid=owner,name='a')


def event(tick,entity=7):
    return dict(tick=tick,entityid=entity,x=10,y=0,z=0,user_steamid='1',user_name='a',user_team_num=3)


def test_projectile_downsampling_and_smoke_lifetime():
    rows=[projectile(t,t-120) for t in range(120,211)]
    events={'smokegrenade_detonate':[event(150)],'smokegrenade_expired':[event(210)]}
    tracks,effects=build_utility(rows,events,ROUNDS,{(1,'1'):'CT'},sample_step=8)
    assert len(tracks)==1
    g=tracks[0]
    assert g['start']==120 and g['end']==150
    assert [p['tick'] for p in g['points']]==[120,128,136,144,150]
    assert g['side']=='CT' and g['owner_id']=='1'
    assert effects[0]['start']==150 and effects[0]['end']==210
    assert effects[0]['end_confirmed'] is True


def test_reused_entity_ids_are_separate_grenades():
    rows=[projectile(t) for t in list(range(120,131))+list(range(200,211))+list(range(510,521))]
    events={'smokegrenade_detonate':[event(130),event(210),event(520)],
            'smokegrenade_expired':[event(150),event(230),event(550)]}
    tracks,effects=build_utility(rows,events,ROUNDS,{})
    assert len(tracks)==3 and len({g['id'] for g in tracks})==3
    assert [g['end'] for g in tracks]==[130,210,520]
    assert [g['round'] for g in tracks]==[1,1,2]


def test_inventory_warmup_and_bad_coordinates_ignored():
    rows=[projectile(50),projectile(120,kind='CSmokeGrenade'),projectile(130,x=float('nan'))]
    tracks,effects=build_utility(rows,{'smokegrenade_detonate':[event(50)]},ROUNDS,{})
    assert tracks==[] and effects==[]


def test_effects_clipped_and_missing_expiry_is_explicit():
    _,effects=build_utility([],{'inferno_startburn':[event(390)],'inferno_expire':[event(510)],
                             'flashbang_detonate':[event(200)]},ROUNDS,{})
    fire=next(e for e in effects if e['kind']=='fire')
    flash=next(e for e in effects if e['kind']=='flash')
    assert fire['end']==400 and fire['end_confirmed'] is False
    assert flash['end']==251 and flash['end_confirmed'] is True
