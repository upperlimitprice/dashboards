"""미국·글로벌 화물 — Cass 화물지수·운송 PPI·철도 물동량·GSCPI (FRED·뉴욕연은, 키 불필요)."""
from core import collect as C
from core import manual
from core import page as P
from core import series as S
from core.sources import fred, gscpi

KEY = "freight"
TITLE = "🚛 화물·물류 사이클"
SUBTITLE = "Cass 물동량·운임지출 · 트럭/해운/항공/철도 PPI · 철도 화차·인터모달 · 공급망 압력(GSCPI)"
NEEDS = []

FRED = [  # (FRED ID, 표시명)
    ("FRGSHPUSM649NCIS", "Cass 물동량"),
    ("FRGEXPUSM649NCIS", "Cass 운임지출"),
    ("TSIFRGHT", "화물운송서비스지수(TSI)"),
    ("PCU484121484121", "PPI 장거리 트럭(TL)"),
    ("PCU483111483111", "PPI 원양 해운"),
    ("PCU481112481112", "PPI 항공 화물"),
    ("PCU482111482111", "PPI 철도"),
    ("RAILFRTCARLOADSD11", "철도 화차"),
    ("RAILFRTINTERMODALD11", "철도 인터모달"),
]


def collect(prev):
    raw = C.new(prev)
    for sid, label in FRED:
        C.attempt(raw, sid, f"FRED {sid}", fred.series, sid)
    C.attempt(raw, "gscpi", "뉴욕연은 GSCPI", gscpi.series)
    return C.finish(raw)


def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "FRED (St. Louis Fed)", "https://fred.stlouisfed.org/")
    P.source(page, "NY Fed Global Supply Chain Pressure Index", "https://www.newyorkfed.org/research/policy/gscpi")
    g = {sid: raw.get(sid) or {} for sid, _ in FRED}
    ship, spend = g["FRGSHPUSM649NCIS"], g["FRGEXPUSM649NCIS"]
    rate = S.ratio(spend, ship)                         # 운임지출 ÷ 물동량 = 암묵적 운임
    for d, label in ((ship, "Cass 물동량"), (spend, "Cass 운임지출"), (rate, "암묵적 운임(지출÷물동량)")):
        k, v = S.last(d)
        if k:
            P.kpi(page, label + " YoY", S.yoy_pct(d).get(k), "%", asof=k)
    k, v = S.last(raw.get("gscpi") or {})
    if k:
        P.kpi(page, "공급망 압력 GSCPI", v, "σ", asof=k, digits=2)
    k, v = S.last(g["PCU483111483111"])
    if k:
        P.kpi(page, "원양 해운 PPI", v, "", S.yoy_pct(g["PCU483111483111"]).get(k), asof=k)

    ks = sorted(k for k in set(S.yoy_pct(ship)) | set(S.yoy_pct(spend)) if k >= "2016-01")
    P.chart(page, "cass", "Cass 화물지수 YoY", ks, [
        P.series("물동량", S.align(ks, S.yoy_pct(ship), 1), slot=0),
        P.series("운임지출", S.align(ks, S.yoy_pct(spend), 1), slot=1),
        P.series("암묵적 운임", S.align(ks, S.yoy_pct(rate), 1), slot=2)], unit="%", window=60,
        note="물동량↓·운임지출↓ 동반 = 화물 경기 침체(Freight recession), 동반 반등이 바닥 신호")
    ppi_ids = ["PCU484121484121", "PCU483111483111", "PCU481112481112", "PCU482111482111"]
    common = sorted(set.intersection(*(set(g[i]) for i in ppi_ids if g[i])) if any(g[i] for i in ppi_ids) else [])
    if common:
        base = common[max(0, len(common) - 61)]
        pk = [k for k in common if k >= base]
        P.chart(page, "ppi", f"운송 모드별 PPI ({base} = 100)", pk,
                [P.series(lbl, S.align(pk, S.index_to(S.since(g[i], base), base), 1), slot=j + 3)
                 for j, (i, lbl) in enumerate((x for x in FRED if x[0] in ppi_ids))], unit="지수", window=61)
    rk = sorted(k for k in set(S.yoy_pct(g["RAILFRTCARLOADSD11"])) | set(S.yoy_pct(g["RAILFRTINTERMODALD11"])) if k >= "2016-01")
    P.chart(page, "rail", "철도 물동량 YoY", rk, [
        P.series("화차(벌크·산업재)", S.align(rk, S.yoy_pct(g["RAILFRTCARLOADSD11"]), 1), slot=0),
        P.series("인터모달(컨테이너·소비재)", S.align(rk, S.yoy_pct(g["RAILFRTINTERMODALD11"]), 1), slot=1)],
        unit="%", window=60)
    gs = raw.get("gscpi") or {}
    gk = sorted(k for k in gs if k >= "2010-01")
    P.chart(page, "gscpi", "글로벌 공급망 압력지수 (GSCPI)", gk, [P.series("GSCPI", S.align(gk, gs))],
            unit="σ", window=120, note="0 = 장기 평균, 단위는 표준편차")
    tsi = g["TSIFRGHT"]
    tk = sorted(k for k in tsi if k >= "2010-01")
    P.chart(page, "tsi", "화물운송서비스지수 (TSI, 계절조정)", tk, [P.series("TSI", S.align(tk, tsi, 1))],
            unit="지수", window=120)

    spot = manual.series_by(manual.read("freight_spot.csv"), "index")
    if spot:
        sk = sorted(set().union(*spot.values()))
        P.chart(page, "spot", "컨테이너 스팟 운임 (SCFI·Drewry WCI, 매일 자동 누적)", sk,
                [P.series(n, S.align(sk, d, 0), slot=i) for i, (n, d) in enumerate(spot.items())], unit="")
    page["notes"].append("SCFI·CCFI·BDI 일별 지수는 기존 '해상 운임 지수' 대시보드(shipping.html)를 함께 보세요. "
                         "WCI 등 유료 지수를 직접 기록하려면 manual/freight_spot.csv 에 추가하면 이 페이지에 그려집니다.")
    return page
