"""manual/*.csv — 무료 API가 없는 지표(리드타임·스팟가 등)를 직접 입력하는 파일."""
import csv

from .env import MANUAL


def read(name):
    p = MANUAL / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(l for l in f if not l.startswith("#")) if any(r.values())]


def series_by(rows, key_field, date_field="date", value_field="value"):
    out = {}
    for r in rows:
        try:
            out.setdefault(r[key_field], {})[r[date_field]] = float(r[value_field])
        except (KeyError, TypeError, ValueError):
            continue
    return out
