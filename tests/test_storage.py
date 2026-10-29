import gzip
import json
from app import storage


def test_round_storage_and_legacy_payload(tmp_path):
    db=tmp_path/'matches.sqlite3'
    storage.init(db)
    storage.create(db,'m','match.dem')
    match=dict(sample_rate=16,rounds=[dict(number=1),dict(number=2)],players=[],events=[],
               frames=[dict(round=1,tick=10),dict(round=2,tick=20)])
    storage.save(db,'m',match)
    assert 'frames' not in storage.load_details(db,'m')
    assert storage.load_round(db,'m',1)==[dict(round=1,tick=10)]
    assert storage.load(db,'m')==match
    # Loading one round must not require or unpack another round.
    with storage.connect(db) as conn:
        conn.execute("UPDATE round_frames SET payload=? WHERE number=2",(b'corrupt',))
    assert storage.load_round(db,'m',1)==[dict(round=1,tick=10)]
    storage.save(db,'m',match)
    with storage.connect(db) as conn:
        conn.execute('DELETE FROM round_frames')
        conn.execute('UPDATE matches SET payload=?',(gzip.compress(json.dumps(match).encode()),))
    assert storage.load(db,'m')==match
    assert storage.load_round(db,'m',2)==[dict(round=2,tick=20)]
    assert 'frames' not in storage.load_details(db,'m')
    assert storage.load(db,'missing') is None


def test_round_sides_preserve_start_side_and_are_cached(tmp_path, monkeypatch):
    db=tmp_path/'sides.sqlite3'
    storage.init(db);storage.create(db,'m','m.dem')
    result=dict(rounds=[dict(number=1,start=1,end=100),dict(number=2,start=101,end=200)],
        frames=[dict(round=1,tick=1,players=[dict(id='p',side='T')]),
                dict(round=1,tick=99,players=[dict(id='p',side='CT')]),
                dict(round=2,tick=101,players=[dict(id='p',side='CT')])])
    storage.save(db,'m',result)
    bounds=((1,1,100),(2,101,200))
    assert storage.round_player_sides(str(db),'m',bounds)=={1:{'p':'T'},2:{'p':'CT'}}
    def fail(*args): raise AssertionError('cache must avoid decompressing frames again')
    monkeypatch.setattr(storage,'load_round',fail)
    assert storage.round_player_sides(str(db),'m',bounds)[1]['p']=='T'
