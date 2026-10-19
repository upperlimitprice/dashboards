"""HTTP GET — 재시도·디스크 캐시. 모든 수집기는 이 모듈만 거친다."""
import hashlib
import json
import time

import requests

from .env import CACHE, env

_session = None


class NotFound(Exception):
    pass


def session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = env(
            "HTTP_USER_AGENT", "industry-dashboards/1.0 (personal research)")
    return _session


def get(url, params=None, headers=None, timeout=60, retries=3, cache_hours=0):
    """bytes 반환. cache_hours>0 이면 .cache/ 에 저장해 재사용 (대용량 엑셀 등)."""
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True, default=str)).encode()).hexdigest()
    path = CACHE / key
    if cache_hours and path.exists() and time.time() - path.stat().st_mtime < cache_hours * 3600:
        return path.read_bytes()
    last = None
    for i in range(retries):
        try:
            r = session().get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 404:
                raise NotFound(url)
            r.raise_for_status()
            if cache_hours:
                CACHE.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
            return r.content
        except NotFound:
            raise
        except requests.RequestException as e:
            last = e
            if i < retries - 1:
                time.sleep(2 ** (i + 1))
    raise last


def get_json(url, params=None, **kw):
    return json.loads(get(url, params, **kw))


def get_text(url, params=None, **kw):
    return get(url, params, **kw).decode("utf-8-sig")
