import gzip
import io
from concurrent.futures import Future

import pytest
from fastapi.testclient import TestClient

from app import faceit, main, storage
from app.sample import sample_match

MID = '1-12345678-1234-1234-1234-123456789abc'
DEMO = b'PBDEMS2\x00' + b'demo-data' * 100


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch):
    monkeypatch.delenv('FACEIT_API_KEY', raising=False)
    monkeypatch.delenv('FACEIT_DOWNLOAD_TOKEN', raising=False)


@pytest.mark.parametrize('profile', ['Some-Nick', 'https://www.faceit.com/ru/players/Some-Nick',
                                     'https://faceit.com/en/players/Some-Nick/?x=1', 'faceit.com/ru/players/Some-Nick'])
def test_profile(profile):
    assert faceit.nickname(profile) == 'Some-Nick'


@pytest.mark.parametrize('profile', ['https://faceit.com.evil.test/ru/players/Nick',
                                     'http://faceit.com/ru/players/Nick', 'https://localhost/players/Nick',
                                     'https://www.faceit.com/ru/cs2/room/' + MID, 'https://faceit.com/players/%2f'])
def test_invalid_profile(profile):
    with pytest.raises(faceit.FaceitError):
        faceit.nickname(profile)


def test_recent_matches_are_latest_cs2_without_signed_urls(monkeypatch):
    calls = []
    def api(path):
        calls.append(path)
        if path.startswith('/players?'):
            return {'player_id': 'player', 'nickname': 'Nick'}
        if '/history?' in path:
            return {'items': [{'match_id': MID, 'finished_at': 100, 'teams': {'a': {'nickname': 'Alpha'}, 'b': {'nickname': 'Beta'}}}]}
        return {'demo_url': ['https://demos.faceit.com/game.dem.zst']}
    monkeypatch.setattr(faceit, 'api', api)
    result = faceit.recent_matches('Nick', 5)
    assert result['matches'][0]['name'] == 'Alpha vs Beta'
    assert result['matches'][0]['demo_count'] == 1
    assert 'game=cs2' in calls[1] and 'limit=5' in calls[1]
    assert 'demo_url' not in result['matches'][0]


@pytest.mark.parametrize('url', ['http://demos.faceit.com/demo', 'https://localhost/demo',
                                 'https://demos.faceit.com.evil.test/demo', 'https://127.0.0.1/demo',
                                 'https://user:secret@demos.faceit.com/demo'])
def test_download_url_validation(url):
    with pytest.raises(faceit.FaceitError):
        faceit.validate_download_url(url)


@pytest.mark.parametrize('compression', ['raw', 'gzip', 'zstd'])
def test_unpack(tmp_path, compression):
    if compression == 'gzip':
        content = gzip.compress(DEMO)
    elif compression == 'zstd':
        try:
            from compression import zstd
            content = zstd.compress(DEMO)
        except ImportError:
            content = pytest.importorskip('zstandard').ZstdCompressor().compress(DEMO)
    else:
        content = DEMO
    source, dest = tmp_path / 'download', tmp_path / 'demo.dem'
    source.write_bytes(content)
    faceit.unpack_demo(source, dest)
    assert dest.read_bytes() == DEMO


def test_unpack_rejects_large_or_invalid_output(tmp_path, monkeypatch):
    source, dest = tmp_path / 'download', tmp_path / 'demo.dem'
    source.write_bytes(gzip.compress(DEMO))
    monkeypatch.setattr(faceit, 'MAX_FILE', 20)
    with pytest.raises(faceit.FaceitError, match='1 ГБ'):
        faceit.unpack_demo(source, dest)
    source.write_bytes(b'<html>Error</html>')
    with pytest.raises(faceit.FaceitError):
        faceit.unpack_demo(source, dest)


def test_download_uses_signed_url_without_api_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(faceit, 'match_details', lambda mid: {'demo_url': ['resource']})
    monkeypatch.setattr(faceit, 'api', lambda *args, **kwargs: {'payload': {'download_url': 'https://demos.faceit.com/demo?signature=secret'}})
    requests = []
    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            response = io.BytesIO(gzip.compress(DEMO))
            response.headers = {}
            return response
    monkeypatch.setattr(faceit, 'build_opener', lambda *args: Opener())
    dest = tmp_path / 'demo.dem'
    faceit.download_demo(MID, 0, dest, lambda *args: None)
    assert dest.read_bytes() == DEMO
    assert not requests[0].has_header('Authorization')
    assert not list(tmp_path.glob('*.download'))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DATA', tmp_path)
    monkeypatch.setattr(main, 'DB', tmp_path / 'test.sqlite3')
    with TestClient(main.app) as client:
        yield client


def test_missing_configuration_is_actionable_and_does_not_leak_keys(client):
    assert client.get('/api/faceit/config').json() == {'data_api': False, 'downloads_api': False}
    response = client.get('/api/faceit/matches?profile=Nick')
    assert response.status_code == 503
    assert 'FACEIT_API_KEY' in response.json()['detail']
    assert client.post('/api/faceit/import', json={'match_id': MID}).status_code == 503


def test_import_reserves_once_and_retries_failed_job(client, monkeypatch):
    monkeypatch.setenv('FACEIT_API_KEY', 'test-data-secret')
    monkeypatch.setenv('FACEIT_DOWNLOAD_TOKEN', 'test-download-secret')
    calls = []
    def submit(*args):
        calls.append(args)
        result = Future()
        result.set_result(None)
        return result
    monkeypatch.setattr(main.app.state.pool, 'submit', submit)
    first = client.post('/api/faceit/import', json={'match_id': MID}).json()
    second = client.post('/api/faceit/import', json={'match_id': MID}).json()
    assert first['id'] == second['id'] and second['existing']
    assert len(calls) == 1
    storage.status(main.DB, first['id'], 'error', 'download failed')
    assert client.post('/api/faceit/import', json={'match_id': MID}).status_code == 202
    assert len(calls) == 2
    assert client.get('/api/faceit/config').json() == {'data_api': True, 'downloads_api': True}
    assert 'secret' not in client.get('/api/faceit/config').text


def test_import_rejects_invalid_ids_sampling_and_full_queue(client, monkeypatch):
    assert client.post('/api/faceit/import', json={'match_id': 'https://localhost'}).status_code == 422
    assert client.post('/api/faceit/import', json={'match_id': MID, 'sample_rate': 3}).status_code == 422
    monkeypatch.setenv('FACEIT_API_KEY', 'test')
    monkeypatch.setenv('FACEIT_DOWNLOAD_TOKEN', 'test')
    main.app.state.uploads = 3
    assert client.post('/api/faceit/import', json={'match_id': MID}).status_code == 429
    assert storage.listing(main.DB) == []


def test_worker_downloads_parses_saves_and_cleans(tmp_path, monkeypatch):
    db, dest = tmp_path / 'jobs.sqlite3', tmp_path / 'demo.dem'
    storage.init(db)
    storage.create(db, 'job', 'FACEIT match')
    def download(mid, index, path, report):
        Path = type(dest)
        Path(path).write_bytes(DEMO)
        report(17, 'Downloaded')
    def parse(path, sample_rate, on_progress):
        on_progress(45, 'Positions')
        return sample_match()
    monkeypatch.setattr(faceit, 'download_demo', download)
    monkeypatch.setattr(main, 'parse_demo', parse)
    main.process_faceit_job(db, 'job', dest, MID, 0, 16)
    assert storage.listing(db)[0]['status'] == 'ready'
    assert storage.load_details(db, 'job')['faceit_match_id'] == MID
    assert not dest.exists()
