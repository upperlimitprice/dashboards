"""미국 가스발전·LNG 사이클 — 가스발전 투자 붐이 가스터빈 발주·LNG 수출로 이어지나.

EIA-860M(가스 발전기 계획 파이프라인, 월별 스냅샷 누적·아카이브 백필) + EIA v2 natural-gas(헨리허브·저장량·
발전용 소비·LNG 수출·생산) + STEO(18개월 전망, 실행마다 전망 vintage 누적).
"""
import calendar
from datetime import date, timedelta

from core import collect as C
from core import page as P
from core import series as S
from core.env import load_env
from core.http import NotFound, get
from core.sources import eia, eia860m

KEY = "gas_lng"
TITLE = "🔥 미국 가스발전·LNG 사이클"
SUBTITLE = "EIA-860M 가스 발전기 파이프라인(월별 스냅샷) · 헨리허브·저장량·발전용 소비·LNG 수출 · STEO 전망"
NEEDS = ["EIA_API_KEY"]

ARCHIVE = "https://www.eia.gov/electricity/data/eia860m/archive/xls/{m}_generator{y}.xlsx"
BACKFILL_MONTHS = 18
MW = "Nameplate Capacity (MW)"

TYPES = [("Combined Cycle", "복합(NGCC)"), ("Combustion Turbine", "단순(CT)"),
         ("Internal Combustion", "엔진(RICE)")]
TYPE_ORDER = ["복합(NGCC)", "단순(CT)", "엔진(RICE)", "기타 가스"]
TYPE_SLOT = {"복합(NGCC)": 0, "단순(CT)": 1, "엔진(RICE)": 2, "기타 가스": -1}
# Planned 시트 Status: (V)>50% 공사 (U)≤50% 공사 (TS) 공사 완료·상업운전 전 (T) 인허가 완료 (L) 인허가 중 (P) 계획
STATUS = {"V": "uc", "U": "uc", "TS": "uc", "T": "permit"}
STATUS_ORDER = [("uc", "건설 중(U·V·TS)", 0), ("permit", "인허가 완료(T)", 3), ("plan", "계획·인허가 중(P·L)", -1)]

NG = {   # key: (route, series id, frequency, 시작 연도 전)
    "henry_hub": ("natural-gas/pri/fut/data/", "RNGWHHD", "daily", 6),
    "storage": ("natural-gas/stor/wkly/data/", "NW2_EPG0_SWO_R48_BCF", "weekly", 9),
    "power_burn": ("natural-gas/cons/sum/data/", "N3045US2", "monthly", 11),
    "lng_exports": ("natural-gas/move/expc/data/", "N9133US2", "monthly", 11),
    "dry_prod": ("natural-gas/prod/sum/data/", "N9070US2", "monthly", 11),
}
LNG_TERMINALS = [   # EIA 출구(point of exit)별 LNG 수출, MMcf
    ("YSPL", "Sabine Pass"), ("YPLAQ", "Plaquemines"), ("YCRP", "Corpus Christi"),
    ("YCAM", "Cameron"), ("YFPT", "Freeport"), ("YCCPL", "Calcasieu Pass"),
    ("YCPT", "Cove Point"), ("YGPT", "Golden Pass"), ("YELBA", "Elba Island"),
    ("YALTA", "Altamira(멕시코 FLNG)"),
]
STEO = {   # seriesId: (표시명, 단위, 연간 집계)
    "NGEPGEN_US": ("가스 발전량(전력부문)", "TWh", "sum"),
    "NGEPCON": ("발전용 가스 소비", "Bcf/d", "mean"),
    "NGEXPUS_LNG": ("LNG 총수출", "Bcf/d", "mean"),
    "NGHHUUS": ("헨리허브", "$/MMBtu", "mean"),
    "NGPRPUS": ("건조가스 생산", "Bcf/d", "mean"),
    "NGEPCGW_US": ("가스 발전설비(여름 순용량)", "GW", "last"),
}


# ───────────────────────── EIA-860M 가스 집계 ─────────────────────────
def gas_type(tech):
    tech = tech or ""
    if "Natural Gas" not in tech:
        return None
    for needle, t in TYPES:
        if needle in tech:
            return t
    return "기타 가스"


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def snapshot(sheets, file_ym):
    """Planned 시트 → {by_year: {연: {유형: {상태: MW}}}, n36: {상태: MW}} (n36 = 파일월 이후 36개월 내 가동 예정)."""
    by_year, n36 = {}, {}
    fy, fm = int(file_ym[:4]), int(file_ym[5:7])
    for r in sheets.get("Planned", []):
        t = gas_type(r.get("Technology"))
        y = _int(r.get("Planned Operation Year"))
        if not t or not y:
            continue
        st = STATUS.get(eia860m.status_code(r.get("Status")), "plan")
        v = float(r[MW])
        d = by_year.setdefault(str(y), {}).setdefault(t, {})
        d[st] = d.get(st, 0.0) + v
        m = _int(r.get("Planned Operation Month")) or 12
        if (y - fy) * 12 + (m - fm) <= 36:
            n36[st] = n36.get(st, 0.0) + v
    return {"by_year": by_year, "n36": n36}


def top_plants(planned, n=15):
    acc = {}
    for r in planned:
        t = gas_type(r.get("Technology"))
        if not t:
            continue
        d = acc.setdefault(r.get("Plant ID"), {
            "entity": r.get("Entity Name"), "plant": r.get("Plant Name"), "state": r.get("Plant State"),
            "mw": 0.0, "types": set(), "yms": [], "status": {}})
        v = float(r[MW])
        d["mw"] += v
        d["types"].add(t)
        y, m = _int(r.get("Planned Operation Year")), _int(r.get("Planned Operation Month"))
        if y:
            d["yms"].append(f"{y}-{m:02d}" if m else str(y))
        sc = eia860m.status_code(r.get("Status"))
        d["status"][sc] = d["status"].get(sc, 0.0) + v
    out = []
    for d in sorted(acc.values(), key=lambda d: -d["mw"])[:n]:
        yms = sorted(d["yms"])
        when = "" if not yms else (yms[0] if yms[0] == yms[-1] else f"{yms[0]}~{yms[-1]}")
        out.append({"entity": d["entity"], "plant": d["plant"], "state": d["state"], "mw": round(d["mw"], 1),
                    "types": "·".join(t for t in TYPE_ORDER if t in d["types"]), "when": when,
                    "status": "·".join(k for k, _ in sorted(d["status"].items(), key=lambda kv: -kv[1]))})
    return out


def gas_additions(operating):
    """Operating 시트의 가동 연도별 가스 신규 용량 {연: {유형: MW}} (2010~)."""
    out = {}
    for r in operating:
        t = gas_type(r.get("Technology"))
        y = _int(r.get("Operating Year"))
        if t and y and y >= 2010:
            d = out.setdefault(str(y), {})
            d[t] = d.get(t, 0.0) + float(r[MW])
    return out


def _month_back(ym, n):
    y, m = int(ym[:4]), int(ym[5:7])
    m -= n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


def fetch_archive(ym):
    url = ARCHIVE.format(m=calendar.month_name[int(ym[5:7])].lower(), y=ym[:4])
    b = get(url, timeout=180, cache_hours=24)
    if b[:2] != b"PK":       # 미공개/없는 월은 200 HTML(소프트 404)
        raise NotFound(f"{url}: xlsx 아님")
    return b


def collect_860m(raw):
    prev = raw["_prev"]

    def fetch_latest():
        content, ym = eia860m.latest()
        sheets = eia860m.parse(content)
        return {"file_month": ym, "snapshot": snapshot(sheets, ym),
                "top_plants": top_plants(sheets.get("Planned", [])),
                "additions": gas_additions(sheets.get("Operating", []))}
    latest = C.attempt(raw, "eia860m", "EIA-860M 최신", fetch_latest)

    snaps = dict(prev.get("gas_snapshots", {}))
    if latest:
        snaps[latest["file_month"]] = latest["snapshot"]
    done = prev.get("backfill_done", False)
    if latest and not done:   # 최초 1회: 아카이브에서 과거 스냅샷 복원
        ok, fail = 0, []
        for i in range(1, BACKFILL_MONTHS + 1):
            ym = _month_back(latest["file_month"], i)
            if ym in snaps:
                ok += 1
                continue
            try:
                snaps[ym] = snapshot(eia860m.parse(fetch_archive(ym)), ym)
                ok += 1
                print(f"  860M 백필 {ym} OK")
            except Exception as e:  # noqa: BLE001 — 한 달 실패가 전체를 막지 않게
                fail.append(f"{ym}({type(e).__name__})")
        done = ok >= BACKFILL_MONTHS // 2
        if fail:
            raw["errors"].append(f"EIA-860M 아카이브 백필 일부 실패: {', '.join(fail)}"[:300])
    raw["gas_snapshots"] = snaps
    raw["backfill_done"] = done


# ───────────────────────── EIA v2 natural-gas / STEO ─────────────────────────
def fetch_ng(route, sid, freq, years, prev):
    """증분 수집 — 이전 데이터가 있으면 최근 1년(일별은 60일)만 다시 받아 덮어씀(개정 반영).
    EIA API 가 큰 일별 요청에 504 를 자주 내므로 최초 수집은 2년 단위로 나눠 받는다."""
    today = date.today()
    if prev:
        last = date.fromisoformat(max(prev) + ("-01" if freq == "monthly" else ""))
        starts = [last - timedelta(days=60 if freq == "daily" else 366)]
    else:
        starts = [date(y, 1, 1) for y in range(today.year - years, today.year + 1, 2)]
    out = dict(prev or {})
    for i, st in enumerate(starts):
        end = starts[i + 1] - timedelta(days=1) if i + 1 < len(starts) else None
        fmt = (lambda d: d.isoformat()[:7]) if freq == "monthly" else date.isoformat
        p = [("frequency", freq), ("data[0]", "value"), ("start", fmt(st)), *eia.facets("series", [sid])]
        if end:
            p.append(("end", fmt(end)))
        out.update(eia.series(eia.fetch(route, p), "series").get(sid, {}))
    return out


def fetch_terminals():
    ids = [f"NGM_EPG0_ENG_{c}-Z00_MMCF" for c, _ in LNG_TERMINALS]
    rows = eia.fetch("natural-gas/move/poe2/data/", [
        ("frequency", "monthly"), ("data[0]", "value"), ("start", f"{date.today().year - 5}-01"),
        *eia.facets("series", ids)])
    s = eia.series(rows, "series")
    return {name: s.get(f"NGM_EPG0_ENG_{c}-Z00_MMCF", {}) for c, name in LNG_TERMINALS}


def fetch_steo():
    rows = eia.fetch("steo/data/", [("frequency", "monthly"), ("data[0]", "value"),
                                    ("start", f"{date.today().year - 4}-01"), *eia.facets("seriesId", list(STEO))])
    return eia.series(rows, "seriesId")


def steo_annual(steo, sid, year):
    vals = [v for k, v in sorted(steo.get(sid, {}).items()) if k[:4] == str(year)]
    if len(vals) < 12:
        return None
    how = STEO[sid][2]
    return sum(vals) if how == "sum" else vals[-1] if how == "last" else sum(vals) / len(vals)


def collect(prev):
    load_env()
    raw = C.new(prev)
    for k, (route, sid, freq, years) in NG.items():
        C.attempt(raw, k, f"EIA 천연가스 {sid}", fetch_ng, route, sid, freq, years, raw["_prev"].get(k))
    C.attempt(raw, "lng_terminals", "EIA LNG 출구별 수출", fetch_terminals)
    n_err = len(raw["errors"]) + len(raw["missing"])
    steo = C.attempt(raw, "steo", "EIA STEO", fetch_steo)
    fresh = len(raw["errors"]) + len(raw["missing"]) == n_err

    # STEO 전망 vintage 누적 — 값이 바뀐 실행만 추가 → 전회 대비 상향/하향
    vint = list(prev.get("steo_vintages", []))
    if steo and fresh:
        y = date.today().year
        vals = {sid: {str(yy): steo_annual(steo, sid, yy) for yy in (y, y + 1)} for sid in STEO}
        if not vint or vint[-1]["vals"] != vals:
            vint.append({"asof": date.today().isoformat(), "vals": vals})
    raw["steo_vintages"] = vint[-24:]

    collect_860m(raw)
    return C.finish(raw)


# ───────────────────────── build ─────────────────────────
def bcfd(monthly_mmcf):
    """월간 MMcf → Bcf/d"""
    return {k: v / 1000 / calendar.monthrange(int(k[:4]), int(k[5:7]))[1] for k, v in monthly_mmcf.items()}


def weekly_avg(daily):
    acc = {}
    for k, v in daily.items():
        d = date.fromisoformat(k)
        acc.setdefault((d - timedelta(days=d.weekday())).isoformat(), []).append(v)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def five_year_avg(weekly):
    """각 주에 대해 직전 5개 연도 동주(±3일) 평균."""
    dates = {date.fromisoformat(k): v for k, v in weekly.items()}
    out = {}
    for d in sorted(dates):
        vals = []
        for y in range(1, 6):
            try:
                base = d.replace(year=d.year - y)
            except ValueError:
                base = d.replace(year=d.year - y, day=28)
            hit = next((dates[base + timedelta(days=o)] for o in (0, -1, 1, -2, 2, -3, 3)
                        if base + timedelta(days=o) in dates), None)
            if hit is not None:
                vals.append(hit)
        if len(vals) == 5:
            out[d.isoformat()] = sum(vals) / 5
    return out


def gw(d):
    return sum(d.values()) / 1000 if d else 0.0


def snap_total(s, st=None):
    return sum(v for y in s["by_year"].values() for t in y.values() for k, v in t.items()
               if st is None or k == st) / 1000


def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "EIA-860M Monthly Generator Inventory (최신+아카이브)", "https://www.eia.gov/electricity/data/eia860m/")
    P.source(page, "EIA Natural Gas data (API v2: natural-gas)", "https://www.eia.gov/naturalgas/data.php")
    P.source(page, "EIA Short-Term Energy Outlook (API v2: steo)", "https://www.eia.gov/outlooks/steo/")
    s860 = raw.get("eia860m") or {}
    snaps = raw.get("gas_snapshots") or {}
    ym = s860.get("file_month")
    snap = snaps.get(ym) if ym else None
    hh = raw.get("henry_hub") or {}
    stor = raw.get("storage") or {}
    burn = bcfd(raw.get("power_burn") or {})
    lng = bcfd(raw.get("lng_exports") or {})
    prod = bcfd(raw.get("dry_prod") or {})
    steo = raw.get("steo") or {}

    # ── KPI ──
    if snap:
        prev_key = max((k for k in snaps if k <= S.shift_year(ym)), default=None)
        prev_snap = snaps.get(prev_key)
        n36, n36p = gw(snap["n36"]), gw(prev_snap["n36"]) if prev_snap else None
        P.kpi(page, "계획 가스 용량 (36개월 내)", n36, "GW",
              (n36 / n36p - 1) * 100 if n36p else None, f"vs {prev_key} 스냅샷" if n36p else "YoY",
              asof=f"EIA-860M {ym}")
        uc, ucp = snap["n36"].get("uc", 0) / 1000, (prev_snap["n36"].get("uc", 0) / 1000 if prev_snap else None)
        P.kpi(page, "그중 건설 중 (U·V·TS)", uc, "GW",
              (uc / ucp - 1) * 100 if ucp else None, f"vs {prev_key}" if ucp else "YoY", asof=f"EIA-860M {ym}")
    k, v = S.last(lng)
    if k:
        P.kpi(page, "LNG 수출", v, "Bcf/d", S.yoy_pct(lng).get(k), asof=k)
    k, v = S.last(burn)
    if k:
        P.kpi(page, "발전용 가스 소비", v, "Bcf/d", S.yoy_pct(burn).get(k), asof=k)
    k, v = S.last(hh)
    if k:
        yago = max((d for d in hh if d <= S.shift_year(k)), default=None)
        P.kpi(page, "헨리허브 현물", v, "$/MMBtu", (v / hh[yago] - 1) * 100 if yago else None, digits=2, asof=k)
    avg5 = five_year_avg(stor)
    k, v = S.last(stor)
    if k:
        a = avg5.get(k)
        P.kpi(page, "가스 저장량 (L48)", v, "Bcf", (v / a - 1) * 100 if a else None, "5년 평균 대비", digits=0, asof=k)
    k, v = S.last(prod)
    if k:
        P.kpi(page, "건조가스 생산", v, "Bcf/d", S.yoy_pct(prod).get(k), asof=k)
    lng_f = steo.get("NGEXPUS_LNG", {})
    if lng_f:
        y = date.today().year
        a0, a1 = steo_annual(steo, "NGEXPUS_LNG", y), steo_annual(steo, "NGEXPUS_LNG", y + 1)
        if a0 and a1:
            P.kpi(page, f"STEO {y + 1} LNG 수출 전망", a1, "Bcf/d", (a1 / a0 - 1) * 100, f"vs {y}")

    # ── 1. 가스터빈 수요 대리지표 (EIA-860M) ──
    if snap:
        fy = int(ym[:4])
        years = [y for y in range(fy, fy + 7) if str(y) in snap["by_year"]]
        by = snap["by_year"]

        def tsum(y, t=None, st=None):
            d = by.get(str(y), {})
            return sum(v for tt, sd in d.items() if t in (None, tt) for k, v in sd.items() if st in (None, k)) / 1000
        P.chart(page, "gas_plan_type", f"가동 예정 연도별 가스 계획 용량 — 유형별 (EIA-860M {ym})", [str(y) for y in years],
                [P.series(t, [round(tsum(y, t), 2) for y in years], slot=TYPE_SLOT[t]) for t in TYPE_ORDER],
                kind="bar", unit="GW", stack=True,
                note="NGCC 용량은 가스터빈(CT)+스팀터빈(CA) 합계. 인허가 전(P·L) 단계 포함 — 늦은 연도일수록 미확정")
        P.chart(page, "gas_plan_status", "가동 예정 연도별 가스 계획 용량 — 진행 상태별", [str(y) for y in years],
                [P.series(lbl, [round(tsum(y, st=st), 2) for y in years], slot=sl) for st, lbl, sl in STATUS_ORDER],
                kind="bar", unit="GW", stack=True, note="건설 중 = 터빈 발주·납품이 확정된 물량으로 볼 수 있음")
        adds = s860.get("additions") or {}
        hy = list(range(fy - 10, fy + 6))
        actual = [round(gw(adds.get(str(y), {})), 2) if y <= fy else None for y in hy]
        P.chart(page, "gas_adds", "가스 설비 연간 신규: 실적 vs 계획", [str(y) for y in hy], [
            P.series("실적 가동", actual, slot=5),
            P.series("계획 — 건설 중", [round(tsum(y, st="uc"), 2) if y >= fy else None for y in hy], slot=0),
            P.series("계획 — 그 외", [round(tsum(y) - tsum(y, st="uc"), 2) if y >= fy else None for y in hy], slot=-1)],
            kind="bar", unit="GW", stack=True,
            note=f"{fy}년은 실적(연초~)과 잔여 계획이 함께 표시됨. 가동 실적은 Operating 시트의 가동 연도 기준")

    if len(snaps) >= 2:
        ks = sorted(snaps)
        P.chart(page, "gas_snap", "가스 계획 파이프라인 총량 — 월별 스냅샷 (전 연도)", ks,
                [P.series(lbl, [round(snap_total(snaps[k], st), 2) for k in ks], slot=sl) for st, lbl, sl in STATUS_ORDER],
                kind="bar", unit="GW", stack=True,
                note="각 월 EIA-860M 파일의 Planned 시트 가스 합계. 늘면 신규 프로젝트 유입 > 가동·취소")
        P.chart(page, "gas_snap_type", "가스 계획 파이프라인 — 유형별(전 연도) · 36개월 내 합계 (월별 스냅샷)", ks, [
            *[P.series(t, [round(sum(v for yd in snaps[k]["by_year"].values() for v in yd.get(t, {}).values()) / 1000, 2)
                           for k in ks], slot=TYPE_SLOT[t]) for t in TYPE_ORDER[:3]],
            P.series("36개월 내 계획(전 유형)", [round(gw(snaps[k]["n36"]), 2) for k in ks], slot=4)], unit="GW")

    tp = s860.get("top_plants") or []
    P.table(page, f"가스 계획 대형 단지 상위 15 (EIA-860M {ym})",
            ["사업자", "발전소", "주", "용량(MW)", "유형", "가동 예정", "상태(용량순)"],
            [[p["entity"], p["plant"], p["state"], p["mw"], p["types"], p["when"], p["status"]] for p in tp],
            note="상태: V/U 공사 중, TS 공사 완료·상업운전 전, T 인허가 완료, L 인허가 중, P 계획")

    # ── 2. 천연가스 수급 ──
    if hh:
        wk = weekly_avg(hh)
        ks = sorted(wk)
        P.chart(page, "hh", "헨리허브 현물가 (주간 평균)", ks, [P.series("Henry Hub", S.align(ks, wk), slot=3)],
                unit="$/MMBtu", window=156)
    if stor:
        ks = [k for k in sorted(stor) if k in avg5]
        ly = {k: stor.get(max((d for d in stor if d <= S.shift_year(k)), default="")) for k in ks}
        P.chart(page, "storage", "가스 저장량 (Lower 48) vs 5년 평균", ks, [
            P.series("저장량", S.align(ks, stor, 0), slot=0),
            P.series("5년 평균", S.align(ks, avg5, 0), slot=-1),
            P.series("전년", S.align(ks, {k: v for k, v in ly.items() if v is not None}, 0), slot=1)],
            unit="Bcf", window=104, note="5년 평균은 직전 5개 연도 같은 주 평균(자체 계산 — EIA 주간 보고서 수치와 소폭 다를 수 있음)")
    if burn:
        ks = sorted(burn)
        P.chart(page, "burn", "발전용 가스 소비 (월간)", ks, [
            P.series("발전용 소비", S.align(ks, burn), slot=0),
            P.series("전년 동월", S.align(ks, {k: burn.get(S.shift_year(k)) for k in ks if burn.get(S.shift_year(k))}), slot=-1),
            P.series("12개월 평균", S.align(ks, S.rolling(burn, 12)), slot=2)], unit="Bcf/d", window=48)
        yo = S.yoy_pct(S.rolling(burn, 12))
        ky = sorted(yo)
        P.chart(page, "burn_yoy", "발전용 가스 소비 YoY (12개월 평균 기준)", ky, [P.series("12M YoY", S.align(ky, yo, 1), slot=0)],
                kind="bar", unit="%", window=60, note="날씨 영향이 큰 단월 대신 12개월 평균의 YoY")

    terms = raw.get("lng_terminals") or {}
    if terms:
        tb = {n: bcfd(d) for n, d in terms.items()}
        ks = sorted({k for d in tb.values() for k in d})
        tot = bcfd(raw.get("lng_exports") or {})
        other = {k: tot[k] - sum(d.get(k, 0) for d in tb.values()) for k in ks if k in tot}
        names = sorted(tb, key=lambda n: -sum(tb[n].get(k, 0) for k in ks[-12:]))
        P.chart(page, "lng_term", "LNG 수출 — 터미널(출구)별", ks,
                [P.series(n, S.align(ks, tb[n]), slot=i if i < 8 else -1) for i, n in enumerate(names)] +
                [P.series("기타", S.align(ks, {k: v for k, v in other.items() if v > 0.005}), slot=-1)],
                kind="bar", unit="Bcf/d", stack=True, window=36,
                note="Plaquemines·Corpus Christi 3단계·Golden Pass 등 신규 터미널 램프업 = LNG선 수요의 실물 근거")

    # ── 3. 실적 + STEO 전망 경로 ──
    def with_forecast(cid, title, actual, sid, unit, start, note="", digits=2):
        f = steo.get(sid, {})
        if not actual and not f:
            return
        la = max(actual) if actual else ""
        ks = sorted({k for k in actual if k >= start} | {k for k in f if k >= start})
        P.chart(page, cid, title, ks, [
            P.series("실적", S.align(ks, actual, digits), slot=0),
            P.series("STEO 추정·전망", S.align(ks, {k: v for k, v in f.items() if k >= la}, digits), slot=3)],
            unit=unit, window=72, note=note or "STEO 선은 실적 마지막 월부터 표시 (EIA 단기 에너지 전망 최신판)")

    y0 = date.today().year
    with_forecast("lng_steo", "LNG 총수출 — 실적과 STEO 전망", lng, "NGEXPUS_LNG", "Bcf/d", f"{y0 - 5}-01")
    hhm = S.daily_to_monthly(hh, "mean")
    if hhm and max(hhm) == date.today().strftime("%Y-%m"):
        hhm.pop(max(hhm))                   # 진행 중인 월 제외
    with_forecast("hh_steo", "헨리허브 월평균 — 실적과 STEO 전망", hhm, "NGHHUUS", "$/MMBtu", f"{y0 - 5}-01")
    with_forecast("burn_steo", "발전용 가스 소비 — 실적과 STEO 전망", burn, "NGEPCON", "Bcf/d", f"{y0 - 5}-01")
    with_forecast("prod_steo", "건조가스 생산 — 실적과 STEO 전망", prod, "NGPRPUS", "Bcf/d", f"{y0 - 5}-01")
    gen = steo.get("NGEPGEN_US", {})
    if gen:
        ks = [k for k in sorted(gen) if k >= f"{y0 - 4}-01"]
        P.chart(page, "gen_steo", "가스 발전량 (전력부문, STEO — 실적·추정·전망 연결 시계열)", ks,
                [P.series("가스 발전량", S.align(ks, gen, 1), slot=0),
                 P.series("전년 동월", S.align(ks, {k: gen.get(S.shift_year(k)) for k in ks if gen.get(S.shift_year(k))}, 1), slot=-1)],
                unit="TWh", window=60, note="STEO 시리즈는 과거 구간도 포함 — 대략 최근 2~3개월부터가 추정·전망")

    # STEO 연간 요약 + 전회 대비
    vint = raw.get("steo_vintages") or []
    rows = []
    for sid, (name, unit, _) in STEO.items():
        if sid not in steo:
            continue
        vals = [steo_annual(steo, sid, yy) for yy in (y0 - 1, y0, y0 + 1)]
        rev = ""
        if len(vint) >= 2:
            a, b = vint[-2]["vals"].get(sid, {}).get(str(y0 + 1)), vint[-1]["vals"].get(sid, {}).get(str(y0 + 1))
            if a and b:
                rev = round((b / a - 1) * 100, 1)
        rows.append([name, unit, *[None if v is None else round(v, 2) for v in vals],
                     None if not (vals[1] and vals[2]) else round((vals[2] / vals[1] - 1) * 100, 1), rev])
    P.table(page, "STEO 연간 전망 요약", ["지표", "단위", f"{y0 - 1}", f"{y0}(추정)", f"{y0 + 1}(전망)",
                                       f"{y0 + 1} vs {y0}(%)", "전회 전망 대비(%)"], rows,
            note="발전량은 연간 합계, 설비는 연말, 나머지는 연평균. '전회 대비'는 직전 수집 vintage와 비교(값이 바뀐 실행만 누적)")
    if len(vint) >= 2:
        a, b = vint[-2], vint[-1]
        msgs = []
        for sid in ("NGEXPUS_LNG", "NGEPGEN_US", "NGHHUUS"):
            pa, pb = a["vals"].get(sid, {}).get(str(y0 + 1)), b["vals"].get(sid, {}).get(str(y0 + 1))
            if pa and pb and abs(pb / pa - 1) >= 0.005:
                msgs.append(f"{STEO[sid][0]} {pa:.2f}→{pb:.2f} {STEO[sid][1]} ({'상향' if pb > pa else '하향'})")
        page["notes"].append(f"STEO {y0 + 1}년 전망 변화 ({a['asof']} → {b['asof']} 수집분): " +
                             ("; ".join(msgs) if msgs else "주요 지표 변화 0.5% 미만"))
    else:
        page["notes"].append("STEO 전망 상향/하향 비교는 다음 STEO 개정(매월 초) 수집 이후부터 표시됩니다.")

    page["notes"] += [
        "계획 가스 용량은 사업자가 EIA에 제출한 일정 기준 — 지연·취소가 잦으므로 건설 중(U·V·TS) 물량과 월별 스냅샷 추세를 함께 볼 것.",
        "가스터빈: 대형 NGCC·CT 파이프라인 증가는 GE버노바·지멘스에너지·미쓰비시중공업 수주잔고와, 납기 부족 시 두산에너빌리티 등 신규 공급자 기회로 연결. "
        "GE버노바·MHI 분기 가스터빈 수주(GW)와 '건설 중' 증가폭을 대조.",
        "LNG: 터미널별 수출 램프업과 STEO LNG 전망 상향은 LNG선 발주(한화오션·삼성중공업·HD한국조선해양)의 수요 근거. "
        "가스 생산·파이프라인 증설은 강관(세아제강·휴스틸) 수요와 연결.",
        "단위: Bcf/d = 십억 입방피트/일 (월간 MMcf ÷ 1000 ÷ 일수). 1 Bcf/d ≈ 연 760만 톤 LNG.",
    ]
    return page
