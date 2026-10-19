"""데이터센터 투자 — 하이퍼스케일러 분기 capex(SEC XBRL) + 데이터센터 밀집 주 상업용 전력 판매(EIA)."""
from core import collect as C
from core import page as P
from core import series as S
from core.sources import eia, sec

KEY = "datacenter"
TITLE = "🏢 데이터센터 투자 사이클"
SUBTITLE = "하이퍼스케일러 분기 capex(SEC 공시) · TTM · YoY + 버지니아·텍사스 등 상업용 전력 판매(EIA)"
NEEDS = ["SEC_USER_AGENT", "EIA_API_KEY(선택)"]

PPE = "PaymentsToAcquirePropertyPlantAndEquipment"
COMPANIES = [  # (티커, CIK, 이름, concept 우선순위)
    ("MSFT", 789019, "Microsoft", [PPE]),
    ("AMZN", 1018724, "Amazon", ["PaymentsToAcquireProductiveAssets", PPE]),
    ("GOOGL", 1652044, "Alphabet", [PPE]),
    ("META", 1326801, "Meta", [PPE]),
    ("ORCL", 1341439, "Oracle", [PPE]),
    ("CRWV", 1769628, "CoreWeave", [PPE]),
]
BIG4 = ("MSFT", "AMZN", "GOOGL", "META")
STATES = [("VA", "버지니아"), ("TX", "텍사스"), ("GA", "조지아"), ("AZ", "애리조나"), ("OH", "오하이오"), ("US", "미국 전체")]


def collect(prev):
    raw = C.new(prev)
    capex = {}
    for t, cik, name, concepts in COMPANIES:
        q = C.attempt(raw, f"capex_{t}", f"SEC {t}", sec.quarterly_concepts, cik, concepts)
        if q:
            capex[t] = {S.quarter_of(e): v for e, v in q.items()}   # 분기말 날짜 → 달력 분기
        raw.pop(f"capex_{t}", None)
    raw["capex"] = capex or raw["_prev"].get("capex", {})

    def retail():
        rows = eia.fetch("electricity/retail-sales/data/", [
            ("frequency", "monthly"), ("data[0]", "sales"), ("start", "2015-01"),
            *eia.facets("stateid", [s for s, _ in STATES]), *eia.facets("sectorid", ["COM"])])
        return eia.series(rows, "stateid", "sales")      # 백만 kWh
    C.attempt(raw, "retail", "EIA 상업용 전력 판매", retail)
    return C.finish(raw)


def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "SEC EDGAR XBRL API", "https://www.sec.gov/search-filings/edgar-application-programming-interfaces")
    P.source(page, "EIA Electricity Retail Sales", "https://www.eia.gov/electricity/data/browser/")
    cap = {t: {q: v / 1e9 for q, v in d.items()} for t, d in (raw.get("capex") or {}).items()}
    names = {t: n for t, _, n, _ in COMPANIES}
    if cap:
        allq = sorted(set().union(*cap.values()))
        full = [q for q in allq if all(q in cap.get(t, {}) for t in BIG4)]
        total = {q: sum(cap[t][q] for t in BIG4) for q in full}
        ttm = S.rolling(total, 4, "sum")
        if full:
            q = full[-1]
            P.kpi(page, "빅4 분기 capex", total[q], "$B", S.yoy_pct(total).get(q), asof=q)
        if ttm:
            q, v = S.last(ttm)
            P.kpi(page, "빅4 TTM capex", v, "$B", S.yoy_pct(ttm).get(q), asof=q)
        for t in ("MSFT", "ORCL"):
            q, v = S.last(cap.get(t, {}))
            if q:
                P.kpi(page, f"{names[t]} 분기 capex", v, "$B", S.yoy_pct(cap[t]).get(q), asof=q)

        qs = [q for q in allq if q >= "2019Q1"]
        P.chart(page, "capex", "분기 capex — 회사별 (달력 분기 기준)", qs,
                [P.series(names[t], S.align(qs, cap.get(t, {})), slot=i) for i, (t, *_) in enumerate(COMPANIES)],
                kind="bar", unit="$B", stack=True, window=16)
        ttm_by = {t: S.rolling(cap.get(t, {}), 4, "sum") for t, *_ in COMPANIES}
        P.chart(page, "ttm", "TTM capex — 회사별", qs,
                [P.series(names[t], S.align(qs, ttm_by[t]), slot=i) for i, (t, *_) in enumerate(COMPANIES)],
                unit="$B", window=24)
        yk = [q for q in full if q >= "2020Q1"]
        P.chart(page, "yoy", "빅4 합계 capex YoY", yk,
                [P.series("분기 YoY", S.align(yk, S.yoy_pct(total), 1), kind="bar", slot=0)], unit="%", window=20)
        rows = []
        for t, *_ in COMPANIES:
            q, v = S.last(cap.get(t, {}))
            if q:
                rows.append([names[t], q, round(v, 2), round(S.yoy_pct(cap[t]).get(q, 0), 1),
                             round(ttm_by[t].get(q, 0), 1)])
        P.table(page, "회사별 최신 분기", ["회사", "분기", "capex($B)", "YoY(%)", "TTM($B)"], rows,
                note="현금흐름표 유형자산 취득액 기준 — 금융리스로 확보한 설비는 미포함 (MSFT·ORCL 등은 실제 투자 규모가 더 큼)")

    retail = raw.get("retail") or {}
    if retail:
        r12 = {s: S.rolling(retail.get(s, {}), 12, "sum") for s, _ in STATES}
        ks = sorted(k for k in set().union(*(S.yoy_pct(v) for v in r12.values())) if k >= "2018-01")
        P.chart(page, "power_yoy", "상업용 전력 판매 12개월 합계 YoY — 데이터센터 밀집 주", ks,
                [P.series(lbl, S.align(ks, S.yoy_pct(r12[s]), 1), slot=i if s != "US" else -1)
                 for i, (s, lbl) in enumerate(STATES)], unit="%", window=60,
                note="데이터센터는 대부분 상업용(COM) 부문으로 집계 — 버지니아 북부가 세계 최대 밀집지")
        va = retail.get("VA", {})
        vk = sorted(va)
        P.chart(page, "va", "버지니아 상업용 전력 판매 (월)", vk, [P.series("버지니아", S.align(vk, {k: v / 1000 for k, v in va.items()}), kind="bar")],
                unit="TWh", window=48)
        k, _ = S.last(r12.get("VA", {}))
        if k:
            P.kpi(page, "버지니아 상업용 전력 12M", r12["VA"][k] / 1000, "TWh", S.yoy_pct(r12["VA"]).get(k), asof=k)
    return page
