"""AI 데이터센터 전력 병목 → 전력기기 나우캐스트.

수요(EIA-930 일별 지역·존 수요) · 판매/요금(EIA retail-sales) · 공급(EIA-860M 계획 신규/폐지)
· 기기 가격(FRED PPI) · 한국 변압기 수출(관세청) 을 묶어 지역별 '전력 병목 점수'를 만든다.
"""
from datetime import date, timedelta

from core import collect as C
from core import page as P
from core import series as S
from core.env import load_env
from core.sources import customs, customs_country, eia, eia860m, fred

KEY = "power_nowcast"
TITLE = "⚡ AI 데이터센터 전력 병목 → 전력기기 나우캐스트"
SUBTITLE = ("데이터센터 밀집 지역 수요·피크·기저수요 vs 계획 발전설비 순증 → 변압기·차단기·가스터빈 수요 지속성 "
            "| HD현대일렉트릭·효성중공업·LS ELECTRIC·산일전기·제룡전기·GE버노바·지멘스에너지")
NEEDS = ["EIA_API_KEY", "DATA_GO_KR_KEY(선택)"]

# (코드, 표시명, EIA-930 소스, 응답자/존 코드들, 860M 필터(BA 코드들, 주 코드들 or None))
REGIONS = [
    ("DOM", "Dominion (버지니아)", "subba", ["DOM"], (["PJM"], ["VA"])),
    ("AEP", "AEP (오하이오 등)", "subba", ["AEP"], (["PJM"], ["OH"])),
    ("PJM", "PJM 전체", "ba", ["PJM"], (["PJM"], None)),
    ("ERCO", "ERCOT (텍사스)", "ba", ["ERCO"], (["ERCO"], None)),
    ("SOCO", "Southern (조지아)", "ba", ["SOCO"], (["SOCO"], None)),
    ("AZ", "애리조나 (APS+SRP)", "ba", ["AZPS", "SRP"], (["AZPS", "SRP"], None)),
    ("US48", "미국 본토 (비교)", "ba", ["US48"], (None, None)),
]
STATES = [("VA", "버지니아"), ("TX", "텍사스"), ("GA", "조지아"), ("AZ", "애리조나"), ("OH", "오하이오"), ("US", "미국 전체")]
PPI = [  # (FRED ID, 표시명) — BLS 생산자물가지수, 산업 기준
    ("PCU335311335311", "변압기 (전력·배전·특수)"),
    ("PCU335313335313", "개폐기·배전반 (차단기)"),
    ("PCU333611333611", "터빈·터빈발전기"),
]
HS_US = [("850423", "10MVA 초과 (대형 전력변압기)"), ("850422", "650kVA~10MVA (중형)"),
         ("850421", "650kVA 이하 (배전용)")]
# 계획 용량 → 피크 기여 유효용량 근사 계수 (ELCC/정격 대비, 지역 무관 단순 가정)
ELCC = {"가스": .9, "원전": .95, "석탄": .85, "수력": .8, "석유": .8, "ESS": .5, "풍력": .15, "태양광": .15, "기타": .5}
HORIZON = 3          # 향후 N개 연도 (860M 파일 연도 포함)
SLOT = {g: i for i, g in enumerate(eia860m.GROUP_ORDER[:8])}
SLOT["기타"] = -1


# ───────────────────────── 수집 ─────────────────────────
def _daily(route, facet, codes, start):
    rows = eia.fetch(route, [
        ("frequency", "daily"), ("data[0]", "value"), ("start", start),
        ("sort[0][column]", "period"), ("sort[0][direction]", "asc"),
        *eia.facets(facet, codes), *(eia.facets("type", ["D"]) if facet == "respondent" else []),
        *eia.facets("timezone", ["Eastern"])])
    return eia.series(rows, facet)          # MWh/일


def summarize_860m(sheets, file_year):
    """지역별 {add, add_uc, retire: {연도: {기술그룹: MW}}} — 향후 HORIZON 년만."""
    mw = "Nameplate Capacity (MW)"
    years = range(file_year, file_year + HORIZON)

    def match(r, flt):
        bas, sts = flt
        if r.get("Plant State") in ("AK", "HI"):
            return False
        if bas and r.get("Balancing Authority Code") not in bas:
            return False
        return not sts or r.get("Plant State") in sts

    def acc(dst, y, r):
        g = eia860m.tech_group(r.get("Technology"))
        dst.setdefault(str(y), {}).setdefault(g, 0.0)
        dst[str(y)][g] += float(r[mw])

    out = {}
    for code, _, _, _, flt in REGIONS:
        d = out[code] = {"add": {}, "add_uc": {}, "retire": {}}
        for r in sheets.get("Planned", []):
            y = r.get("Planned Operation Year")
            if isinstance(y, (int, float)) and int(y) in years and match(r, flt):
                acc(d["add"], int(y), r)
                if eia860m.status_code(r.get("Status")) in eia860m.UNDER_CONSTRUCTION:
                    acc(d["add_uc"], int(y), r)
        for r in sheets.get("Operating", []):
            y = r.get("Planned Retirement Year")
            if isinstance(y, (int, float)) and int(y) in years and match(r, flt):
                acc(d["retire"], int(y), r)
    return out


def collect(prev):
    load_env()          # run.py 밖에서 직접 import 해도 키를 읽도록 (setdefault — 중복 호출 무해)
    raw = C.new(prev)
    start = "2019-01-01"
    ba = [c for _, _, src, codes, _ in REGIONS if src == "ba" for c in codes]
    sub = [c for _, _, src, codes, _ in REGIONS if src == "subba" for c in codes]
    C.attempt(raw, "demand", "EIA-930 일별 지역 수요", _daily,
              "electricity/rto/daily-region-data/data/", "respondent", ba, start)
    C.attempt(raw, "demand_sub", "EIA-930 PJM 존(DOM·AEP) 일별 수요", _daily,
              "electricity/rto/daily-region-sub-ba-data/data/", "subba", sub, start)

    def retail():
        rows = eia.fetch("electricity/retail-sales/data/", [
            ("frequency", "monthly"), ("data[0]", "sales"), ("data[1]", "price"), ("start", "2015-01"),
            *eia.facets("stateid", [s for s, _ in STATES]), *eia.facets("sectorid", ["COM", "IND"])])
        out = {}
        for r in rows:
            for f in ("sales", "price"):
                if r.get(f) not in (None, ""):
                    out.setdefault(f"{r['sectorid']}_{f}", {}).setdefault(r["stateid"], {})[r["period"]] = float(r[f])
        return out          # sales: 백만 kWh, price: ¢/kWh
    C.attempt(raw, "retail", "EIA 주별 전력 판매·요금", retail)

    def supply():
        content, ym = eia860m.latest()
        return {"file_month": ym, "regions": summarize_860m(eia860m.parse(content), int(ym[:4]))}
    C.attempt(raw, "supply", "EIA-860M 계획 신규·폐지", supply)

    for sid, label in PPI:
        C.attempt(raw, f"ppi_{sid}", f"FRED {sid}", fred.series, sid)
    y0 = date.today().year - 6
    C.attempt(raw, "kr_850423_all", "관세청 HS 850423 전체", customs.monthly, "850423", y0)
    for hs, _ in HS_US:
        C.attempt(raw, f"kr_{hs}_us", f"관세청 HS {hs} 대미", customs_country.monthly, hs, "US", y0)
    return C.finish(raw)


# ───────────────────────── 계산 ─────────────────────────
def _clip(x, lo, hi):
    """lo→0, hi→25 선형 (역방향이면 lo>hi)."""
    if x is None:
        return None
    t = (x - lo) / (hi - lo)
    return max(0.0, min(1.0, t)) * 25


def clean(s, lo=.65, hi=1.6):
    """보고 오류 제거 — 앞뒤 7일 중앙값 대비 lo배 미만·hi배 초과인 날은 버림 (예: DOM 2021-10-18 25억 MWh)."""
    keys = sorted(s)
    out = {}
    for i, k in enumerate(keys):
        nb = sorted(s[x] for x in keys[max(0, i - 7):i + 8] if x != k)
        med = nb[len(nb) // 2] if nb else s[k]
        if lo * med <= s[k] <= hi * med:
            out[k] = s[k]
    return out


def region_demand(raw):
    """{코드: {날짜: MWh}} — 이상치 제거 후, 복수 응답자는 합산(공통 날짜만)."""
    d = {c: clean(v) for c, v in {**(raw.get("demand") or {}), **(raw.get("demand_sub") or {})}.items()}
    out = {}
    for code, _, _, codes, _ in REGIONS:
        parts = [d.get(c) for c in codes]
        if all(parts):
            s = S.add(*parts) if len(parts) > 1 else dict(parts[0])
            if s:
                k = max(s)                   # 마지막 날이 집계 중이면(직전 7일 평균의 80% 미만) 제외
                prev7 = [s[x] for x in sorted(s)[-8:-1]]
                if prev7 and s[k] < .8 * sum(prev7) / len(prev7):
                    s.pop(k)
                out[code] = s
    return out


def rolling_min(d, n):
    keys = sorted(d)
    return {keys[i]: min(d[k] for k in keys[i - n + 1:i + 1]) for i in range(n - 1, len(keys))}


def demand_metrics(s):
    k = max(s)
    r28 = S.rolling(s, 28, "sum")
    base = S.rolling(rolling_min(s, 30), 30)          # 30일 최저치의 30일 평균 = 기저수요
    cut = (date.fromisoformat(k) - timedelta(days=365)).isoformat()
    last365 = {x: v for x, v in s.items() if x > cut}
    prior = {x: v for x, v in s.items() if x <= cut}
    pk_k = max(last365, key=last365.get)
    rec_k = max(prior, key=prior.get) if prior else None
    c30 = (date.fromisoformat(k) - timedelta(days=30)).isoformat()
    recent = max(v for x, v in s.items() if x > c30)
    return {
        "asof": k, "r28": r28, "yoy28": S.yoy_pct(r28), "base": base, "base_yoy": S.yoy_pct(base),
        "peak365": last365[pk_k], "peak365_date": pk_k,
        "record_prior": prior[rec_k] if rec_k else None, "record_prior_date": rec_k,
        "peak_vs_record": last365[pk_k] / prior[rec_k] * 100 if rec_k else None,
        "new_record": bool(rec_k and last365[pk_k] > prior[rec_k]),
        "recent30_vs_peak365": recent / last365[pk_k] * 100,
        "avg_load_gw": sum(last365.values()) / len(last365) / 24 / 1000,
    }


def supply_metrics(reg):
    def tot(by_year, eff):
        return sum(v * (ELCC.get(g, .5) if eff else 1) for y in by_year.values() for g, v in y.items()) / 1000
    by_tech = {}
    for key in ("add", "retire"):
        for y in reg[key].values():
            for g, v in y.items():
                by_tech.setdefault(key, {}).setdefault(g, 0.0)
                by_tech[key][g] += v / 1000
    return {"add_gw": tot(reg["add"], False), "uc_gw": tot(reg["add_uc"], False),
            "ret_gw": tot(reg["retire"], False),
            "net_gw": tot(reg["add"], False) - tot(reg["retire"], False),
            "net_eff_gw": tot(reg["add"], True) - tot(reg["retire"], True),
            "uc_eff_gw": tot(reg["add_uc"], True),
            "by_tech": by_tech}


def score(dm, sm):
    """0~100 = 수요 28일 YoY(25) + 기저수요 YoY(25) + 피크/과거기록(25) + 수요-공급 갭(25)."""
    yoy = dm["yoy28"].get(dm["asof"])
    byoy = dm["base_yoy"].get(dm["asof"])
    parts = [_clip(yoy, 0, 8), _clip(byoy, 0, 8), _clip(dm["peak_vs_record"], 95, 105)]
    gap = None
    if sm and dm["avg_load_gw"] and byoy is not None:
        need = ((1 + byoy / 100) ** HORIZON - 1) * 100             # 기저 증가율이 3년 지속될 때 필요 증가
        have = sm["net_eff_gw"] / dm["avg_load_gw"] * 100           # 유효 순증 / 평균부하
        gap = need - have
        parts.append(_clip(gap, -10, 10))
    valid = [p for p in parts if p is not None]
    if not valid:
        return None, gap
    return sum(valid) / len(valid) * 4, gap                          # 결측 항목은 나머지 평균으로 환산


# ───────────────────────── 페이지 ─────────────────────────
def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "EIA-930 Hourly Electric Grid Monitor (일별 지역·PJM 존 수요)", "https://www.eia.gov/electricity/gridmonitor/")
    P.source(page, "EIA Electricity Retail Sales (주별 판매·요금)", "https://www.eia.gov/electricity/data/browser/")
    P.source(page, "EIA-860M Monthly Generator Inventory", "https://www.eia.gov/electricity/data/eia860m/")
    P.source(page, "FRED — BLS PPI (변압기·개폐기·터빈)", "https://fred.stlouisfed.org/series/PCU335311335311")
    P.source(page, "관세청 품목별·국가별 수출입실적 (data.go.kr)", "https://www.data.go.kr/data/15100475/openapi.do")
    names = {c: n for c, n, *_ in REGIONS}
    dem = region_demand(raw)
    dms = {c: demand_metrics(s) for c, s in dem.items() if len(s) > 400}
    sup = raw.get("supply") or {}
    sms = {c: supply_metrics(r) for c, r in (sup.get("regions") or {}).items()}
    scores = {c: score(dms[c], sms.get(c)) for c in dms}

    # KPI
    ranked = sorted((c for c in scores if c != "US48" and scores[c][0] is not None), key=lambda c: -scores[c][0])
    if ranked:
        c = ranked[0]
        P.kpi(page, f"병목 점수 1위: {names[c]}", scores[c][0], "/100", digits=0, asof=dms[c]["asof"])
    for c in ("DOM", "ERCO", "PJM"):
        if c in dms:
            m = dms[c]
            P.kpi(page, f"{names[c]} 28일 수요", m["r28"].get(m["asof"], 0) / 1e6, "TWh", m["yoy28"].get(m["asof"]), asof=m["asof"])
    if "DOM" in dms:
        m = dms["DOM"]
        P.kpi(page, "Dominion 기저수요", m["base"].get(m["asof"], 0) / 24 / 1000, "GW", m["base_yoy"].get(m["asof"]), asof=m["asof"])
    for c in ("PJM", "ERCO"):
        if c in dms and dms[c]["peak_vs_record"] is not None:
            m = dms[c]
            P.kpi(page, f"{names[c].split(' ')[0]} 1년 피크 / 과거 기록", m["peak_vs_record"], "%",
                  asof=("신기록 " if m["new_record"] else "") + m["peak365_date"])
    if "US48" in sms:
        P.kpi(page, f"미국 {HORIZON}년 계획 유효 순증", sms["US48"]["net_eff_gw"], "GW", asof=f"EIA-860M {sup.get('file_month')}")
    tr = raw.get(f"ppi_{PPI[0][0]}") or {}
    if tr:
        k, v = S.last(tr)
        P.kpi(page, "변압기 PPI", v, "", S.yoy_pct(tr).get(k), asof=k)
    us23 = {k: v["exp_usd"] / 1e6 for k, v in (raw.get("kr_850423_us") or {}).items()}
    if us23:
        r12 = S.rolling(us23, 12, "sum")
        k, v = S.last(r12)
        if k:
            P.kpi(page, "대미 대형변압기 수출 12M", v, "$M", S.yoy_pct(r12).get(k), asof=k, digits=0)

    # 1) 수요 — 28일 YoY / 기저수요 YoY
    order = [c for c, *_ in REGIONS if c in dms]
    slot = {c: (i if c != "US48" else -1) for i, c in enumerate(c for c, *_ in REGIONS)}
    for cid, title, key, note in (
            ("yoy28", "지역별 28일 수요 합계 YoY", "yoy28", "기온 영향 큼 — 추세로 볼 것"),
            ("base_yoy", "지역별 기저수요 YoY (30일 최저치의 30일 평균)", "base_yoy",
             "기저수요 = 가장 덜 쓰는 날의 수요 → 냉난방 영향이 적어 데이터센터 같은 24시간 부하 증가를 더 잘 보여줌")):
        end = min(dms[c]["asof"] for c in order) if order else ""
        keys = sorted(set().union(*(set(dms[c][key]) for c in order))) if order else []
        keys = [k for k in keys if "2021-01-01" <= k <= end][::-7][::-1]     # 공통 최신일부터 거꾸로 주 1회 샘플
        P.chart(page, cid, title, keys, [P.series(names[c], S.align(keys, dms[c][key], 1), slot=slot[c]) for c in order],
                unit="%", note=note, window=78)
    # 2) 연도별 최대 일수요 (첫 완전 연도 = 100)
    if order:
        years = sorted({k[:4] for c in order for k in dem[c]})
        years = [y for y in years if all(any(k[:4] == y for k in dem[c]) for c in order)]
        if years:
            base_y = years[1] if len(years) > 1 and not any(k.startswith(years[0] + "-01-0") for k in dem[order[0]]) else years[0]
            ser = []
            for c in order:
                ymax = {y: max(v for k, v in dem[c].items() if k[:4] == y) for y in years}
                ser.append(P.series(names[c], [round(ymax[y] / ymax[base_y] * 100, 1) if ymax.get(base_y) else None for y in years],
                                    kind="bar", slot=slot[c]))
            P.chart(page, "peak_year", f"연도별 최대 일수요 ({base_y}=100)", years, ser, kind="bar", unit="지수",
                    note="일별 총수요(MWh/일)의 연중 최대값 — 시간 단위 순간 피크(MW)의 근사치. 올해는 연초 이후 누적")
    if "DOM" in dem:
        mon = S.daily_to_monthly({k: v / 1e6 for k, v in dem["DOM"].items()})
        mk = sorted(mon)[:-1]
        yo = S.yoy_pct(mon)
        P.chart(page, "dom_monthly", "Dominion 존 월별 수요 (세계 최대 데이터센터 밀집지)", mk,
                [P.series("월 수요", S.align(mk, mon, 2), kind="bar", slot=0)], unit="TWh", window=36,
                note=f"최근 완결월 YoY {yo.get(mk[-1], 0):+.1f}%" if mk and yo.get(mk[-1]) is not None else "")

    # 3) 주별 판매·요금
    rt = raw.get("retail") or {}
    com, ind_p = rt.get("COM_sales") or {}, rt.get("IND_price") or {}
    if com:
        r12 = {s: S.rolling(com.get(s, {}), 12, "sum") for s, _ in STATES}
        ks = sorted(k for k in set().union(*(set(S.yoy_pct(v)) for v in r12.values())) if k >= "2018-01")
        P.chart(page, "com_yoy", "상업용 전력 판매 12개월 합계 YoY — 주별", ks,
                [P.series(lbl, S.align(ks, S.yoy_pct(r12[s]), 1), slot=i if s != "US" else -1)
                 for i, (s, lbl) in enumerate(STATES)], unit="%", window=60,
                note="데이터센터는 대부분 상업용(COM) 부문으로 집계")
    if ind_p:
        r12p = {s: S.rolling(ind_p.get(s, {}), 12) for s, _ in STATES}
        ks = sorted(k for k in set().union(*(set(S.yoy_pct(v)) for v in r12p.values())) if k >= "2018-01")
        P.chart(page, "ind_price", "산업용 평균 전력요금 YoY (12개월 평균) — 주별", ks,
                [P.series(lbl, S.align(ks, S.yoy_pct(r12p[s]), 1), slot=i if s != "US" else -1)
                 for i, (s, lbl) in enumerate(STATES)], unit="%", window=60,
                note="요금 상승 = 수급 타이트 + 송배전 투자비 전가 신호")

    # 4) 공급 — 향후 N년 계획 신규(+)·폐지(−)
    sorder = [c for c, *_ in REGIONS if c in sms and c != "US48"]
    if sorder:
        groups = [g for g in eia860m.GROUP_ORDER if any(sms[c]["by_tech"].get(k, {}).get(g) for c in sorder for k in ("add", "retire"))]
        fy = int(sup["file_month"][:4])
        ser = [P.series(f"{g} 신규", [round(sms[c]["by_tech"].get("add", {}).get(g, 0), 2) for c in sorder], slot=SLOT.get(g, -1))
               for g in groups if any(sms[c]["by_tech"].get("add", {}).get(g) for c in sorder)]
        ser.append(P.series("폐지 (전체)", [round(-sum(sms[c]["by_tech"].get("retire", {}).values()), 2) for c in sorder], slot=-1))
        P.chart(page, "supply", f"{fy}~{fy + HORIZON - 1}년 계획 신규(+)·폐지(−) — 지역별", [names[c] for c in sorder], ser,
                kind="bar", unit="GW", stack=True,
                note=f"EIA-860M {sup['file_month']} 기준 정격용량. 인허가 전(P·L) 포함 — 실제 가동은 더 적고 늦어지는 경향")
        # 수요 vs 공급
        both = [c for c in sorder if c in dms and dms[c]["avg_load_gw"]]
        if both:
            need = {c: ((1 + (dms[c]["base_yoy"].get(dms[c]["asof"]) or 0) / 100) ** HORIZON - 1) * 100 for c in both}
            have = {c: sms[c]["net_eff_gw"] / dms[c]["avg_load_gw"] * 100 for c in both}
            uc = {c: sms[c]["uc_eff_gw"] / dms[c]["avg_load_gw"] * 100 for c in both}
            P.chart(page, "gap", f"{HORIZON}년 필요 수요 증가 vs 계획 유효 순증 (평균부하 대비 %)", [names[c] for c in both], [
                P.series(f"수요 증가 ({HORIZON}년, 기저수요 YoY 지속 가정)", [round(need[c], 1) for c in both], slot=3),
                P.series("계획 유효 순증 (전체 상태)", [round(have[c], 1) for c in both], slot=0),
                P.series("공사 중 유효 신규 (폐지 차감 전)", [round(uc[c], 1) for c in both], slot=1)],
                kind="bar", unit="%",
                note="유효 순증 = Σ 정격 × 피크 기여계수(가스 .9·원전 .95·석탄 .85·ESS .5·태양광/풍력 .15) − 폐지분. 수요 막대가 공급보다 높을수록 병목")

    # 5) 전력기기 가격·수출
    ppis = {sid: raw.get(f"ppi_{sid}") or {} for sid, _ in PPI}
    if any(ppis.values()):
        ks = sorted(k for k in set().union(*(set(v) for v in ppis.values())) if k >= "2019-01")
        P.chart(page, "ppi", "전력기기 생산자물가 (2020-01=100)", ks,
                [P.series(lbl, S.align(ks, S.index_to(S.since(ppis[sid], "2019-01"), "2020-01"), 1), slot=i)
                 for i, (sid, lbl) in enumerate(PPI)], unit="지수", window=84)
        P.chart(page, "ppi_yoy", "전력기기 생산자물가 YoY", ks,
                [P.series(lbl, S.align(ks, S.yoy_pct(ppis[sid]), 1), slot=i) for i, (sid, lbl) in enumerate(PPI)],
                unit="%", window=60, note="가격 상승세 둔화는 공급(증설) 따라잡기의 신호일 수 있음")
    exp = {hs: {k: v["exp_usd"] / 1e6 for k, v in (raw.get(f"kr_{hs}_us") or {}).items()} for hs, _ in HS_US}
    all23 = {k: v["exp_usd"] / 1e6 for k, v in (raw.get("kr_850423_all") or {}).items()}
    if any(exp.values()):
        ks = sorted(set().union(*(set(v) for v in exp.values())))
        P.chart(page, "kr_us", "한국 → 미국 변압기 수출 (월, HS 8504.21~23)", ks,
                [P.series(lbl, S.align(ks, exp[hs], 1), slot=i) for i, (hs, lbl) in enumerate(HS_US)],
                kind="bar", unit="$M", stack=True, window=36)
    if exp.get("850423") or all23:
        r_us, r_all = S.rolling(exp.get("850423", {}), 12, "sum"), S.rolling(all23, 12, "sum")
        share = S.ratio(r_us, r_all, 100)
        ks = sorted(set(S.yoy_pct(r_us)) | set(S.yoy_pct(r_all)))
        P.chart(page, "kr_yoy", "대형 전력변압기(HS 850423) 수출 12M 합계 YoY", ks, [
            P.series("대미", S.align(ks, S.yoy_pct(r_us), 1), slot=0),
            P.series("전체", S.align(ks, S.yoy_pct(r_all), 1), slot=-1)], unit="%", window=48,
            note=f"최근 12M 대미 비중 {S.last(share)[1]:.0f}%" if share else "")

    # 6) 점수
    if scores:
        sc = [c for c in order if scores[c][0] is not None]
        P.chart(page, "score", "지역별 전력 병목 점수", [names[c] for c in sc],
                [P.series("점수", [round(scores[c][0], 0) for c in sc], kind="bar", slot=3)], kind="bar", unit="/100")

    # 표
    rows = []
    for c in order:
        m, sm = dms[c], sms.get(c)
        a = m["asof"]
        rows.append([names[c], a, round(m["yoy28"].get(a, 0), 1), round(m["base_yoy"].get(a, 0), 1),
                     round(m["avg_load_gw"], 1),
                     round(m["peak_vs_record"], 1) if m["peak_vs_record"] else "-",
                     ("신기록 " if m["new_record"] else "") + m["peak365_date"],
                     round(m["recent30_vs_peak365"], 1),
                     round(sm["net_gw"], 1) if sm else "-", round(sm["net_eff_gw"], 1) if sm else "-",
                     round(scores[c][1], 1) if scores[c][1] is not None else "-",
                     round(scores[c][0]) if scores[c][0] is not None else "-"])
    P.table(page, "지역별 요약", ["지역", "기준일", "28일 YoY(%)", "기저 YoY(%)", "평균부하(GW)",
                                "1년 피크/과거기록(%)", "1년 피크일", "최근30일 피크/1년 피크(%)",
                                f"{HORIZON}년 순증 정격(GW)", f"{HORIZON}년 순증 유효(GW)", "수요-공급 갭(%p)", "병목 점수"], rows,
            note="Dominion·AEP 공급은 PJM 내 VA·OH 소재 발전기로 근사. 피크는 일 총수요 기준")
    if rt.get("COM_sales"):
        srows = []
        for s, lbl in STATES:
            cs, ip = S.rolling(rt["COM_sales"].get(s, {}), 12, "sum"), S.rolling(ind_p.get(s, {}), 12)
            k, v = S.last(cs)
            kp, vp = S.last(ip)
            if k:
                srows.append([lbl, k, round(v / 1000, 1), round(S.yoy_pct(cs).get(k, 0), 1),
                              round(vp, 2) if kp else "-", round(S.yoy_pct(ip).get(kp, 0), 1) if kp else "-"])
        P.table(page, "주별 상업용 판매·산업용 요금 (12개월)", ["주", "기준월", "상업용 판매(TWh)", "YoY(%)",
                                                   "산업용 요금(¢/kWh)", "YoY(%)"], srows)

    page["notes"] += [
        "병목 점수(0~100) = 4개 항목 각 0~25점 합계: ① 28일 수요 YoY 0%→0점·8% 이상→25점 ② 기저수요 YoY 0%→0·8%→25 "
        "③ 최근 1년 최대 일수요 / 그 이전 기록 95%→0·105%→25 ④ 수요-공급 갭 −10%p→0·+10%p→25 (구간 내 선형). 결측 항목은 나머지 평균으로 환산.",
        f"수요-공급 갭 = 기저수요 YoY가 {HORIZON}년 지속될 때의 누적 증가율 − (향후 {HORIZON}년 계획 유효 순증 GW / 최근 1년 평균부하 GW). "
        "예비율·송전 제약·수입 전력은 반영하지 않는 단순 지표입니다.",
        "읽는 법: 점수가 높고 갭이 플러스인 지역일수록 가스터빈(GE버노바·지멘스에너지)·대형변압기(HD현대일렉트릭·효성중공업)·"
        "배전/차단기(LS ELECTRIC·산일전기·제룡전기) 수요가 이어질 가능성이 큽니다. PPI 상승률 둔화와 대미 수출 YoY 꺾임은 사이클 피크 신호로 함께 확인.",
        "EIA-930 일별 수요는 동부시간 기준 일 합계(MWh)이며 최근 며칠은 수정될 수 있습니다. 마지막 날이 집계 중이면 제외합니다.",
    ]
    return page
