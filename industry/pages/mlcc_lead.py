"""MLCC 사이클 선행지표 — 한국 MLCC 수출(관세청) · 대만 수동부품사 월매출(TWSE) · 리드타임(수동 입력)."""
from core import collect as C
from core import manual
from core import page as P
from core import series as S
from core import trade as T
from core.sources import customs, twse

KEY = "mlcc_lead"
TITLE = "🧱 MLCC 사이클 선행지표"
SUBTITLE = "한국 MLCC(HS 8532.24) 수출·단가 · 대만 Yageo·Walsin·Holy Stone 월매출 · 리드타임 기록"
NEEDS = ["DATA_GO_KR_KEY"]

HS = "853224"        # 적층 세라믹 콘덴서(MLCC)
TW = {"2327": "Yageo(國巨)", "2492": "Walsin Tech(華新科)", "3026": "Holy Stone(禾伸堂)"}
MUSD = 1e-6


def collect(prev):
    raw = C.new(prev)
    C.attempt(raw, "kr_mlcc", "관세청 HS 8532.24", customs.monthly, HS, 2018)
    latest = C.attempt(raw, "tw_latest", "TWSE 월매출", twse.monthly_revenue, list(TW))
    # TWSE OpenAPI 는 최신 1개월만 제공 → 실행할 때마다 이력에 누적
    hist = {c: dict(v) for c, v in raw["_prev"].get("tw_history", {}).items()}
    for code, r in (latest or {}).items():
        hist.setdefault(code, {})[r["ym"]] = {"rev": r["rev"], "yoy": r["yoy"], "mom": r["mom"]}
    raw["tw_history"] = hist
    return C.finish(raw)


def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "관세청 품목별 수출입실적 (공공데이터포털)", "https://www.data.go.kr/data/15100475/openapi.do")
    P.source(page, "TWSE OpenAPI — 上市公司每月營業收入", "https://openapi.twse.com.tw/")
    kr = raw.get("kr_mlcc") or {}
    exp = T.field(kr, "exp_usd", MUSD)
    imp = T.field(kr, "imp_usd", MUSD)
    up = S.rolling(T.unit_price(kr), 3)
    k, v = S.last(exp)
    if k:
        P.kpi(page, "한국 MLCC 수출", v, "백만$", S.yoy_pct(exp).get(k), asof=k)
        uk, uv = S.last(up)
        P.kpi(page, "수출 단가(3MMA)", uv, "$/kg", S.yoy_pct(up).get(uk), asof=uk, digits=0)
    for code in ("2327", "2492"):
        r = (raw.get("tw_latest") or {}).get(code)
        if r:
            P.kpi(page, f"{TW[code].split('(')[0]} 월매출", (r["rev"] or 0) / 1e6, "십억TWD", r["yoy"], asof=r["ym"], digits=2)
    lead = manual.read("mlcc_leadtime.csv")
    if lead:
        lt = sorted(lead, key=lambda r: r["date"])[-1]
        try:
            P.kpi(page, f"리드타임 {lt['vendor']} {lt['category']}",
                  (float(lt["weeks_min"]) + float(lt["weeks_max"])) / 2, "주", asof=lt["date"])
        except (KeyError, ValueError):
            pass

    ks = sorted(k for k in exp if k >= "2019-01")
    P.chart(page, "exp", "한국 MLCC 월 수출·수입", ks, [
        P.series("수출", S.align(ks, exp, 1), kind="bar", slot=0),
        P.series("수입", S.align(ks, imp, 1), slot=1)], unit="백만$", window=48)
    e3 = S.rolling(exp, 3)
    yk = sorted(k for k in S.yoy_pct(e3) if k >= "2019-01")
    P.chart(page, "yoy", "MLCC 수출 YoY (3개월 이동평균) · 단가 YoY", yk, [
        P.series("수출금액 YoY", S.align(yk, S.yoy_pct(e3), 1), slot=0),
        P.series("단가($/kg) YoY", S.align(yk, S.yoy_pct(up), 1), slot=2)], unit="%", window=60,
        note="금액 YoY가 단가 YoY보다 먼저 꺾이면 물량 주도, 단가가 따라 오르면 업황 타이트")

    hist = raw.get("tw_history") or {}
    hk = sorted(set().union(*(set(d) for d in hist.values()))) if hist else []
    if len(hk) >= 2:
        P.chart(page, "tw", "대만 수동부품사 월매출 YoY", hk,
                [P.series(TW[c], [hist.get(c, {}).get(m, {}).get("yoy") for m in hk], slot=i)
                 for i, c in enumerate(TW)], unit="%", note="매 실행마다 최신월을 누적 — 이력이 쌓일수록 길어짐")
    rows = [[TW[c], r["ym"], round((r["rev"] or 0) / 1e3, 0), r["yoy"], r["mom"]]
            for c, r in (raw.get("tw_latest") or {}).items()]
    P.table(page, "대만 최신 월매출", ["회사", "월", "매출(백만TWD)", "YoY(%)", "MoM(%)"], rows)

    if lead:
        by = {}
        for r in lead:
            try:
                by.setdefault(f"{r['vendor']} {r['category']}", {})[r["date"]] = (float(r["weeks_min"]) + float(r["weeks_max"])) / 2
            except (KeyError, ValueError):
                continue
        lk = sorted(set().union(*by.values()))
        P.chart(page, "lead", "MLCC 리드타임 (주, 범위 중간값)", lk,
                [P.series(n, S.align(lk, d, 1), slot=i if i < 8 else -1) for i, (n, d) in enumerate(by.items())],
                unit="주")
        P.table(page, "리드타임 기록 (최근 20건)", ["날짜", "업체", "품목", "최소(주)", "최대(주)", "출처"],
                [[r["date"], r["vendor"], r["category"], r["weeks_min"], r["weeks_max"], r.get("source", "")]
                 for r in sorted(lead, key=lambda r: r["date"], reverse=True)[:20]])
    page["notes"].append("MLCC 리드타임은 무료 공개 API가 없습니다. 유통사·증권사 자료에서 확인한 값을 "
                         "manual/mlcc_leadtime.csv 에 한 줄씩 추가하면 차트와 KPI에 반영됩니다.")
    page["notes"].append("관련: 전자부품 리드타임 트렌드(parts-trend.html), 트렌드포스 MLCC 전망(trendforce.html).")
    return page
