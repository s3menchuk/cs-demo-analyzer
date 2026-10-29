import sqlite3

from app import main, storage
from app.sample import sample_match


def test_progress_migrates_existing_database_and_completes(tmp_path):
    db = tmp_path / 'old.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE matches (id TEXT PRIMARY KEY, name TEXT, created TEXT, status TEXT, error TEXT, summary TEXT, payload BLOB)')
        conn.execute("INSERT INTO matches(id,status) VALUES('old','ready')")
    storage.init(db)
    storage.create(db, 'new', 'match.dem')
    storage.status(db, 'new', 'parsing')
    storage.progress(db, 'new', 45, 'Positions')
    row = next(m for m in storage.listing(db) if m['id'] == 'new')
    assert (row['progress'], row['stage']) == (45, 'Positions')
    storage.save(db, 'new', sample_match())
    storage.progress(db, 'new', 50, 'Late update')
    row = next(m for m in storage.listing(db) if m['id'] == 'new')
    assert (row['status'], row['progress']) == ('ready', 100)
    assert any(m['id'] == 'old' for m in storage.listing(db))


def test_worker_publishes_progress_and_preserves_failure(tmp_path, monkeypatch):
    db = tmp_path / 'jobs.sqlite3'
    storage.init(db)
    storage.create(db, 'job', 'match.dem')
    demo = tmp_path / 'match.dem'
    demo.touch()

    def parse(path, sample_rate, on_progress):
        on_progress(25, 'Positions')
        assert storage.listing(db)[0]['progress'] == 25
        raise ValueError('Broken demo')

    monkeypatch.setattr(main, 'parse_demo', parse)
    main.process_job(db, 'job', demo)
    row = storage.listing(db)[0]
    assert row['status'] == 'error'
    assert row['progress'] == 25
    assert 'Broken demo' in row['error']
    assert not demo.exists()
