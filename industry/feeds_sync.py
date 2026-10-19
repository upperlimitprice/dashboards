# -*- coding: utf-8 -*-
"""manual/*.csv 자동 채움 — 무료 API가 없던 3개 지표를 기존 트래커·공개 페이지에서 가져온다 (run.py 전에 실행).
- solar_prices.csv  ← ~/solar-tracker (InfoLink 주간 스팟, SunSirs 폴리실리콘 일별)
- mlcc_leadtime.csv ← ~/전자부품트렌드 (Future Electronics 월간 리드타임, 세라믹 커패시터 행)
- freight_spot.csv  ← Drewry WCI(웹페이지) + 상하이해운거래소 SCFI(JSON) — 실행마다 누적
실행: .venv/bin/python feeds_sync.py"""
import csv
import glob
import json
import re
from datetime import datetime
from pathlib import Path

from core.env import MANUAL
from core.http import get

HOME = Path.home()
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def write(name, header_comment, fields, rows):
    p = MANUAL / name
    with p.open("w", encoding="utf-8", newline="") as f:
        f.write(header_comment.rstrip() + "\n")
        w = csv.writer(f)
        w.writerow(fields)
        w.writerows(rows)
    return len(rows)


def read_rows(name):
    p = MANUAL / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return [r for r in csv.reader(l for l in f if not l.startswith("#"))][1:]


# ── 태양광 ──────────────────────────────────────────────────────────────
SOLAR_ITEMS = [  # (InfoLink 품목명, 표시명)
    ("Mono-grade polysilicon (RMB)", "폴리실리콘(RMB/kg)"),
    ("Mono N Type Wafer - 182-183.75mm / 130µm (RMB)", "N형 웨이퍼 182(RMB/장)"),
    ("TOPCon Cell - 182-183.75mm / 25.4%+ (RMB)", "TOPCon 셀 182(RMB/W)"),
    ("182*182-210mm/210mm Mono TOPCon Module (RMB)", "TOPCon 모듈(RMB/W)"),
    ("TOPCon Module - US assembled (USD, DDP)", "TOPCon 모듈 미국조립(USD/W)"),
    ("TOPCon Module - Europe projects - China made (USD, FOB)", "TOPCon 모듈 유럽향(USD/W)"),
]


def solar():
    d = json.loads((HOME / "solar-tracker/data/solar_prices.json").read_text(encoding="utf-8"))
    rows = []
    for dt, items in sorted(d.get("infolink", {}).items()):
        by = {x["item"]: x for x in items}
        for src, label in SOLAR_ITEMS:
            x = by.get(src)
            if x and x.get("avg") is not None:
                rows.append([dt, label, x["avg"]])
    poly = HOME / "solar-tracker/data/poly_daily.json"
    if poly.exists():
        for dt, v in sorted(json.loads(poly.read_text()).items()):
            rows.append([dt, "폴리실리콘 SunSirs 일별(RMB/kg)", round(v / 1000, 2)])
    return write("solar_prices.csv", "# 자동 생성 — feeds_sync.py (InfoLink 주간 스팟·SunSirs 일별, ~/solar-tracker). 직접 수정하지 마세요.",
                 ["date", "item", "value"], rows)


# ── MLCC 리드타임 ──────────────────────────────────────────────────────
MLCC_VENDORS = {"Murata", "Samsung Electro-Mechanics", "TAIYO YUDEN", "TDK", "YAGEO", "KYOCERA AVX", "Walsin Technology Corporation", "Vishay"}


def _weeks(s):
    nums = [int(n) for n in re.findall(r"\d+", s or "")]
    if not nums:
        return None
    return (nums[0], nums[-1] if len(nums) > 1 else nums[0])


def mlcc():
    rows = []
    for f in sorted(glob.glob(str(HOME / "전자부품트렌드/data/*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        month = d.get("month") or Path(f).stem
        for cat in d.get("categories", []):
            if cat.get("category") != "Passives":
                continue
            for m in cat.get("manufacturers", []):
                if m.get("name") not in MLCC_VENDORS:
                    continue
                for r in m.get("rows", []):
                    p = r.get("product", "")
                    if "Ceramic" not in p:
                        continue
                    w = _weeks(r.get("lead_time"))
                    if not w:
                        continue
                    kind = "1uF 미만" if "Less than" in p else "1uF 이상" if "greater" in p else "차량용" if "Automotive" in p else p.replace("Surface Mount General Capacitors - ", "")
                    rows.append([f"{month[:7]}-15", m["name"], f"세라믹 {kind}", w[0], w[1], f"Future Electronics {month[:7]} (추세 {r.get('trend', '')}, 가격 {r.get('pricing', '')})"])
    return write("mlcc_leadtime.csv", "# 자동 생성 — feeds_sync.py (Future Electronics 월간 Market Conditions, ~/전자부품트렌드). 직접 수정하지 마세요.",
                 ["date", "vendor", "category", "weeks_min", "weeks_max", "source"], rows)


# ── 컨테이너 운임 ──────────────────────────────────────────────────────
def freight():
    old = {(r[0], r[1]): r[2] for r in read_rows("freight_spot.csv") if len(r) >= 3}
    errs = []
    try:  # 상하이해운거래소 SCFI 종합 (이번 주·지난주)
        j = json.loads(get("https://en.sse.net.cn/currentIndex?indexName=scfi", headers=UA, timeout=30))["data"]
        comp = next(x for x in j["lineDataList"] if x.get("dataItemTypeName") == "SCFI_T" or x["properties"].get("lineName_EN") == "Comprehensive Index")
        old[(j["currentDate"], "SCFI 종합")] = round(comp["currentContent"], 1)
        old[(j["lastDate"], "SCFI 종합")] = round(comp["lastContent"], 1)
    except Exception as e:  # noqa: BLE001
        errs.append(f"SCFI: {e}")
    try:  # Drewry WCI 종합 ($/FEU) — 페이지 본문 "composite ... $4,485 per 40ft"
        h = get("https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry", headers=UA, timeout=40).decode("utf-8", "replace")
        txt = re.sub(r"<[^>]+>", " ", h)
        m = re.search(r"World Container Index[^.]{0,200}?\$([\d,]{3,6}) per 40ft", txt) or re.search(r"\$([\d,]{3,6}) per 40ft container", txt)
        dm = re.search(r"(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (20\d\d)", txt)
        if m:
            d = datetime.strptime(" ".join(dm.groups()), "%d %b %Y").strftime("%Y-%m-%d") if dm else datetime.now().strftime("%Y-%m-%d")
            old[(d, "WCI 종합($/FEU)")] = float(m.group(1).replace(",", ""))
        else:
            errs.append("WCI: 페이지에서 종합지수를 찾지 못함")
    except Exception as e:  # noqa: BLE001
        errs.append(f"WCI: {e}")
    rows = [[d, k, v] for (d, k), v in sorted(old.items())]
    write("freight_spot.csv", "# 자동 누적 — feeds_sync.py (상하이해운거래소 SCFI 종합 · Drewry WCI 종합 $/FEU). 매 실행 시 최신값 추가.",
          ["date", "index", "value"], rows)
    return len(rows), errs


def main():
    out, errs = {}, []
    for name, fn in (("solar", solar), ("mlcc", mlcc)):
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001
            errs.append(f"{name}: {type(e).__name__}: {e}")
    try:
        out["freight"], fe = freight()
        errs += fe
    except Exception as e:  # noqa: BLE001
        errs.append(f"freight: {e}")
    print("feeds_sync", out, "오류" if errs else "", errs)
    (MANUAL.parent / "logs").mkdir(exist_ok=True)
    (MANUAL.parent / "logs" / "feeds_sync_errors.json").write_text(json.dumps(errs, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
