"""수집 단계 공통 — 소스별 실패를 격리하고, 실패 시 이전 값을 유지한다."""
import traceback

from .env import MissingKey, scrub


def new(prev):
    return {"errors": [], "missing": [], "_prev": prev or {}}


def attempt(raw, key, label, fn, *a, **kw):
    """fn 결과를 raw[key] 에 저장. 실패하면 직전 실행의 raw[key] 를 유지하고 에러를 기록."""
    msg = None
    try:
        raw[key] = fn(*a, **kw)
        return raw[key]
    except MissingKey as e:
        raw["missing"].append(str(e))
    except Exception as e:  # noqa: BLE001 — 소스 하나의 실패가 페이지 전체를 막지 않게
        msg = f"{label}: {type(e).__name__}: {scrub(e)}"[:300]
        print(scrub(traceback.format_exc()))
    prev = raw["_prev"].get(key)
    if prev is not None:
        raw[key] = prev
        if msg:
            msg += " (이전 데이터 유지)"
    if msg:
        raw["errors"].append(msg)
    return raw.get(key)


def finish(raw):
    raw.pop("_prev", None)
    return raw
