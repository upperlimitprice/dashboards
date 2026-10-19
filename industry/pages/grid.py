"""미국 전력망 수요 — EIA-930 일별 지역 수요 (데이터센터·전기화 수요 모니터)."""
from datetime import date, timedelta

from core import collect as C
from core import page as P
from core import series as S
from core.sources import eia

KEY = "grid"
TITLE = "🔌 미국 전력망 수요"
SUBTITLE = "EIA-930 일별 수요 — 미국 본토·주요 ISO, 28일 합계 YoY · 연중 동기 비교"
NEEDS = ["EIA_API_KEY"]

REGIONS = [   # (EIA respondent, 표시명)
    ("US48", "미국 본토"), ("PJM", "PJM (버지니아 포함)"), ("ERCO", "ERCOT (텍사스)"),
    ("MISO", "MISO (중부)"), ("SWPP", "SPP (남부평원)"), ("CISO", "CAISO (캘리포니아)"),
    ("NYIS", "NYISO (뉴욕)"), ("ISNE", "ISO-NE (뉴잉글랜드)"), ("SOCO", "Southern (조지아 등)"),
]


def collect(prev):
    raw = C.new(prev)
    start = (date.today() - timedelta(days=365 * 4 + 40)).isoformat()

    def fetch():
        rows = eia.fetch("electricity/rto/daily-region-data/data/", [
            ("frequency", "daily"), ("data[0]", "value"), ("start", start),
            ("sort[0][column]", "period"), ("sort[0][direction]", "asc"),
            *eia.facets("respondent", [r for r, _ in REGIONS]),
            *eia.facets("type", ["D"]), *eia.facets("timezone", ["Eastern"])])
        return eia.series(rows, "respondent")      # MWh/일
    C.attempt(raw, "demand", "EIA-930 일별 수요", fetch)
    return C.finish(raw)


def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "EIA Hourly Electric Grid Monitor (EIA-930)", "https://www.eia.gov/electricity/gridmonitor/")
    d = raw.get("demand") or {}
    if not d:
        return page

    def r28(code):
        return S.rolling({k: v / 1000 for k, v in d.get(code, {}).items()}, 28, "sum")   # GWh

    us = d.get("US48", {})
    if us:
        k, _ = S.last(us)
        roll = r28("US48")
        yoy = S.yoy_pct(roll)
        P.kpi(page, "미국 본토 28일 수요", roll.get(k, 0) / 1000, "TWh", yoy.get(k), asof=k)
        ytd_now = sum(v for kk, v in us.items() if kk[:4] == k[:4] and kk <= k)
        ytd_ly = sum(v for kk, v in us.items() if kk[:4] == str(int(k[:4]) - 1) and kk <= S.shift_year(k))
        if ytd_ly:
            P.kpi(page, "연초 이후 누적 수요", ytd_now / 1e6, "TWh", (ytd_now / ytd_ly - 1) * 100, "YTD YoY")
        peak_k = max(us, key=us.get)
        P.kpi(page, "기간 내 최대 일수요", us[peak_k] / 1000, "GWh", asof=peak_k)
    for code, label in REGIONS[1:3]:
        roll = r28(code)
        k, v = S.last(roll)
        if k:
            P.kpi(page, f"{label.split(' ')[0]} 28일 수요", v / 1000, "TWh", S.yoy_pct(roll).get(k), asof=k)

    # 1) 연중 동기 비교 — 미국 본토 7일 평균, 올해 vs 작년 vs 재작년
    ma7 = S.rolling({k: v / 1000 for k, v in us.items()}, 7)
    if ma7:
        y0 = int(max(ma7)[:4])
        mmdd = sorted({k[5:] for k in ma7 if k[5:] != "02-29"})
        P.chart(page, "seasonal", "미국 본토 일수요 7일 평균 — 연도별 겹쳐보기", mmdd,
                [P.series(str(y), [None if f"{y}-{md}" not in ma7 else round(ma7[f"{y}-{md}"], 1) for md in mmdd],
                          slot=i) for i, y in enumerate([y0, y0 - 1, y0 - 2])], unit="GWh/일", window=400)
    # 2) 지역별 28일 합계 YoY
    keys = None
    ser = []
    for i, (code, label) in enumerate(REGIONS):
        yoy = S.yoy_pct(r28(code))
        if not yoy:
            continue
        keys = sorted(set(keys or []) | set(yoy))
        ser.append((label, yoy, i))
    if keys:
        keys = keys[::7] if len(keys) > 200 else keys     # 주 1회 샘플로 가독성 확보
        P.chart(page, "yoy", "지역별 28일 수요 YoY", keys,
                [P.series(lbl, S.align(keys, y, 1), slot=i if i < 8 else -1) for lbl, y, i in ser[:8]],
                unit="%", note="기온 영향이 크므로 단일 월보다 추세로 볼 것", window=60)
    # 3) 월별 수요 (미국 본토)
    mon = S.daily_to_monthly({k: v / 1e6 for k, v in us.items()})
    mk = sorted(mon)[:-1]                 # 진행 중인 월 제외
    if mk:
        P.chart(page, "monthly", "미국 본토 월별 수요", mk, [P.series("수요", S.align(mk, mon, 1))],
                kind="bar", unit="TWh", window=36)
    rows = []
    for code, label in REGIONS:
        roll = r28(code)
        k, v = S.last(roll)
        if not k:
            continue
        yt = S.yoy_pct(roll)
        rows.append([label, k, round(v, 0), round(yt.get(k, 0), 1),
                     round(max(d[code].values()) / 1000, 1)])
    P.table(page, "지역별 요약", ["지역", "기준일", "28일 수요(GWh)", "YoY(%)", "최대 일수요(GWh)"], rows)
    return page
