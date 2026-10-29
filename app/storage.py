import gzip
import json
import sqlite3
from collections import defaultdict
from functools import lru_cache
from datetime import datetime, timezone


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    return db


def init(path):
    with connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS matches (id TEXT PRIMARY KEY, name TEXT, created TEXT, status TEXT, error TEXT, summary TEXT, payload BLOB)")
        columns = {r[1] for r in db.execute("PRAGMA table_info(matches)")}
        for name, kind in (("progress", "INTEGER DEFAULT 0"), ("stage", "TEXT")):
            if name not in columns:
                db.execute(f"ALTER TABLE matches ADD COLUMN {name} {kind}")
        db.execute("CREATE TABLE IF NOT EXISTS round_frames (match_id TEXT, number INTEGER, payload BLOB NOT NULL, PRIMARY KEY(match_id,number))")
        db.execute("UPDATE matches SET status='error', error='Обработка прервана перезапуском. Загрузите файл повторно.' WHERE status IN ('queued', 'parsing')")


def create(path, mid, name):
    with connect(path) as db:
        db.execute("INSERT INTO matches(id,name,created,status) VALUES(?,?,?,'queued')", (mid, name, datetime.now(timezone.utc).isoformat()))


def status(path, mid, state, error=None):
    with connect(path) as db:
        db.execute("UPDATE matches SET status=?,error=? WHERE id=?", (state, error, mid))


def reserve_import(path, mid, name):
    """Reserve a remote demo once; failed jobs may be retried."""
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT status FROM matches WHERE id=?', (mid,)).fetchone()
        if row and row['status'] != 'error':
            return False
        if row:
            db.execute("UPDATE matches SET status='queued',error=NULL,progress=0,stage=NULL WHERE id=?", (mid,))
        else:
            db.execute("INSERT INTO matches(id,name,created,status) VALUES(?,?,?,'queued')",
                       (mid, name, datetime.now(timezone.utc).isoformat()))
    return True


def progress(path, mid, percent, stage):
    with connect(path) as db:
        db.execute("UPDATE matches SET progress=?,stage=? WHERE id=? AND status='parsing'",
                   (max(0, min(99, int(percent))), stage, mid))


def rename(path, mid, name):
    with connect(path) as db:
        return db.execute("UPDATE matches SET name=? WHERE id=?", (name, mid)).rowcount > 0


def save(path, mid, result):
    round_player_sides.cache_clear()
    summary = {k:v for k,v in result.items() if k not in ("frames", "events", "grenades", "utility_effects", "bombs", "bomb_events", "shots")}
    details = {k:v for k,v in result.items() if k != "frames"}
    grouped = defaultdict(list)
    for frame in result.get("frames", []):
        grouped[frame["round"]].append(frame)
    def packed(value):
        return gzip.compress(json.dumps(value, ensure_ascii=False, allow_nan=False).encode())
    with connect(path) as db:
        db.execute("UPDATE matches SET status='ready',progress=100,stage='Анализ завершён',summary=?,payload=? WHERE id=?",
            (json.dumps(summary, ensure_ascii=False), packed(details), mid))
        db.execute("DELETE FROM round_frames WHERE match_id=?", (mid,))
        db.executemany("INSERT INTO round_frames(match_id,number,payload) VALUES(?,?,?)",
            [(mid, r["number"], packed(grouped[r["number"]])) for r in result["rounds"]])


def listing(path):
    with connect(path) as db:
        rows = db.execute("SELECT id,name,created,status,error,summary,progress,stage FROM matches ORDER BY created DESC").fetchall()
    return [dict(r, summary=json.loads(r["summary"]) if r["summary"] else None) for r in rows]


def load_details(path, mid):
    with connect(path) as db:
        row = db.execute("SELECT payload FROM matches WHERE id=? AND status='ready'", (mid,)).fetchone()
    if not row:
        return None
    details = json.loads(gzip.decompress(row[0]))
    details.pop("frames", None)
    return details


def load_round(path, mid, number):
    with connect(path) as db:
        row = db.execute("SELECT payload FROM round_frames WHERE match_id=? AND number=?", (mid, number)).fetchone()
    if row:
        return json.loads(gzip.decompress(row[0]))
    # Legacy matches store their snapshots in one compressed payload.
    data = load(path, mid)
    return [f for f in data["frames"] if f["round"] == number] if data else None


def load(path, mid):
    with connect(path) as db:
        row = db.execute("SELECT payload FROM matches WHERE id=? AND status='ready'", (mid,)).fetchone()
        if not row:
            return None
        data = json.loads(gzip.decompress(row[0]))
        if "frames" not in data:
            rows = db.execute("SELECT payload FROM round_frames WHERE match_id=? ORDER BY number", (mid,)).fetchall()
            data["frames"] = [f for r in rows for f in json.loads(gzip.decompress(r[0]))]
    return data


class MatchBusy(Exception):
    pass


def delete(path, mid):
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM matches WHERE id=?", (mid,)).fetchone()
        if row is None:
            return False
        if row["status"] in ("queued", "parsing"):
            raise MatchBusy("Дождитесь завершения обработки, затем удалите матч.")
        db.execute("DELETE FROM round_frames WHERE match_id=?", (mid,))
        db.execute("DELETE FROM matches WHERE id=?", (mid,))
    return True


@lru_cache(maxsize=64)
def round_player_sides(path, mid, bounds):
    """Compact metadata for legacy payloads; decompress snapshots once per match."""
    sides = {}
    for number, start, end in bounds:
        players = {}
        for frame in load_round(path, mid, number) or []:
            for p in frame["players"]:
                if p.get("side") in ("CT", "T"):
                    players.setdefault(p["id"], p["side"])
        sides[number] = players
    return sides
