"""미국 태양광·ESS·원전 '계획 대비 실제' — EIA-860M 월별 스냅샷 발전기 추적 · 원전 정지 · ESS 방전.

핵심 질문: 발표된 태양광·ESS 물량 중 실제 가동되는 비율은? IRA 축소·FEOC(중국산 부품) 규제 이후
취소·지연이 늘고 있나? 원전 가동률은?
"""
from datetime import date, datetime, timedelta

from core import collect as C
from core import page as P
from core import series as S
from core.sources import eia
from core.sources import eia860m_hist as H

KEY = "plan_actual"
TITLE = "☀️ 미국 태양광·ESS·원전 '계획 대비 실제'"
SUBTITLE = ("EIA-860M 월별 스냅샷을 발전기 단위로 추적 — 계획 실현율·지연·취소, 원전 가동률(NRC), "
            "ESS 실제 방전(EIA-930)")
NEEDS = ["EIA_API_KEY(원전·ESS)"]

BACKFILL = 24        # 첫 실행 백필 스냅샷 수
KEEP = 36            # 보관 스냅샷 상한
TECHS = [("S", "태양광", 0), ("B", "ESS", 1), ("W", "풍력", 2), ("N", "원전", 4)]
NAME = {t: n for t, n, _ in TECHS}
SLOT = {t: s for t, _, s in TECHS}
STAGES = [("P", "계획"), ("L", "인허가 중"), ("T", "인허가 완료"), ("U", "공사 ≤50%"),
          ("V", "공사 >50%"), ("TS", "공사 완료·시운전"), ("OT", "기타")]
STAGE_NAME = dict(STAGES)
OP_STATES = ("US", "TX", "CA", "AZ", "FL", "NV")
BAT_RESP = [("ERCO", "ERCOT"), ("US48", "미국 본토(US48)")]
POLICY_NOTE = ("2025-07 OBBBA(IRA 세액공제 축소·FEOC 중국산 부품 제한) 서명 — 이후 스냅샷의 지연·취소 변화를 보세요.")


# ───────────────────────── 월 인덱스 유틸 ─────────────────────────
def mi(ym):
    return int(ym[:4]) * 12 + int(ym[5:7]) - 1


def ym_of(i):
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def dec(tok):
    """토큰 → ('P', due_idx, code) | ('O', op_idx|None) | ('C',) | ('R',) | None"""
    if not tok:
        return None
    if tok[0] == "O":
        return ("O", 2000 * 12 + int(tok[1:3]) * 12 + int(tok[3:5]) - 1 if len(tok) >= 5 else None)
    if tok in ("C", "R"):
        return (tok,)
    return ("P", 2000 * 12 + int(tok[:2]) * 12 + int(tok[2:4]) - 1, tok[4:])


# ───────────────────────── 수집 ─────────────────────────
def _update_860m(prev, errs, today=None):
    """이전 스냅샷 이력을 보존하고 아직 없는 월만 내려받아 끼워 넣는다."""
    today = today or date.today()
    months = list(prev.get("months", []))
    gens = {k: list(v) for k, v in prev.get("gens", {}).items()}
    hist = {k: v.split(",") for k, v in prev.get("hist", {}).items()}
    op_mw = dict(prev.get("op_mw", {}))
    have = set(months)

    # 최신 공개 월 탐색 — 미공개 월은 200 HTML 이 오므로 짧은 캐시로 확인
    latest, latest_b, i = None, None, mi(today.strftime("%Y-%m"))
    for _ in range(8):
        ym = ym_of(i)
        if ym in have:
            latest = ym
            break
        latest_b = H.download(ym, cache_hours=12)
        if latest_b is not None:
            latest = ym
            break
        i -= 1
    if not latest:
        raise RuntimeError("EIA-860M 최신 파일을 찾지 못함")
    want = [ym_of(mi(latest) - k) for k in range(BACKFILL)]
    # 오래된 월부터 순서대로 끼워 넣어야 '계획 → 가동' 토큰이 빠짐없이 기록된다
    # (계획 시트에 처음 등장한 뒤의 월에서만 Operating 토큰을 기록하므로)
    for ym in sorted(set(want) - have):
        try:
            b = latest_b if ym == latest else H.download(ym)
            if b is None:
                errs.append(f"EIA-860M {ym}: 파일 없음(xls·archive 모두 xlsx 아님)")
                continue
            _insert(ym, b, months, gens, hist, op_mw)
        except Exception as e:  # noqa: BLE001 — 월 하나 실패가 백필 전체를 막지 않게
            errs.append(f"EIA-860M {ym}: {type(e).__name__}: {e}"[:200])
    # 보관 상한 + 계획 시트에 한 번도 없던 발전기 제거
    drop = len(months) - KEEP
    if drop > 0:
        for ym in months[:drop]:
            op_mw.pop(ym, None)
        months = months[drop:]
        hist = {k: v[drop:] for k, v in hist.items()}
    hist = {k: v for k, v in hist.items() if any(t and t[0] not in "OCR" for t in v)}
    gens = {k: gens[k] for k in hist}
    return {"months": months, "gens": gens, "hist": {k: ",".join(v) for k, v in hist.items()},
            "op_mw": op_mw}


def _insert(ym, content, months, gens, hist, op_mw):
    snap, op = H.parse(content)
    pos = sum(1 for m in months if m < ym)
    newest = pos == len(months)
    months.insert(pos, ym)
    n = len(months)
    for k, v in hist.items():
        v.insert(pos, "")
    for k, (t, st, mw, tok) in snap.items():
        if k not in hist:
            if tok[0] in "OCR":
                continue          # 계획 단계를 거친 적 없는(이미 가동 중인) 발전기는 추적 불필요
            hist[k] = [""] * n
        hist[k][pos] = tok
        if newest or k not in gens:
            gens[k] = [t, st, mw]
    op_mw[ym] = {t: {s: d.get(s, 0) for s in OP_STATES} for t, d in op.items()}


def _nuclear():
    rows = eia.fetch("nuclear-outages/us-nuclear-outages/data/", [
        ("frequency", "daily"), ("data[0]", "capacity"), ("data[1]", "outage"), ("start", "2019-01-01")])
    return {r["period"]: [round(float(r["capacity"]), 1), round(float(r["outage"]), 1)]
            for r in rows if r.get("capacity") not in (None, "") and r.get("outage") not in (None, "")}


def _nuclear_facilities():
    rows = eia.fetch("nuclear-outages/facility-nuclear-outages/data/", [
        ("frequency", "daily"), ("data[0]", "capacity"), ("data[1]", "outage"),
        ("start", (date.today() - timedelta(days=10)).isoformat())])
    if not rows:
        return {}
    d = max(r["period"] for r in rows)
    out = [[r["facilityName"], round(float(r["capacity"] or 0), 1), round(float(r["outage"] or 0), 1)]
           for r in rows if r["period"] == d]
    return {"date": d, "rows": sorted(out, key=lambda x: -x[2])}


def _battery(prev):
    """EIA-930 시간별 BAT(배터리 순출력, +방전 / −충전) → 일별 [방전 MWh, 충전 MWh]. 미국 중부시 기준 일자."""
    out = {k: dict(v) for k, v in (prev or {}).items()}
    last = min((max(v) for v in out.values() if v), default=None)
    start = (date.fromisoformat(last) - timedelta(days=3)).isoformat() if last else "2024-07-15"
    rows = eia.fetch("electricity/rto/fuel-type-data/data/", [
        ("frequency", "hourly"), ("data[0]", "value"), ("start", start + "T00"),
        *eia.facets("fueltype", ["BAT"]), *eia.facets("respondent", [r for r, _ in BAT_RESP])],
        max_rows=400_000)
    acc = {}
    for r in rows:
        if r.get("value") in (None, ""):
            continue
        t = datetime.strptime(r["period"], "%Y-%m-%dT%H") - timedelta(hours=6)
        d = acc.setdefault(r["respondent"], {}).setdefault(t.date().isoformat(), [0.0, 0.0, 0])
        v = float(r["value"])
        d[0 if v > 0 else 1] += v
        d[2] += 1
    for resp, days in acc.items():
        for d, (dis, chg, n) in days.items():
            if n >= 20:       # 하루 시간 수가 모자란 (경계·누락) 날 제외
                out.setdefault(resp, {})[d] = [round(dis), round(-chg)]
    return out


def collect(prev):
    raw = C.new(prev)
    errs = []
    C.attempt(raw, "h860", "EIA-860M 스냅샷", _update_860m, raw["_prev"].get("h860") or {}, errs)
    raw["errors"].extend(errs)
    C.attempt(raw, "nuc", "EIA 원전 정지(US)", _nuclear)
    C.attempt(raw, "nuc_fac", "EIA 원전 정지(발전소)", _nuclear_facilities)
    C.attempt(raw, "bat", "EIA-930 배터리", _battery, raw["_prev"].get("bat"))
    return C.finish(raw)


# ───────────────────────── 분석 ─────────────────────────
class Hist:
    def __init__(self, h):
        self.months = h["months"]
        self.idx = {m: i for i, m in enumerate(self.months)}
        self.gens = h["gens"]
        self.toks = {k: [dec(t) for t in v.split(",")] for k, v in h["hist"].items()}

    def cohort(self, s, m):
        """스냅샷 s 기준 (s, m] 에 가동 예정이던 발전기 → [(key, tech, state, mw, code, due)]"""
        i, a, b = self.idx[s], mi(s), mi(m)
        out = []
        for k, ts in self.toks.items():
            d = ts[i]
            if d and d[0] == "P" and a < d[1] <= b:
                t, st, mw = self.gens[k]
                out.append((k, t, st, mw, d[2], d[1]))
        return out

    def realization(self, n):
        """{tech: {target_month: %}} — n개월 전 스냅샷의 '그 달까지 가동 예정' 용량 중 그 달 스냅샷에서 가동."""
        out = {}
        for m in self.months:
            s = ym_of(mi(m) - n)
            if s not in self.idx:
                continue
            j = self.idx[m]
            tot, ok = {}, {}
            for k, t, st, mw, code, due in self.cohort(s, m):
                tot[t] = tot.get(t, 0) + mw
                d = self.toks[k][j]
                if d and d[0] == "O":
                    ok[t] = ok.get(t, 0) + mw
            for t, v in tot.items():
                if v:
                    out.setdefault(t, {})[m] = ok.get(t, 0) / v * 100
        return out

    def outcome(self, k, j):
        """스냅샷 j 에서의 결과: 가동/계획/취소/소멸"""
        d = self.toks[k][j]
        if d is None or d[0] == "R":
            return "소멸"
        return {"O": "가동", "P": "계획", "C": "취소"}[d[0]]

    def flows(self):
        """연속 스냅샷 쌍별 계획 발전기의 이동: {tech: {month: {가동,계획,취소,소멸,slip_mw,slip_sum,base}}}"""
        out = {}
        for j in range(1, len(self.months)):
            m = self.months[j]
            for k, ts in self.toks.items():
                d0 = ts[j - 1]
                if not d0 or d0[0] != "P":
                    continue
                t, st, mw = self.gens[k]
                f = out.setdefault(t, {}).setdefault(m, {"가동": 0, "계획": 0, "취소": 0, "소멸": 0,
                                                        "slip_mw": 0, "slip_sum": 0, "base": 0})
                o = self.outcome(k, j)
                if o == "소멸" and any(x and x[0] in "PO" for x in ts[j + 1:]):
                    o = "계획"      # 한 달 누락 후 재등장 — 소멸로 보지 않음
                f[o] += mw
                d1 = ts[j]
                if o == "계획" and d1 and d1[0] == "P":
                    f["base"] += mw
                    slip = d1[1] - d0[1]
                    if slip > 0:
                        f["slip_mw"] += mw
                        f["slip_sum"] += slip * mw
        return out

    def stages(self, t):
        """{month: {code: MW}} — 스냅샷별 계획 시트 단계별 용량"""
        out = {}
        for j, m in enumerate(self.months):
            acc = {}
            for k, ts in self.toks.items():
                d = ts[j]
                if d and d[0] == "P" and self.gens[k][0] == t:
                    c = d[2] if d[2] in STAGE_NAME else "OT"
                    acc[c] = acc.get(c, 0) + self.gens[k][2]
            out[m] = acc
        return out

    def actual_adds(self, t):
        """최신 스냅샷 기준 가동 개시 월별 용량(계획 목록을 거쳐 가동된 발전기)"""
        out = {}
        for k, ts in self.toks.items():
            d = ts[-1]
            if d and d[0] == "O" and d[1] is not None and self.gens[k][0] == t:
                m = ym_of(d[1])
                out[m] = out.get(m, 0) + self.gens[k][2]
        return out

    def due_in(self, s, m, t):
        """스냅샷 s 기준 정확히 m 월에 가동 예정이던 용량, 그 중 m 스냅샷에서 가동"""
        i, j, b = self.idx[s], self.idx[m], mi(m)
        tot = ok = 0
        for k, ts in self.toks.items():
            d = ts[i]
            if d and d[0] == "P" and d[1] == b and self.gens[k][0] == t:
                tot += self.gens[k][2]
                e = ts[j]
                if e and e[0] == "O":
                    ok += self.gens[k][2]
        return tot, ok


def cohort_detail(h, n=12):
    """최신 스냅샷 기준 n개월 전 코호트의 결과 분해 (기술·단계·주별) + 평균 지연."""
    last = h.months[-1]
    s = ym_of(mi(last) - n)
    if s not in h.idx:
        return None
    j = len(h.months) - 1
    rows = []
    for k, t, st, mw, code, due in h.cohort(s, last):
        o = h.outcome(k, j)
        d = h.toks[k][j]
        cur = d[1] if d and d[0] in ("P", "O") and d[1] is not None else None
        rows.append({"t": t, "st": st, "mw": mw, "code": code, "o": o,
                     "delay": max(0, cur - due) if cur is not None else None})
    return {"from": s, "to": last, "rows": rows}


def agg(rows, key):
    out = {}
    for r in rows:
        d = out.setdefault(key(r), {"mw": 0, "가동": 0, "계획": 0, "취소": 0, "소멸": 0, "dsum": 0, "dmw": 0})
        d["mw"] += r["mw"]
        d[r["o"]] += r["mw"]
        if r["delay"] is not None:
            d["dsum"] += r["delay"] * r["mw"]
            d["dmw"] += r["mw"]
    return out


def pct(a, b):
    return a / b * 100 if b else None


def r1(v, nd=1):
    return None if v is None else round(v, nd)


# ───────────────────────── 페이지 ─────────────────────────
def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "EIA-860M Monthly Generator Inventory (월별 아카이브)",
             "https://www.eia.gov/electricity/data/eia860m/")
    P.source(page, "EIA Nuclear Outages (NRC Power Reactor Status)", "https://www.eia.gov/nuclear/outages/")
    P.source(page, "EIA-930 Hourly Electric Grid Monitor (fuel type BAT)",
             "https://www.eia.gov/electricity/gridmonitor/")
    h860 = raw.get("h860")
    if h860 and len(h860.get("months", [])) >= 2:
        _build_860(page, Hist(h860), h860)
    _build_nuclear(page, raw.get("nuc") or {}, raw.get("nuc_fac") or {})
    _build_battery(page, raw.get("bat") or {}, (h860 or {}).get("op_mw", {}))
    for e in raw.get("errors", []):
        P.error(page, e)
    page["notes"] += [
        "실현율 = N개월 전 스냅샷에서 '이후 N개월 안에 가동 예정'이던 발전기 용량 중, 그 달 스냅샷에서 Operating 시트에 있는 비율 "
        "(Plant ID + Generator ID 로 같은 발전기를 추적, 용량은 명판 MW·AC).",
        "지연 = 연속한 두 스냅샷 사이 같은 발전기의 예정 가동월이 뒤로 밀린 경우. 취소 = 'Canceled or Postponed' 시트로 이동, "
        "소멸 = 어느 시트에도 없고 이후에도 재등장하지 않음(발전기 ID 변경·중복 정리 포함 가능).",
        POLICY_NOTE,
        "연결 종목: 한화솔루션(큐셀 미국 공장)·OCI — 태양광 실현율·지연 / LG에너지솔루션·삼성SDI·서진시스템 — ESS 실현율·방전 / "
        "두산에너빌리티·원전 기자재 — 원전 가동률. 대조: First Solar(태양광), Fluence(ESS).",
    ]
    return page


def _build_860(page, h, raw860):
    last = h.months[-1]
    real12, real3 = h.realization(12), h.realization(3)
    flows = h.flows()
    det = cohort_detail(h, 12)
    by_t = agg(det["rows"], lambda r: r["t"]) if det else {}

    # KPI
    for t in ("S", "B"):
        k, v = S.last(real12.get(t, {}))
        prev = real12.get(t, {}).get(ym_of(mi(k) - 12)) if k else None
        P.kpi(page, f"{NAME[t]} 12개월 계획 실현율", v, "%", None if v is None or prev is None else v - prev,
              delta_label="전년 대비", delta_unit="%p", asof=f"{ym_of(mi(k) - 12)} 계획 → {k}" if k else None)
    for t in ("S", "B"):
        d = by_t.get(t)
        if d and d["dmw"]:
            P.kpi(page, f"{NAME[t]} 평균 지연(12개월 코호트·정시 포함)", d["dsum"] / d["dmw"], "개월",
                  asof=f"{det['from']} 계획 대비 {det['to']}")
    recent = h.months[-12:]
    for t in ("S", "B"):
        exits = sum(flows.get(t, {}).get(m, {}).get("취소", 0) + flows.get(t, {}).get(m, {}).get("소멸", 0)
                    for m in recent)
        P.kpi(page, f"{NAME[t]} 취소·소멸 (최근 12개월)", exits / 1000, "GW", digits=2,
              asof=f"{recent[0]}~{recent[-1]} 스냅샷")

    # 실현율 추이
    for n, real in ((12, real12), (3, real3)):
        ks = sorted(set().union(*[set(v) for v in real.values()])) if real else []
        P.chart(page, f"real{n}", f"{n}개월 전 계획 실현율 — 기술별", ks,
                [P.series(NAME[t], S.align(ks, real.get(t, {}), 1), slot=SLOT[t]) for t in ("S", "B", "W")],
                unit="%", note=f"x = 평가 월. {n}개월 전 스냅샷에서 (그 시점, 평가 월] 사이 가동 예정이던 용량 중 평가 월에 가동 중인 비율")

    # 3개월 전 계획 vs 실제 (월별 GW)
    for t in ("S", "B"):
        ks, plan, ok = [], {}, {}
        for m in h.months:
            s = ym_of(mi(m) - 3)
            if s in h.idx:
                a, b = h.due_in(s, m, t)
                ks.append(m)
                plan[m], ok[m] = a / 1000, b / 1000
        adds = {k: v / 1000 for k, v in h.actual_adds(t).items()}
        P.chart(page, f"plan_vs_{t}", f"{NAME[t]}: 3개월 전 '이 달 가동' 계획 vs 실제", ks, [
            P.series("3개월 전 계획(해당 월)", S.align(ks, plan, 2), slot=-1),
            P.series("그 중 해당 월 가동", S.align(ks, ok, 2), slot=SLOT[t]),
            P.series("실제 신규 가동(전체, 최신 스냅샷 기준)", S.align(ks, adds, 2), kind="line", slot=3)],
            kind="bar", unit="GW", note="실제 신규 가동 = 최신 스냅샷의 가동 개시 월 기준(860M 계획 목록을 거친 발전기). 늦은 신고로 최근 월은 사후 상향될 수 있음")

    # 지연 지수
    fk = h.months[1:]
    P.chart(page, "slip_share", "지연 비중 — 직전 스냅샷 대비 예정 가동월이 밀린 용량 / 계속 계획 중 용량", fk,
            [P.series(NAME[t], S.align(fk, {m: pct(f["slip_mw"], f["base"]) for m, f in flows.get(t, {}).items()
                                             if f["base"]}, 1), slot=SLOT[t]) for t in ("S", "B", "W")],
            unit="%", note=POLICY_NOTE)
    P.chart(page, "slip_months", "지연 시 평균 연기 개월 (용량 가중)", fk,
            [P.series(NAME[t], S.align(fk, {m: f["slip_sum"] / f["slip_mw"] for m, f in flows.get(t, {}).items()
                                             if f["slip_mw"]}, 1), slot=SLOT[t]) for t in ("S", "B", "W")],
            unit="개월")

    # 취소·소멸 / 완료 흐름
    P.chart(page, "exits", "취소·소멸 용량 (직전 스냅샷 계획 → 이번 스냅샷)", fk,
            [P.series(f"{NAME[t]} {o}", S.align(fk, {m: f[o] / 1000 for m, f in flows.get(t, {}).items()}, 2),
                      slot=SLOT[t] if o == "취소" else (5 if t == "S" else 6))
             for t in ("S", "B") for o in ("취소", "소멸")],
            kind="bar", unit="GW", stack=True, note="취소 = Canceled or Postponed 시트로 이동, 소멸 = 목록에서 사라짐")
    P.chart(page, "completed", "계획 → 가동 전환 용량 (월별)", fk,
            [P.series(NAME[t], S.align(fk, {m: f["가동"] / 1000 for m, f in flows.get(t, {}).items()}, 2),
                      slot=SLOT[t]) for t in ("S", "B", "W")], kind="bar", unit="GW", stack=True)

    # 단계별 용량 추이
    for t in ("S", "B"):
        st = h.stages(t)
        P.chart(page, f"stage_{t}", f"{NAME[t]} 계획 파이프라인 단계별 용량 (스냅샷별)", h.months,
                [P.series(nm, [round(st[m].get(c, 0) / 1000, 2) for m in h.months], slot=i if i < 7 else -1)
                 for i, (c, nm) in enumerate(STAGES)], kind="area", unit="GW", stack=True,
                note="P 계획 → L 인허가 중 → T 인허가 완료 → U·V 공사 중 → TS 시운전")

    if not det:
        return
    # 단계별 실현율 표 (12개월 코호트)
    rows = []
    for t in ("S", "B", "W"):
        g = agg([r for r in det["rows"] if r["t"] == t], lambda r: r["code"] if r["code"] in STAGE_NAME else "OT")
        for c, nm in STAGES:
            d = g.get(c)
            if d and d["mw"]:
                rows.append([NAME[t], nm, r1(d["mw"] / 1000, 2), r1(pct(d["가동"], d["mw"])),
                             r1(pct(d["계획"], d["mw"])), r1(pct(d["취소"] + d["소멸"], d["mw"])),
                             r1(d["dsum"] / d["dmw"] if d["dmw"] else None)])
    P.table(page, f"계획 단계별 실현율 — {det['from']} 스냅샷에서 12개월 내 가동 예정이던 물량의 {det['to']} 결과",
            ["기술", "당시 단계", "코호트 GW", "가동 %", "여전히 계획 %", "취소·소멸 %", "평균 지연(개월)"], rows,
            note="공사 중(U·V) 단계에서 출발한 물량이 얼마나 더 확실한지 비교")

    # 주별 실현율 표
    st = agg([r for r in det["rows"] if r["t"] in ("S", "B")], lambda r: (r["st"], r["t"]))
    states = {}
    for (s, t), d in st.items():
        states.setdefault(s, {})[t] = d
    top = sorted(states, key=lambda s: -sum(d["mw"] for d in states[s].values()))[:12]
    rows = []
    for s in top:
        row = [s]
        for t in ("S", "B"):
            d = states[s].get(t)
            row += [r1(d["mw"] / 1000, 2) if d else None, r1(pct(d["가동"], d["mw"])) if d else None,
                    r1(pct(d["취소"] + d["소멸"], d["mw"])) if d else None]
        rows.append(row)
    P.table(page, f"주별 12개월 실현율 상위 12 ({det['from']} 계획 → {det['to']})",
            ["주", "태양광 코호트 GW", "태양광 가동 %", "태양광 취소·소멸 %", "ESS 코호트 GW", "ESS 가동 %", "ESS 취소·소멸 %"],
            rows)

    # 기술별 요약 표
    rows = []
    for t in ("S", "B", "W", "N"):
        d = by_t.get(t)
        if d and d["mw"]:
            rows.append([NAME[t], r1(d["mw"] / 1000, 2), r1(pct(d["가동"], d["mw"])), r1(pct(d["계획"], d["mw"])),
                         r1(pct(d["취소"], d["mw"])), r1(pct(d["소멸"], d["mw"])),
                         r1(d["dsum"] / d["dmw"] if d["dmw"] else None)])
    P.table(page, f"기술별 12개월 코호트 결과 ({det['from']} 계획 → {det['to']})",
            ["기술", "코호트 GW", "가동 %", "여전히 계획 %", "취소 %", "소멸 %", "평균 지연(개월)"], rows,
            note=f"스냅샷 {len(h.months)}개: {h.months[0]} ~ {h.months[-1]}")


def _build_nuclear(page, nuc, fac):
    if not nuc:
        return
    ks = sorted(nuc)
    avail = {k: (c - o) / c * 100 for k, (c, o) in nuc.items() if c}
    on = {k: (c - o) / 1000 for k, (c, o) in nuc.items()}
    off = {k: o / 1000 for k, (c, o) in nuc.items()}
    k, v = S.last(avail)
    m30 = S.rolling(avail, 30)
    k30, v30 = S.last(m30)
    prev = m30.get(S.shift_year(k30)) if k30 else None
    P.kpi(page, "원전 가동률 (최신일)", v, "%", asof=k)
    P.kpi(page, "원전 가동률 30일 평균", v30, "%", None if prev is None else v30 - prev,
          delta_label="전년 동기 대비", delta_unit="%p", asof=k30)
    P.chart(page, "nuc_mw", "미국 원전 가동·정지 용량 (일별)", ks, [
        P.series("가동 용량", S.align(ks, on, 2), slot=SLOT["N"]),
        P.series("정지 용량", S.align(ks, off, 2), slot=-1)], kind="area", unit="GW", stack=True, window=730,
        note="NRC 일일 원자로 상태 기준. 봄(3~5월)·가을(9~11월) 계획예방정비 시즌에 정지 용량이 늘어남")
    mon = S.daily_to_monthly(avail, "mean")
    years = sorted({m[:4] for m in mon})[-6:]
    mx = [f"{i:02d}월" for i in range(1, 13)]
    P.chart(page, "nuc_season", "월평균 원전 가동률 — 연도별 겹쳐보기", mx,
            [P.series(y, [r1(mon.get(f"{y}-{i:02d}"), 2) for i in range(1, 13)],
                      slot=(i if i < 7 else -1) if y != years[-1] else 4) for i, y in enumerate(years)],
            unit="%", note="정비 시즌의 깊이·길이 비교")
    if fac.get("rows"):
        rows = [[n, round(c), round(o), r1(pct(o, c))] for n, c, o in fac["rows"] if o > 0]
        P.table(page, f"정지·감발 중인 원전 ({fac['date']})", ["발전소", "용량 MW", "정지 MW", "정지 %"], rows)


def _build_battery(page, bat, op_mw):
    if not bat:
        return
    ks = sorted(set().union(*[set(v) for v in bat.values()]))
    dis = {r: {d: v[0] / 1000 for d, v in bat.get(r, {}).items()} for r, _ in BAT_RESP}
    P.chart(page, "bat_daily", "배터리 일 방전량 (EIA-930, 시간별 + 합계)", ks,
            [P.series(nm, S.align(ks, dis[r], 2), slot=SLOT["B"] if r == "ERCO" else 3) for r, nm in BAT_RESP],
            unit="GWh", window=365, note="CAISO 는 EIA-930 에 배터리(BAT)를 따로 보고하지 않아 US48 합계에서도 빠짐")
    for r, nm in BAT_RESP:
        m30 = S.rolling(dis[r], 30)
        k, v = S.last(m30)
        prev = m30.get(S.shift_year(k)) if k else None
        P.kpi(page, f"{nm} 배터리 일 방전 (30일 평균)", v, "GWh", None if prev is None or not prev else (v / prev - 1) * 100,
              asof=k)
    # ERCOT 방전 시간 = 월평균 일 방전 MWh / 텍사스 배터리 가동 MW (860M)
    mon = S.daily_to_monthly({d: v[0] for d, v in bat.get("ERCO", {}).items()}, "mean")
    tx = {m: d.get("B", {}).get("TX") for m, d in op_mw.items() if d.get("B", {}).get("TX")}
    hrs = {m: mon[m] / tx[m] for m in mon if m in tx}
    if hrs:
        P.chart(page, "bat_hours", "ERCOT 배터리 활용 — 일 방전 시간 (방전 MWh ÷ 텍사스 배터리 가동 MW)", sorted(hrs),
                [P.series("일 평균 방전 시간", S.align(sorted(hrs), hrs, 2), slot=SLOT["B"])], unit="시간/일",
                note="설치 용량(860M 텍사스 Batteries 명판 MW) 대비 실제 하루 몇 시간분을 방전하는지 — 1 이상이면 하루 1사이클 이상 수준")
    if tx:
        tk = sorted(tx)
        P.chart(page, "bat_cap", "배터리 가동 용량 (EIA-860M Operating)", tk, [
            P.series(s, S.align(tk, {m: op_mw[m].get("B", {}).get(s, 0) / 1000 for m in tk}, 2),
                     slot=i) for i, s in enumerate(("TX", "CA", "AZ", "NV", "FL"))], unit="GW")
