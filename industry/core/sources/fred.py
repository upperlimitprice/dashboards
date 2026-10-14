"""FRED — 키 없는 CSV 다운로드 (fredgraph.csv). 월별 값은 'YYYY-MM' 키로 정규화."""
import csv
import io

from ..http import get_text

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def parse_csv(text, monthly=True):
    rows = list(csv.reader(io.StringIO(text)))
    out = {}
    for r in rows[1:]:
        if len(r) < 2 or r[1] in ("", "."):
            continue
        try:
            out[r[0][:7] if monthly else r[0]] = float(r[1])
        except ValueError:
            continue
    return out


def series(sid, monthly=True, start="2015-01-01"):
    return parse_csv(get_text(URL, [("id", sid), ("cosd", start)]), monthly)
