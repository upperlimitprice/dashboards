"""태양광 — 미국 설치·파이프라인(EIA-860M) · 발전 비중(EIA) · 한국 셀/모듈 교역(관세청) · 가격(수동)."""
from core import collect as C
from core import manual
from core import page as P
from core import series as S
from core import trade as T
from core.sources import customs, eia, eia860m

KEY = "solar"
TITLE = "☀️ 태양광 수요·교역"
SUBTITLE = "미국 태양광·ESS 신규 설치와 계획 파이프라인 · 발전 비중 · 한국 셀·모듈 수출입"
NEEDS = ["EIA_API_KEY(발전량)", "DATA_GO_KR_KEY(교역)"]

MUSD = 1e-6


def _solar_subset(s):
    def pick(by_year):
        return {y: {"태양광": d.get("태양광", 0), "ESS": d.get("ESS", 0)} for y, d in by_year.items()}
    return {"file_month": s["file_month"],
            "op": {g: s["operating_by_tech"].get(g, 0) for g in ("태양광", "ESS")},
            "adds": pick(s["additions_by_year"]), "planned": pick(s["planned_by_year"]),
            "planned_uc": pick(s["planned_uc_by_year"])}


def collect(prev):
    raw = C.new(prev)

    def us_pipeline():
        content, ym = eia860m.latest()          # gen_capacity 와 같은 파일 — 24시간 캐시 공유
        return _solar_subset({"file_month": ym, **eia860m.summarize(eia860m.parse(content))})
    C.attempt(raw, "us860m", "EIA-860M", us_pipeline)

    def generation():
        rows = eia.fetch("electricity/electric-power-operational-data/data/", [
            ("frequency", "monthly"), ("data[0]", "generation"), ("start", "2015-01"),
            *eia.facets("location", ["US"]), *eia.facets("sectorid", ["99"]),
            *eia.facets("fueltypeid", ["SUN", "ALL"])])
        return eia.series(rows, "fueltypeid", "generation")     # 천 MWh
    C.attempt(raw, "gen", "EIA 발전량", generation)
    C.attempt(raw, "kr_module", "관세청 HS 8541.43 모듈", customs.monthly, "854143", 2022)
    C.attempt(raw, "kr_cell", "관세청 HS 8541.42 셀", customs.monthly, "854142", 2022)
    return C.finish(raw)


def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "EIA-860M", "https://www.eia.gov/electricity/data/eia860m/")
    P.source(page, "EIA Electric Power Operational Data", "https://www.eia.gov/opendata/")
    P.source(page, "관세청 품목별 수출입실적", "https://www.data.go.kr/data/15100475/openapi.do")
    s = raw.get("us860m")
    if s:
        this_year = int(s["file_month"][:4])
        P.kpi(page, "미국 태양광 가동 용량", s["op"]["태양광"] / 1000, "GW", asof=f"EIA-860M {s['file_month']}")
        P.kpi(page, "미국 ESS 가동 용량", s["op"]["ESS"] / 1000, "GW")
        pl = s["planned"].get(str(this_year), {})
        P.kpi(page, f"{this_year}년 태양광 계획 추가", pl.get("태양광", 0) / 1000, "GW")
        years = [str(y) for y in range(this_year - 10, this_year + 5)]

        def val(y, g):
            if int(y) < this_year:
                return s["adds"].get(y, {}).get(g, 0) / 1000
            return s["planned"].get(y, {}).get(g, 0) / 1000 + (s["adds"].get(y, {}).get(g, 0) / 1000 if int(y) == this_year else 0)
        P.chart(page, "us_adds", "미국 연간 신규 — 실적 + 계획", years, [
            P.series("태양광", [round(val(y, "태양광"), 2) for y in years], slot=0),
            P.series("ESS", [round(val(y, "ESS"), 2) for y in years], slot=1)], kind="bar", unit="GW", stack=True,
            note=f"{this_year}년 = 연초 이후 실적 + 잔여 계획, 이후 연도는 사업자 제출 계획(전체 상태)")
        fy = [str(y) for y in range(this_year, this_year + 5)]
        P.chart(page, "us_uc", "계획 중 공사 착수(U·V) 물량", fy, [
            P.series("태양광", [round(s["planned_uc"].get(y, {}).get("태양광", 0) / 1000, 2) for y in fy], slot=0),
            P.series("ESS", [round(s["planned_uc"].get(y, {}).get("ESS", 0) / 1000, 2) for y in fy], slot=1)],
            kind="bar", unit="GW", stack=True)
    gen = raw.get("gen") or {}
    sun, tot = gen.get("SUN", {}), gen.get("ALL", {})
    if sun:
        share12 = S.ratio(S.rolling(sun, 12, "sum"), S.rolling(tot, 12, "sum"), 100)
        k, v = S.last(share12)
        if k:
            P.kpi(page, "미국 발전 중 태양광 비중(12M)", v, "%", asof=k)
        gk = sorted(k for k in sun if k >= "2018-01")
        P.chart(page, "gen", "미국 태양광 발전량 (유틸리티 규모)", gk,
                [P.series("태양광 발전", S.align(gk, {k: v / 1000 for k, v in sun.items()}, 1), kind="bar")],
                unit="TWh", window=48)
        sk = sorted(k for k in share12 if k >= "2018-01")
        P.chart(page, "share", "태양광 발전 비중 (12개월 합계)", sk, [P.series("비중", S.align(sk, share12, 2))], unit="%")
    mod, cell = raw.get("kr_module") or {}, raw.get("kr_cell") or {}
    if mod:
        me, mi = T.field(mod, "exp_usd", MUSD), T.field(mod, "imp_usd", MUSD)
        ce = T.field(cell, "exp_usd", MUSD)
        k, v = S.last(me)
        P.kpi(page, "한국 모듈 수출", v, "백만$", S.yoy_pct(me).get(k), asof=k)
        tk = sorted(set(me) | set(mi))
        P.chart(page, "kr", "한국 태양광 모듈·셀 교역", tk, [
            P.series("모듈 수출", S.align(tk, me, 1), slot=0),
            P.series("모듈 수입", S.align(tk, mi, 1), slot=1),
            P.series("셀 수출", S.align(tk, ce, 1), slot=2)], unit="백만$", window=48)
        up = T.unit_price(mod, "imp")
        uk = sorted(up)
        P.chart(page, "kr_price", "한국 모듈 수입 단가 ($/kg)", uk, [P.series("수입 단가", S.align(uk, up, 2))],
                unit="$/kg", note="중국산 모듈 가격 흐름의 프록시")
    price = manual.series_by(manual.read("solar_prices.csv"), "item")
    if price:
        pk = sorted(set().union(*price.values()))
        P.chart(page, "price", "밸류체인 스팟 가격 (InfoLink 주간·SunSirs 일별, 자동)", pk,
                [P.series(n, S.align(pk, d, 3), slot=i if i < 8 else -1) for i, (n, d) in enumerate(price.items())])
    page["notes"].append("폴리실리콘·웨이퍼·셀·모듈 주간 스팟가는 기존 '태양광 밸류체인 스팟가격'(solar-price.html)을 보세요. "
                         "직접 기록하려면 manual/solar_prices.csv 에 추가하면 됩니다.")
    return page
