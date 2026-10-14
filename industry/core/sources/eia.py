"""EIA Open Data API v2 — https://www.eia.gov/opendata/ (무료 키: EIA_API_KEY)."""
from ..env import require
from ..http import get_json

BASE = "https://api.eia.gov/v2/"
PAGE = 5000


def fetch(route, params, max_rows=200_000):
    """route 예: 'electricity/rto/daily-region-data/data/'. params 는 (k, v) 튜플 리스트."""
    key = require("EIA_API_KEY")
    rows, offset = [], 0
    while True:
        p = [("api_key", key), ("offset", offset), ("length", PAGE)] + list(params)
        resp = get_json(BASE + route, p, timeout=90)["response"]
        chunk = resp.get("data", [])
        rows.extend(chunk)
        total = int(resp.get("total", 0) or 0)
        offset += len(chunk)
        if not chunk or offset >= total or offset >= max_rows:
            return rows


def facets(name, values):
    return [(f"facets[{name}][]", v) for v in values]


def series(rows, key_field, value_field="value", period="period"):
    """rows → {key_field 값: {period: float}}"""
    out = {}
    for r in rows:
        v = r.get(value_field)
        if v in (None, ""):
            continue
        out.setdefault(r[key_field], {})[r[period]] = float(v)
    return out
