from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
import csv
import io
import json
import logging
import os
import uuid
from fastapi import FastAPI, HTTPException, Request, Query
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from . import storage
from . import faceit
from starlette.concurrency import run_in_threadpool
from .parser import parse_demo, SAMPLE_RATES, DEFAULT_SAMPLE_RATE
from .sample import sample_match
from .maps import catalog
from .player_analysis import analyze_player
from .knife_round import visible_match
from .map_analysis import analyze_maps

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("CS2_DATA_DIR", str(ROOT / "data")))
DB = DATA / "matches.sqlite3"
MAX_UPLOAD = 1024 * 1024 * 1024


def process_job(db, mid, path, sample_rate=DEFAULT_SAMPLE_RATE):
    storage.status(db, mid, "parsing")
    try:
        result = parse_demo(path, sample_rate=sample_rate,
                            on_progress=lambda percent, stage: storage.progress(db, mid, percent, stage))
        storage.progress(db, mid, 96, "Сохранение результатов")
        storage.save(db, mid, result)
    except Exception as exc:
        logging.exception("Demo parsing failed: %s", mid)
        storage.status(db, mid, "error", f"Не удалось разобрать demo: {str(exc)[:400]}")
    finally:
        Path(path).unlink(missing_ok=True)


def process_faceit_job(db, mid, path, faceit_id, demo_index, sample_rate):
    storage.status(db, mid, 'parsing')
    try:
        report = lambda percent, stage: storage.progress(db, mid, percent, stage)
        faceit.download_demo(faceit_id, demo_index, path, report)
        result = parse_demo(path, sample_rate=sample_rate,
                            on_progress=lambda percent, stage: report(20 + int(percent * .76), stage))
        result['faceit_match_id'] = faceit_id
        result['faceit_demo_index'] = demo_index
        report(96, 'Сохранение результатов')
        storage.save(db, mid, result)
    except faceit.FaceitError as exc:
        storage.status(db, mid, 'error', str(exc))
    except Exception:
        storage.status(db, mid, 'error', 'Не удалось обработать демо FACEIT. Попробуйте повторить импорт.')
    finally:
        Path(path).unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(app):
    DATA.mkdir(parents=True, exist_ok=True)
    storage.init(DB)
    # A single native parser at a time bounds memory and isolates parser failures.
    app.state.pool = ProcessPoolExecutor(max_workers=1)
    app.state.jobs = set()
    app.state.uploads = 0
    yield
    app.state.pool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(title="CS2 Demo Lab", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/matches")
def matches():
    return storage.listing(DB)


@app.get("/api/maps")
def maps():
    return catalog()


@app.post("/api/sample", status_code=201)
def sample():
    existing = next((r for r in storage.listing(DB) if r["summary"] and r["summary"].get("source") == "synthetic"), None)
    if existing:
        if existing["summary"].get("schema_version", 1) < 4:
            storage.save(DB, existing["id"], sample_match())
        return {"id": existing["id"]}
    mid = uuid.uuid4().hex
    storage.create(DB, mid, "Учебный матч · синтетические данные")
    storage.save(DB, mid, sample_match())
    return {"id": mid}


@app.post("/api/upload", status_code=202)
async def upload(request: Request, name: str, sample_rate: int = Query(DEFAULT_SAMPLE_RATE)):
    if sample_rate not in SAMPLE_RATES:
        raise HTTPException(422, "Частота снимков должна быть 1, 8, 16, 32 или 64 Гц.")
    if not name.lower().endswith(".dem") or len(name) > 240:
        raise HTTPException(400, "Выберите файл с расширением .dem (до 240 символов в имени).")
    if len(app.state.jobs) + app.state.uploads >= 3:
        raise HTTPException(429, "Очередь заполнена. Дождитесь завершения текущего анализа.")
    mid = uuid.uuid4().hex
    path = DATA / f"{mid}.dem"
    size = 0
    app.state.uploads += 1
    try:
        with path.open("wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Максимальный размер файла — 1 ГБ.")
                f.write(chunk)
        with path.open("rb") as f:
            if f.read(8) != b"PBDEMS2\x00":
                raise HTTPException(400, "Файл не содержит заголовок CS2 demo (PBDEMS2). Распакуйте архив перед загрузкой.")
        storage.create(DB, mid, name.replace("\\", "/").split("/")[-1])
        future = app.state.pool.submit(process_job, str(DB), mid, str(path), sample_rate)
        app.state.jobs.add(future)
        def completed(job):
            app.state.jobs.discard(job)
            if not job.cancelled() and job.exception():
                storage.status(DB, mid, "error", "Процесс парсера завершился аварийно. Перезапустите приложение.")
                path.unlink(missing_ok=True)
        future.add_done_callback(completed)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        app.state.uploads -= 1
    return {"id": mid, "sample_rate": sample_rate}


@app.get('/api/faceit/config')
def faceit_config():
    return faceit.configuration()


@app.get('/api/faceit/matches')
async def faceit_matches(profile: str = Query(min_length=1, max_length=300), limit: int = Query(5, ge=1, le=20)):
    try:
        return await run_in_threadpool(faceit.recent_matches, profile, limit)
    except faceit.FaceitError as exc:
        raise HTTPException(exc.status, str(exc)) from None


class FaceitImport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    match_id: str = Field(pattern=faceit.MATCH_ID.pattern)
    demo_index: int = Field(0, ge=0, le=9)
    sample_rate: int = DEFAULT_SAMPLE_RATE


@app.post('/api/faceit/import', status_code=202)
async def faceit_import(body: FaceitImport):
    if body.sample_rate not in SAMPLE_RATES:
        raise HTTPException(422, 'Неподдерживаемая частота снимков.')
    config = faceit.configuration()
    if not config['data_api'] or not config['downloads_api']:
        raise HTTPException(503, 'Для импорта настройте FACEIT_API_KEY и FACEIT_DOWNLOAD_TOKEN на сервере.')
    mid = f'faceit_{body.match_id.lower()}_{body.demo_index}'
    existing = next((m for m in storage.listing(DB) if m['id'] == mid), None)
    if existing and existing['status'] != 'error':
        return {'id': mid, 'existing': True, 'sample_rate': body.sample_rate}
    if len(app.state.jobs) + app.state.uploads >= 3:
        raise HTTPException(429, 'Очередь заполнена. Дождитесь завершения текущего анализа.')
    if not storage.reserve_import(DB, mid, f'FACEIT · {body.match_id} · демо {body.demo_index + 1}'):
        return {'id': mid, 'existing': True, 'sample_rate': body.sample_rate}
    path = DATA / f'{mid}.dem'
    try:
        future = app.state.pool.submit(process_faceit_job, str(DB), mid, str(path),
                                       body.match_id, body.demo_index, body.sample_rate)
        app.state.jobs.add(future)
        def completed(job):
            app.state.jobs.discard(job)
            if job.cancelled() or job.exception():
                storage.status(DB, mid, 'error', 'Импорт FACEIT прерван. Повторите попытку.')
                path.unlink(missing_ok=True)
                Path(str(path) + '.download').unlink(missing_ok=True)
        future.add_done_callback(completed)
    except Exception:
        storage.status(DB, mid, 'error', 'Не удалось запустить импорт FACEIT. Перезапустите приложение.')
        raise HTTPException(503, 'Не удалось запустить импорт FACEIT.') from None
    return {'id': mid, 'existing': False, 'sample_rate': body.sample_rate}


def result(mid, include_frames=False):
    value = storage.load(DB, mid) if include_frames else storage.load_details(DB, mid)
    if value is None:
        raise HTTPException(404, "Матч не найден или анализ ещё не завершён.")
    return value


@app.get("/api/matches/{mid}")
def match(mid: str, include_knife: bool = False):
    value = visible_match(result(mid), include_knife)
    if any("player_sides" not in r for r in value["rounds"]):
        bounds = tuple((r["number"], r["start"], r["end"]) for r in value["rounds"])
        sides = storage.round_player_sides(str(DB), mid, bounds)
        value["rounds"] = [dict(r, player_sides=r.get("player_sides", sides.get(r["number"], {})))
                           for r in value["rounds"]]
    return {k:v for k,v in value.items() if k != "frames"}


@app.delete("/api/matches/{mid}")
def delete_match(mid: str):
    try:
        removed = storage.delete(DB, mid)
    except storage.MatchBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    if not removed:
        raise HTTPException(404, "Матч не найден.")
    return {"id": mid, "deleted": True}


class RenameMatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=240)

    @field_validator("name")
    @classmethod
    def printable_name(cls, value):
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Название не должно содержать управляющие символы.")
        return value


@app.patch("/api/matches/{mid}")
def rename_match(mid: str, body: RenameMatch):
    if not storage.rename(DB, mid, body.name):
        raise HTTPException(404, "Матч не найден.")
    return {"id": mid, "name": body.name}


@app.get("/api/matches/{mid}/players/{pid}/analysis")
def player_analysis(mid: str, pid: str, round_number: int | None = Query(None, ge=1),
                    side: Literal["CT", "T"] | None = None,
                    cell_size: int = Query(256, ge=64, le=1024), include_knife: bool = False):
    match = visible_match(result(mid), include_knife)
    if round_number is not None and round_number not in [r["number"] for r in match["rounds"]]:
        raise HTTPException(404, "Раунд не найден.")
    report = analyze_player(match, pid, round_number, side, cell_size)
    if report is None:
        raise HTTPException(404, "Игрок не найден.")
    return report


@app.get("/api/matches/{mid}/rounds/{number}")
def round_frames(mid: str, number: int):
    data = result(mid)
    if number not in [r["number"] for r in data["rounds"]]:
        raise HTTPException(404, "Раунд не найден.")
    return storage.load_round(DB, mid, number)


@app.get("/api/matches/{mid}/export")
def export(mid: str, format: str = "json", include_knife: bool = False):
    data = visible_match(result(mid, include_frames=format == "json"), include_knife)
    if format == "json":
        return Response(json.dumps(data, ensure_ascii=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{mid}.json"'})
    if format != "csv":
        raise HTTPException(400, "Доступны форматы json и csv.")
    out = io.StringIO(newline="")
    if data["players"]:
        writer = csv.DictWriter(out, fieldnames=data["players"][0].keys())
        writer.writeheader()
        for player in data["players"]:
            # Prevent spreadsheet formula execution for untrusted Steam names.
            writer.writerow({k: "'"+v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else v for k,v in player.items()})
    return Response("\ufeff"+out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{mid}.csv"'})


class MapAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_ids: list[str] = Field(min_length=1, max_length=100)
    player_id: str | None = Field(None, max_length=100)
    cell_size: int = Field(256, ge=64, le=1024)
    include_knife: bool = False


@app.post("/api/analysis/maps")
def map_analysis(body: MapAnalysisRequest):
    rows = {r["id"]: r for r in storage.listing(DB)}
    selected = list(dict.fromkeys(body.match_ids))
    for mid in selected:
        if mid not in rows: raise HTTPException(404, "Один из выбранных матчей удалён. Обновите список.")
        if rows[mid]["status"] != "ready": raise HTTPException(409, "Дождитесь завершения анализа выбранных матчей.")
    entries = ((mid, rows[mid]["name"], visible_match(result(mid), body.include_knife)) for mid in selected)
    return analyze_maps(entries, body.player_id, body.cell_size)


@app.get("/api/analysis/maps")
def all_maps_analysis(map_name: str | None = Query(None, max_length=160),
                      player_id: str | None = Query(None, max_length=100),
                      cell_size: int = Query(256, ge=64, le=1024),
                      include_knife: bool = False, include_synthetic: bool = False):
    # Group membership always follows saved map metadata, not filenames or UI selection.
    selected = [r for r in storage.listing(DB) if r["status"] == "ready" and r["summary"]
                and (map_name is None or r["summary"].get("map") == map_name)
                and (include_synthetic or r["summary"].get("source") != "synthetic")]
    entries = ((r["id"], r["name"], visible_match(result(r["id"]), include_knife)) for r in selected)
    return dict(analyze_maps(entries, player_id, cell_size), scope_map=map_name, automatic=True)
