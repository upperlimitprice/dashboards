"""시계열 유틸. 시계열은 {키: 값} dict — 월별 'YYYY-MM', 일별 'YYYY-MM-DD', 분기 'YYYYQn'."""
from datetime import date


def sorted_items(d):
    return sorted(d.items())


def last(d):
    if not d:
        return None, None
    k = max(d)
    return k, d[k]


def shift_year(key, years=1):
    if "Q" in key:
        y, q = key.split("Q")
        return f"{int(y) - years}Q{q}"
    return f"{int(key[:4]) - years}{key[4:]}"


def yoy_pct(d):
    out = {}
    for k, v in d.items():
        p = d.get(shift_year(k))
        if v is not None and p:
            out[k] = (v / p - 1) * 100
    return out


def rolling(d, n, fn="mean"):
    keys = sorted(d)
    out = {}
    for i in range(n - 1, len(keys)):
        win = [d[k] for k in keys[i - n + 1:i + 1] if d[k] is not None]
        if len(win) == n:
            out[keys[i]] = sum(win) / n if fn == "mean" else sum(win)
    return out


def ratio(a, b, scale=1.0):
    return {k: a[k] / b[k] * scale for k in a if k in b and b[k]}


def add(*ds):
    keys = set.intersection(*(set(d) for d in ds)) if ds else set()
    return {k: sum(d[k] for d in ds) for k in keys}


def sub(a, b):
    return {k: a[k] - b[k] for k in a if k in b}


def index_to(d, base_key=None):
    """base_key(없으면 첫 값) = 100 으로 지수화."""
    if not d:
        return {}
    keys = sorted(d)
    base_key = base_key if base_key in d else keys[0]
    b = d[base_key]
    return {k: d[k] / b * 100 for k in keys} if b else {}


def since(d, start):
    return {k: v for k, v in d.items() if k >= start}


def align(keys, d, nd=2):
    return [None if d.get(k) is None else round(d[k], nd) for k in keys]


def quarter_of(iso):
    y, m = int(iso[:4]), int(iso[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def months_back(n, today=None):
    today = today or date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def daily_to_monthly(d, fn="sum"):
    acc = {}
    for k, v in d.items():
        if v is None:
            continue
        acc.setdefault(k[:7], []).append(v)
    return {k: (sum(v) if fn == "sum" else sum(v) / len(v)) for k, v in acc.items()}
