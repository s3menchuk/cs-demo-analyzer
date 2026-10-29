from app.analytics import analyze, identity


def player(pid, side="CT"):
    return dict(id=str(pid), name=f"p{pid}", side=side, x=0, y=0, hp=100, alive=True)


def event(a, v, tick, ateam=3, vteam=2, **extra):
    return dict(round=1, tick=tick, attacker_steamid=str(a), user_steamid=str(v),
                attacker_name=f"p{a}", user_name=f"p{v}", attacker_team_num=ateam,
                user_team_num=vteam, **extra)


def fixture():
    rounds = [dict(number=1, start=0, end=6400)]
    frames = [dict(tick=0, round=1, players=[player(1),player(2,"T"),player(3)])]
    return rounds, frames


def test_enemy_stats_and_trade():
    rounds, frames = fixture()
    # T kills CT; CT teammate trades within 5 sec.
    deaths = [event(2,1,64,2,3, headshot=True),event(3,2,320)]
    players, _ = analyze(rounds,deaths,[event(2,1,63,2,3,dmg_health=120)],frames)
    p = {x['id']:x for x in players}
    assert p['1']['kast'] == 100
    assert p['2']['kills'] == 1 and p['2']['hs'] == 100
    assert p['2']['adr'] == 100  # Overkill is capped.
    assert p['2']['opening_kills'] == 1
    assert p['1']['opening_deaths'] == 1


def test_late_trade_does_not_count():
    rounds, frames = fixture()
    players,_=analyze(rounds,[event(2,1,64,2,3),event(3,2,385)],[],frames)
    assert next(p for p in players if p['id']=='1')['kast']==0


def test_teamkills_suicides_world_and_damage():
    rounds, frames = fixture()
    deaths=[event(1,3,10,3,3),event(2,2,20,2,2),event(0,1,30,0,3)]
    hurts=[event(1,3,1,3,3,dmg_health=50),event(1,2,2,dmg_health=200)]
    # World has no player ID/name.
    deaths[-1].update(attacker_steamid=None,attacker_name=None)
    players,_=analyze(rounds,deaths,hurts,frames)
    p={x['id']:x for x in players}
    assert p['1']['kills']==0 and p['1']['damage']==100
    assert p['3']['deaths']==1 and p['2']['deaths']==1
    assert all(x['opening_kills']==0 for x in players)


def test_participation_denominator_and_assist():
    rounds,frames=fixture()
    rounds.append(dict(number=2,start=6500,end=7000))
    frames.append(dict(tick=6500,round=2,players=[player(1),player(2,'T')]))
    e=event(1,2,64,assister_steamid='3',assister_name='p3',assister_team_num=3)
    players,_=analyze(rounds,[e],[event(1,2,63,dmg_health=80)],frames)
    p={x['id']:x for x in players}
    assert p['1']['adr']==40 and p['1']['rounds']==2
    assert p['3']['assists']==1 and p['3']['rounds']==1


def test_ids_keep_precision_and_bot_identity():
    assert identity({'user_steamid':'76561198000000001'})=='76561198000000001'
    assert identity({'user_steamid':0,'user_name':'bot'})=='bot:bot'
