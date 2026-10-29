"""Official FACEIT APIs and bounded demo downloads. Credentials stay server-side."""
import gzip
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DATA_API = 'https://open.faceit.com/data/v4'
DOWNLOAD_API = 'https://open.faceit.com/download/v2/demos/download'
MATCH_ID = re.compile(r'^1-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')
MAX_FILE = 1024**3


class FaceitError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def configuration():
    return {'data_api': bool(os.environ.get('FACEIT_API_KEY')),
            'downloads_api': bool(os.environ.get('FACEIT_DOWNLOAD_TOKEN'))}


def nickname(profile):
    value = profile.strip()
    if '://' in value or '/' in value:
        parsed = urlsplit(value if '://' in value else 'https://' + value)
        if parsed.scheme != 'https' or parsed.hostname not in ('faceit.com', 'www.faceit.com') or parsed.username or parsed.password:
            raise FaceitError('Нужна ссылка на профиль игрока на faceit.com.', 422)
        parts = [unquote(p) for p in parsed.path.split('/') if p]
        if len(parts) < 2 or parts[-2] != 'players':
            raise FaceitError('Ссылка должна вести на профиль /players/никнейм.', 422)
        value = parts[-1]
    if not re.fullmatch(r'[\w-]{1,64}', value, flags=re.ASCII):
        raise FaceitError('Проверьте никнейм в ссылке FACEIT.', 422)
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api(path, *, download=False, body=None):
    token = os.environ.get('FACEIT_DOWNLOAD_TOKEN' if download else 'FACEIT_API_KEY')
    if not token:
        raise FaceitError('Для скачивания демо настройте FACEIT_DOWNLOAD_TOKEN.' if download else
                          'Для поиска игрока настройте FACEIT_API_KEY на сервере.', 503)
    url = DOWNLOAD_API if download else DATA_API + path
    request = Request(url, data=json.dumps(body).encode() if body is not None else None,
                      headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json',
                               'Content-Type': 'application/json', 'User-Agent': 'CS2-Demo-Lab/1.0'})
    try:
        with build_opener(NoRedirect()).open(request, timeout=25) as response:
            data = response.read(4 * 1024**2 + 1)
        if len(data) > 4 * 1024**2:
            raise FaceitError('Ответ FACEIT слишком большой.')
        result = json.loads(data)
        if not isinstance(result, dict):
            raise FaceitError('FACEIT вернул неожиданный ответ.')
        return result
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise FaceitError('FACEIT отклонил доступ к Downloads API. Проверьте токен и разрешение на скачивание.' if download else
                              'FACEIT отклонил ключ Data API. Проверьте серверный ключ.', 403) from None
        if exc.code == 404:
            raise FaceitError('Игрок или матч FACEIT не найден.', 404) from None
        if exc.code == 429:
            raise FaceitError('Лимит запросов FACEIT. Повторите немного позже.', 429) from None
        raise FaceitError('FACEIT временно не отвечает. Повторите позже.') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise FaceitError('Не удалось получить ответ FACEIT. Проверьте подключение.') from None


def match_details(match_id):
    if not MATCH_ID.fullmatch(match_id):
        raise FaceitError('Некорректный идентификатор матча FACEIT.', 422)
    return api('/matches/' + match_id)


def demo_resources(details):
    values = details.get('demo_url') or []
    return [v for v in values if isinstance(v, str) and v] if isinstance(values, list) else []


def recent_matches(profile, limit=5):
    nick = nickname(profile)
    player = api('/players?' + urlencode({'nickname': nick}))
    player_id = player.get('player_id')
    if not player_id:
        raise FaceitError('FACEIT не вернул идентификатор игрока.')
    history = api('/players/' + quote(player_id, safe='') + '/history?' +
                  urlencode({'game': 'cs2', 'limit': limit, 'offset': 0, 'from': 0}))
    rows = []
    # History is normally newest first; sort explicitly and exclude unfinished matches.
    items = sorted(history.get('items') or [], key=lambda m: m.get('finished_at') or 0, reverse=True)
    for item in items[:limit]:
        if not item.get('finished_at'):
            continue
        mid = item.get('match_id', '')
        if not MATCH_ID.fullmatch(mid):
            continue
        try:
            details = match_details(mid)
            resources = demo_resources(details)
            reason = '' if resources else 'FACEIT не предоставил демо для этого матча.'
        except FaceitError as exc:
            if exc.status != 404:
                raise
            details, resources, reason = {}, [], 'Матч больше недоступен в FACEIT.'
        teams = item.get('teams') or {}
        names = [v.get('nickname') or v.get('name') or 'Команда' for v in teams.values() if isinstance(v, dict)]
        rows.append({'match_id': mid, 'finished_at': item['finished_at'],
                     'name': ' vs '.join(names) or mid, 'demo_count': len(resources),
                     'unavailable_reason': reason,
                     'url': 'https://www.faceit.com/en/cs2/room/' + mid})
    return {'nickname': player.get('nickname') or nick, 'matches': rows, **configuration()}


def validate_download_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    domains = ('faceit.com', 'faceit-cdn.net', 'cloudfront.net', 'amazonaws.com', 'backblazeb2.com')
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or not any(
            host == domain or host.endswith('.' + domain) for domain in domains):
        raise FaceitError('FACEIT вернул неподдерживаемый адрес демо.')
    return url


class DemoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def unpack_demo(source, destination, report=lambda percent, stage: None):
    """Select compression by signature, limit the decompressed size, never trust filenames."""
    with Path(source).open('rb') as raw:
        magic = raw.read(8)
        raw.seek(0)
        if magic.startswith(b'\x1f\x8b'):
            reader = gzip.GzipFile(fileobj=raw)
        elif magic.startswith(b'\x28\xb5\x2f\xfd'):
            try:
                from compression import zstd
                reader = zstd.ZstdFile(raw, 'rb')
            except ImportError:
                import zstandard
                reader = zstandard.ZstdDecompressor().stream_reader(raw)
        elif magic == b'PBDEMS2\x00':
            reader = raw
        else:
            raise FaceitError('Скачанный файл не является demo CS2 или архивом gzip/zstd.')
        report(18, 'Распаковка демо FACEIT')
        total = 0
        try:
            with Path(destination).open('wb') as output:
                while chunk := reader.read(1024**2):
                    total += len(chunk)
                    if total > MAX_FILE:
                        raise FaceitError('Распакованная демка больше 1 ГБ.')
                    output.write(chunk)
        finally:
            if reader is not raw:
                reader.close()
    with Path(destination).open('rb') as output:
        if output.read(8) != b'PBDEMS2\x00':
            raise FaceitError('В архиве нет поддерживаемой demo CS2.')


def download_demo(match_id, demo_index, destination, report):
    resources = demo_resources(match_details(match_id))
    if not 0 <= demo_index < len(resources):
        raise FaceitError('Демо этого матча недоступно или ещё не готово.', 404)
    signed = api('', download=True, body={'resource_url': resources[demo_index]})
    url = (signed.get('payload') or {}).get('download_url')
    if not isinstance(url, str):
        raise FaceitError('FACEIT не предоставил ссылку для скачивания демо.')
    validate_download_url(url)
    archive = Path(str(destination) + '.download')
    try:
        report(1, 'Скачивание демо FACEIT')
        # No bearer token or FACEIT cookies are sent to the storage host.
        with build_opener(DemoRedirect()).open(Request(url, headers={'User-Agent': 'CS2-Demo-Lab/1.0'}), timeout=45) as response:
            expected = int(response.headers.get('Content-Length') or 0)
            if expected > MAX_FILE:
                raise FaceitError('Архив демо больше 1 ГБ.')
            total, previous = 0, -1
            with archive.open('wb') as output:
                while chunk := response.read(1024**2):
                    total += len(chunk)
                    if total > MAX_FILE:
                        raise FaceitError('Архив демо больше 1 ГБ.')
                    output.write(chunk)
                    percent = min(17, int(total / expected * 17)) if expected else 1
                    if percent != previous:
                        report(percent, 'Скачивание демо FACEIT')
                        previous = percent
        unpack_demo(archive, destination, report)
    except FaceitError:
        raise
    except Exception:
        # Signed URLs contain credentials: do not surface/log HTTP exception URLs.
        raise FaceitError('Не удалось скачать или распаковать демо. Ссылка могла истечь; повторите импорт.') from None
    finally:
        archive.unlink(missing_ok=True)
