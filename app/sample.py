"""Deterministic synthetic match, explicitly marked in API and UI."""
import random
from math import atan2, degrees
from .analytics import analyze


def sample_match():
    rng = random.Random(42)
    names = ["s1lent", "m0tion", "quasar", "north", "pixel", "sh1ft", "echo", "vortex", "frost", "nova"]
    rounds, frames, deaths, hurts = [], [], [], []
    for rid in range(1, 19):
        start = (rid-1)*6400
        rounds.append(dict(number=rid, start=start, end=start+5760, decision_tick=start+(75 if rid%3 else 90)*64,
                           freeze_end=start+15*64,winner="CT" if rid % 3 else "T", reason="Учебные данные"))
        order = rng.sample(range(10), 8)
        death_at = {p: 24+i*7 for i, p in enumerate(order)}
        def team(p):
            return 3 if (p < 5) == (rid <= 12) else 2
        round_deaths = []
        for victim, second in sorted(death_at.items(), key=lambda x: x[1]):
            candidates = [p for p in range(10) if team(p) != team(victim) and death_at.get(p,999)>second]
            if not candidates:
                continue
            a = rng.choice(candidates)
            e = dict(tick=start+second*64, round=rid, user_steamid=str(victim+1), user_name=names[victim], user_team_num=team(victim), attacker_steamid=str(a+1), attacker_name=names[a], attacker_team_num=team(a), weapon=rng.choice(["ak47", "m4a1_silencer", "awp"]), headshot=rng.random()<.45)
            for prefix, p in (("attacker", a), ("user", victim)):
                e.update({f"{prefix}_X":150+(p%5)*130+math_sin(second/18+p)*95,
                          f"{prefix}_Y":180+(p//5)*530+math_sin(second/25+p)*110-second*2*(1 if p>=5 else -1),
                          f"{prefix}_Z":0})
            round_deaths.append(e)
            hurts.append(dict(e, dmg_health=100))
        deaths.extend(round_deaths)
        actual_deaths = {int(e['user_steamid'])-1:(e['tick']-start)//64 for e in round_deaths}
        for second in range(91):
            pts = []
            for p, name in enumerate(names):
                x = 150 + (p % 5)*130 + math_sin(second/18+p)*95
                y = 180 + (p//5)*530 + math_sin(second/25+p)*110 - second*2*(1 if p>=5 else -1)
                pts.append(dict(id=str(p+1), name=name, side="CT" if team(p)==3 else "T", x=round(x,1), y=round(y,1), z=0, hp=100 if second < actual_deaths.get(p, 999) else 0, alive=second < actual_deaths.get(p, 999), yaw=(second*7+p*36)%360-180, pitch=0))
            frames.append(dict(tick=start+second*64, round=rid, players=pts,
                clock=dict(seconds=15-second if second<15 else max(0,115-(second-15)),freeze=second<15,
                           paused=False,duration=115,game_time=start/64+second,round_start_time=start/64+15)))
    players, events = analyze(rounds, deaths, hurts, frames)
    grenades, effects = [], []
    for r in rounds:
        start = r["start"]+15*64
        points = [dict(tick=start+i*4,x=200+i*5,y=400+i*2,z=0) for i in range(33)]
        grenades.append(dict(id=f"sample:{r['number']}",round=r["number"],kind="smoke",owner_id="1",owner_name=names[0],side="CT" if r["number"]<=12 else "T",start=start,end=start+128,points=points))
        effects.append(dict(id=f"sample-effect:{r['number']}",round=r["number"],kind="smoke",owner_id="1",owner_name=names[0],side="CT" if r["number"]<=12 else "T",start=start+128,end=start+128+18*64,x=360,y=464,z=0,end_confirmed=True))
    bombs,bomb_events,shots=[],[],[]
    for r in rounds:
        t=r['start'];resolved=t+(75 if r['winner']=='CT' else 90)*64
        point=dict(x=400,y=450,z=0)
        bombs.append(dict(round=r['number'],planted_tick=t+50*64,position=point,position_source='synthetic',
            site='A',raw_site=0,planter=names[0],planter_id='1',planted_game_time=t/64+50,
            resolved_tick=resolved,outcome='defused' if r['winner']=='CT' else 'exploded',fuse_seconds=40,fuse_source='server_cvar'))
        actions=[('bomb_beginplant',47),('bomb_planted',50)]
        if r['winner']=='CT':actions.extend([('bomb_begindefuse',65),('bomb_defused',75)])
        else:actions.append(('bomb_exploded',90))
        bomb_events.extend(dict(type=name,tick=t+sec*64,round=r['number'],actor_id='1',actor=names[0],position=point,site='A',raw_site=0,has_kit=False) for name,sec in actions)
    for i,e in enumerate(deaths):
        point=dict(x=e['attacker_X'],y=e['attacker_Y'],z=e['attacker_Z'])
        shots.append(dict(id=f'sample-shot:{i}',tick=e['tick']-2,round=e['round'],shooter_id=e['attacker_steamid'],
            shooter=e['attacker_name'],side='CT' if e['attacker_team_num']==3 else 'T',weapon=e['weapon'],silenced=False,
            position=point,yaw=degrees(atan2(e['user_Y']-point['y'],e['user_X']-point['x'])),pitch=0))
    return dict(map="training_arena", tickrate=64, sample_seconds=1, rounds=rounds, players=players,
                events=events, frames=frames, grenades=grenades, utility_effects=effects,
                bombs=bombs,bomb_events=bomb_events,shots=shots,
                capabilities=dict(view_angles=True,grenades=True,bomb_events=True,shots=True,round_clock=True),source="synthetic", schema_version=4, warnings=["Синтетический матч для знакомства с интерфейсом. Позиции и результаты сгенерированы."])


def math_sin(x):
    from math import sin
    return sin(x)
