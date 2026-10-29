from app.tactical import build_tactical,clock,RULES


def event(tick,**extra):
    return dict(tick=tick,user_steamid='1',user_name='a',user_X=-465,user_Y=-2178,user_Z=-160,
                user_team_num=2,user_yaw=10,user_pitch=2,site=184,**extra)


def rounds():
    return [dict(number=1,start=0,end=5000,decision_tick=4800),dict(number=2,start=6000,end=10000,decision_tick=9900)]


def test_native_round_clock_freeze_active_and_pause():
    row=dict(game_time=10,round_start_time=20,is_freeze_period=True)
    row[RULES+'m_iRoundTime']=115
    assert clock(row)['seconds']==10
    row.update(game_time=25,is_freeze_period=False)
    assert clock(row)['seconds']==110
    row[RULES+'m_bGamePaused']=True
    assert clock(row)['paused'] is True
    assert clock({}) is None


def test_observed_explosion_and_estimate_from_other_rounds():
    events=dict(bomb_planted=[event(1000),event(7000)],bomb_exploded=[event(3560)],bomb_defused=[event(8500)])
    bombs,normalized,_=build_tactical(events,rounds(),'de_mirage')
    assert bombs[0]['fuse_seconds']==40 and bombs[0]['fuse_source']=='recorded_explosion'
    assert bombs[0]['site']=='A' and bombs[0]['raw_site']==184
    assert bombs[1]['fuse_seconds']==40 and bombs[1]['fuse_source']=='measured_other_rounds'
    assert bombs[1]['outcome']=='defused'
    assert bombs[0]['position']==dict(x=-465,y=-2178,z=-160)


def test_cvar_at_plant_time_and_unknown_timer_are_not_confused():
    events=dict(bomb_planted=[event(1000),event(7000)],server_cvar=[
        dict(tick=-1,name='mp_c4timer',value='45'),dict(tick=6000,name='mp_c4timer',value='30')])
    bombs,_,_=build_tactical(events,rounds(),'unknown')
    assert [b['fuse_seconds'] for b in bombs]==[45,30]
    assert bombs[0]['site'] is None
    bombs,_,_=build_tactical(dict(bomb_planted=[event(1000)]),rounds(),'unknown')
    assert bombs[0]['fuse_seconds'] is None and bombs[0]['fuse_source']=='unknown'


def test_shots_keep_exact_position_angle_and_exclude_grenade_and_knife():
    events=dict(weapon_fire=[event(1000,weapon='weapon_ak47'),event(1001,weapon='weapon_smokegrenade'),
                            event(1002,weapon='weapon_knife_t'),event(5500,weapon='weapon_ak47')])
    _,_,shots=build_tactical(events,rounds(),'unknown')
    assert len(shots)==1
    assert shots[0]['tick']==1000 and shots[0]['yaw']==10 and shots[0]['weapon']=='ak47'
    assert shots[0]['position']==dict(x=-465,y=-2178,z=-160)


def test_native_game_time_is_used_for_observed_fuse():
    frames=[dict(tick=1000,round=1,clock=dict(game_time=20,paused=False)),
            dict(tick=3560,round=1,clock=dict(game_time=55,paused=False))]
    bombs,_,_=build_tactical(dict(bomb_planted=[event(1000)],bomb_exploded=[event(3560)]),rounds(),'unknown',frames=frames)
    assert bombs[0]['planted_game_time']==20 and bombs[0]['fuse_seconds']==35
