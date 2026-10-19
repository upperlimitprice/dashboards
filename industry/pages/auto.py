"""한국 자동차 수출 — 관세청 HS별 월간 (승용차·전기차·하이브리드·부품·배터리)."""
from core import collect as C
from core import page as P
from core import series as S
from core import trade as T
from core.sources import customs

KEY = "auto"
TITLE = "🚗 한국 자동차 수출"
SUBTITLE = "관세청 품목별 수출 — 승용차·전기차(BEV)·하이브리드·부품·2차전지, 월별 금액·YoY·단가($/kg)"
NEEDS = ["DATA_GO_KR_KEY"]

ITEMS = [   # (키, HS, 표시명, 시작연도) — HS2022 세분류(8703.40~80)는 2022년부터
    ("car", "8703", "승용차 전체", 2019),
    ("bev", "870380", "전기차(BEV)", 2022),
    ("hev", "870340", "하이브리드(가솔린)", 2022),
    ("phev", "870360", "플러그인 하이브리드(가솔린)", 2022),
    ("parts", "8708", "자동차 부품", 2019),
    ("battery", "850760", "리튬이온 배터리", 2019),
]
EOK = 1e-8   # USD → 억 달러


def collect(prev):
    raw = C.new(prev)
    for key, hs, label, start in ITEMS:
        C.attempt(raw, key, f"관세청 {hs} {label}", customs.monthly, hs, start)
    return C.finish(raw)


def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "관세청 품목별 수출입실적 (공공데이터포털)", "https://www.data.go.kr/data/15100475/openapi.do")
    exp = {k: T.field(raw.get(k), "exp_usd", EOK) for k, *_ in ITEMS}
    car = exp["car"]
    if not car:
        return page
    hyb = S.add(exp["hev"], exp["phev"]) if exp["hev"] and exp["phev"] else exp["hev"]
    k, v = S.last(car)
    P.kpi(page, "승용차 수출", v, "억$", S.yoy_pct(car).get(k), asof=k)
    share = S.ratio(exp["bev"], car, 100)
    if k in share:
        prev = share.get(S.shift_year(k))
        P.kpi(page, "전기차 비중", share[k], "%", None if prev is None else share[k] - prev,
              "YoY", delta_unit="%p")
    for key, label in (("bev", "전기차 수출"), ("parts", "부품 수출"), ("battery", "배터리 수출")):
        kk, vv = S.last(exp[key])
        if kk:
            P.kpi(page, label, vv, "억$", S.yoy_pct(exp[key]).get(kk), asof=kk)

    # 1) 승용차 구성
    keys = sorted(k for k in car if k >= "2022-01")
    ice = {k: car[k] - exp["bev"].get(k, 0) - hyb.get(k, 0) for k in keys}
    P.chart(page, "mix", "승용차 수출 구성 (BEV · 하이브리드 · 내연기관 등)", keys, [
        P.series("전기차(BEV)", S.align(keys, exp["bev"]), slot=0),
        P.series("하이브리드+PHEV", S.align(keys, hyb), slot=2),
        P.series("내연기관 등", S.align(keys, ice), slot=-1)], kind="bar", unit="억$", stack=True, window=36)
    # 2) YoY (3개월 이동평균)
    yk = sorted(set().union(*(S.yoy_pct(S.rolling(exp[x], 3)) for x in ("car", "parts", "battery"))))
    P.chart(page, "yoy", "수출 YoY (3개월 이동평균)", yk, [
        P.series(lbl, S.align(yk, S.yoy_pct(S.rolling(exp[x], 3)), 1), slot=i)
        for i, (x, lbl) in enumerate((("car", "승용차"), ("parts", "부품"), ("battery", "배터리")))],
        unit="%", window=48)
    # 3) 단가 프록시
    up_car, up_bev = T.unit_price(raw.get("car")), T.unit_price(raw.get("bev"))
    uk = sorted(set(up_car) | set(up_bev))
    P.chart(page, "price", "수출 단가 프록시 ($/kg)", uk, [
        P.series("승용차 전체", S.align(uk, up_car), slot=0),
        P.series("전기차(BEV)", S.align(uk, up_bev), slot=1)], unit="$/kg", window=48,
        note="중량당 금액 — 대수 데이터가 없어 믹스·판가 변화를 함께 반영")
    # 4) 부품·배터리 절대액
    pk = sorted(set(exp["parts"]) | set(exp["battery"]))
    P.chart(page, "parts", "부품·배터리 월 수출", pk, [
        P.series("자동차 부품", S.align(pk, exp["parts"]), slot=3),
        P.series("리튬이온 배터리", S.align(pk, exp["battery"]), slot=4)], unit="억$", window=48)

    rows = []
    for m in sorted(car)[-13:][::-1]:
        rows.append([m] + [round(exp[x].get(m, 0), 1) if m in exp[x] else "—"
                           for x in ("car", "bev", "hev", "phev", "parts", "battery")])
    P.table(page, "최근 13개월 (억 달러)", ["월", "승용차", "BEV", "HEV", "PHEV", "부품", "배터리"], rows)
    return page
