"""미국 발전설비 — 가동·신규 추가·계획 파이프라인·폐지 (EIA-860M)."""
from core import collect as C
from core import page as P
from core.sources import eia860m

KEY = "gen_capacity"
TITLE = "⚡ 미국 발전설비 파이프라인"
SUBTITLE = "EIA-860M 월간 발전기 인벤토리 — 기술별 가동 용량·연도별 신규·계획(공사중)·폐지"
NEEDS = []

SLOT = {g: i for i, g in enumerate(eia860m.GROUP_ORDER[:8])}
SLOT["기타"] = -1


def collect(prev):
    raw = C.new(prev)

    def fetch():
        content, ym = eia860m.latest()
        return {"file_month": ym, **eia860m.summarize(eia860m.parse(content))}
    snap = C.attempt(raw, "eia860m", "EIA-860M", fetch)
    # 매달 파이프라인 총량 스냅샷을 누적 → '계획 물량이 늘고 있나' 추세
    hist = dict(raw["_prev"].get("pipeline_history", {}))
    if snap:
        planned = snap["planned_by_year"]
        hist[snap["file_month"]] = {
            "planned_gw": sum(sum(v.values()) for v in planned.values()) / 1000,
            "uc_gw": sum(sum(v.values()) for v in snap["planned_uc_by_year"].values()) / 1000,
        }
    raw["pipeline_history"] = hist
    return C.finish(raw)


def stacked(page, cid, title, by_year, years, note="", kind="bar"):
    groups = [g for g in eia860m.GROUP_ORDER
              if any(by_year.get(str(y), {}).get(g) for y in years)]
    P.chart(page, cid, title, [str(y) for y in years],
            [P.series(g, [round(by_year.get(str(y), {}).get(g, 0) / 1000, 2) for y in years],
                      slot=SLOT.get(g, -1)) for g in groups],
            kind=kind, unit="GW", stack=True, note=note)


def build(raw):
    page = P.new(KEY, TITLE, SUBTITLE)
    P.source(page, "EIA-860M Monthly Generator Inventory", "https://www.eia.gov/electricity/data/eia860m/")
    s = raw.get("eia860m")
    if not s:
        return page
    ym = s["file_month"]
    years_planned = sorted(int(y) for y in s["planned_by_year"])
    this_year = int(ym[:4])
    years_planned = [y for y in years_planned if this_year <= y <= this_year + 5]

    op_total = sum(s["operating_by_tech"].values()) / 1000
    planned_total = sum(sum(v.values()) for y, v in s["planned_by_year"].items()) / 1000
    uc_total = sum(sum(v.values()) for v in s["planned_uc_by_year"].values()) / 1000
    nxt = sorted(s["planned_monthly"])
    nxt12 = [k for k in nxt if k > ym][:12]
    nxt12_gw = sum(sum(s["planned_monthly"][k].values()) for k in nxt12) / 1000
    se_share = 0
    if planned_total:
        se_share = sum(v.get("태양광", 0) + v.get("ESS", 0) for v in s["planned_by_year"].values()) / 1000 / planned_total * 100
    adds_this = sum(s["additions_by_year"].get(str(this_year), {}).values()) / 1000

    P.kpi(page, "가동 중 설비", op_total, "GW", asof=f"EIA-860M {ym}")
    P.kpi(page, "향후 12개월 계획 추가", nxt12_gw, "GW", asof=f"{nxt12[0] if nxt12 else ''}~")
    P.kpi(page, "공사 중(U·V)", uc_total, "GW")
    P.kpi(page, "계획 중 태양광+ESS 비중", se_share, "%")
    P.kpi(page, f"{this_year}년 누적 신규 가동", adds_this, "GW")

    stacked(page, "planned", "연도별 계획 신규 용량 (전체 상태)", s["planned_by_year"], years_planned,
            note="인허가 전 단계(P·L)까지 포함 — 실제 가동은 이보다 적게 나오는 경향")
    stacked(page, "planned_uc", "연도별 계획 신규 용량 — 공사 중(U·V)만", s["planned_uc_by_year"], years_planned)
    hist_years = [y for y in range(this_year - 15, this_year + 1)]
    stacked(page, "adds", "연도별 실제 신규 가동 (가동 연도 기준)", s["additions_by_year"], hist_years)
    ret = {}
    for src in (s["retired_by_year"], s["planned_retire_by_year"]):
        for y, d in src.items():
            for g, v in d.items():
                ret.setdefault(y, {}).setdefault(g, 0)
                ret[y][g] += v
    stacked(page, "retire", "연도별 폐지 (실적 + 계획)", ret,
            list(range(this_year - 10, this_year + 6)), note=f"{this_year}년 이후는 사업자 제출 계획")

    op = sorted(s["operating_by_tech"].items(), key=lambda kv: -kv[1])
    P.chart(page, "op", "기술별 가동 용량", [g for g, _ in op],
            [P.series("가동 용량", [round(v / 1000, 1) for _, v in op])], kind="bar", unit="GW")

    hist = raw.get("pipeline_history", {})
    if len(hist) >= 2:
        ks = sorted(hist)
        P.chart(page, "pipe_hist", "계획 파이프라인 총량 추이 (매월 스냅샷)", ks, [
            P.series("계획 전체", [round(hist[k]["planned_gw"], 1) for k in ks]),
            P.series("공사 중", [round(hist[k]["uc_gw"], 1) for k in ks])], unit="GW")

    states = sorted(s["planned_by_state"].items(), key=lambda kv: -kv[1]["all"])[:15]
    P.table(page, "주별 계획 용량 상위 15 (GW)", ["주", "계획 전체", "공사 중", "태양광+ESS"],
            [[st, round(d["all"] / 1000, 2), round(d["uc"] / 1000, 2), round(d["solar_ess"] / 1000, 2)]
             for st, d in states])
    page["notes"].append("계획 용량은 사업자가 EIA에 제출한 일정 기준이며, 지연·취소가 잦습니다. 공사 중(U·V) 수치가 더 보수적인 지표입니다.")
    return page
