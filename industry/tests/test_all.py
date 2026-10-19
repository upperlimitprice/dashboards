"""오프라인 테스트 — 파서 + 모든 페이지 build/render 를 합성 데이터로 검증.

  python -m unittest discover -s tests -t .
"""
import io
import math
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import page as P                       # noqa: E402
from core import series as S                     # noqa: E402
from core.env import scrub                       # noqa: E402
from core.sources import customs, eia860m, fred, gscpi, sec, twse   # noqa: E402
import pages                                     # noqa: E402


def months(start="2018-01", end="2026-08"):
    y, m = map(int, start.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= end:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def wave(i, base, amp=0.1, trend=0.005):
    return base * (1 + trend * i) * (1 + amp * math.sin(i / 2))


def trade(base, start="2019-01"):
    return {k: {"exp_usd": wave(i, base), "imp_usd": wave(i, base * .3),
                "exp_kg": wave(i, base / 20, .05), "imp_kg": wave(i, base / 60, .05)}
            for i, k in enumerate(months(start))}


def monthly(base, start="2015-01"):
    return {k: wave(i, base) for i, k in enumerate(months(start))}


def xlsx(sheets):
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def fake_860m():
    hdr = ["Entity ID", "Plant State", "Nameplate Capacity (MW)", "Technology", "Operating Year",
           "Planned Retirement Year", "Status", "Planned Operation Month", "Planned Operation Year", "Retirement Year"]
    techs = ["Solar Photovoltaic", "Batteries", "Onshore Wind Turbine", "Natural Gas Fired Combined Cycle",
             "Conventional Steam Coal", "Nuclear", "Conventional Hydroelectric", "Landfill Gas"]
    op, pl, rt = [["EIA-860M title row"], hdr], [["title"], hdr], [["title"], hdr]
    for i in range(400):
        t = techs[i % len(techs)]
        op.append([i, "TX" if i % 3 else "VA", 50 + i % 7 * 10, t, 2005 + i % 22,
                   2030 if t.endswith("Coal") else None, "(OP) Operating", None, None, None])
        pl.append([i, ["TX", "CA", "AZ", "VA"][i % 4], 80 + i % 5 * 20, t, None, None,
                   ["(V) Under construction, more than 50 percent complete", "(U) Under construction",
                    "(P) Planned", "(T) Regulatory approvals received"][i % 4], 1 + i % 12, 2026 + i % 5, None])
        rt.append([i, "OH", 30, t, 1980, None, "(RE) Retired", None, None, 2015 + i % 11])
    op.append(["NOTE: footnote row", None, "n/a"])
    return xlsx({"Operating": op, "Planned": pl, "Retired": rt})


def fake_raw():
    today = date(2026, 10, 1)
    days = [(today - timedelta(days=d)).isoformat() for d in range(4 * 365 + 40, 0, -1)]
    demand = {code: {d: wave(i, base, .15, .0001) for i, d in enumerate(days)}
              for code, base in (("US48", 11e6), ("PJM", 2.2e6), ("ERCO", 1.3e6), ("MISO", 1.8e6), ("CISO", .65e6))}
    s860 = {"file_month": "2026-08", **eia860m.summarize(eia860m.parse(fake_860m()))}
    capex = {t: {S.quarter_of(f"{y}-{m:02d}-28"): wave(i, b * 1e9, .05, .03)
                 for i, (y, m) in enumerate((y, m) for y in range(2018, 2027) for m in (3, 6, 9, 12) if f"{y}-{m:02d}" <= "2026-06")}
             for t, b in (("MSFT", 10), ("AMZN", 12), ("GOOGL", 9), ("META", 7), ("ORCL", 2), ("CRWV", 1))}
    from pages.solar import _solar_subset
    return {
        "gen_capacity": {"errors": [], "missing": [], "eia860m": s860,
                         "pipeline_history": {"2026-07": {"planned_gw": 400, "uc_gw": 90}, "2026-08": {"planned_gw": 410, "uc_gw": 95}}},
        "grid": {"errors": [], "missing": [], "demand": demand},
        "auto": {"errors": [], "missing": [], "car": trade(5e9), "bev": trade(8e8, "2022-01"),
                 "hev": trade(1e9, "2022-01"), "phev": trade(1e8, "2022-01"), "parts": trade(1.8e9), "battery": trade(6e8)},
        "datacenter": {"errors": [], "missing": [], "capex": capex,
                       "retail": {s: monthly(b) for s, b in (("VA", 6000), ("TX", 15000), ("GA", 5000), ("AZ", 3000), ("OH", 4000), ("US", 120000))}},
        "freight": {"errors": ["FRED RAILFRTINTERMODALD11: HTTPError: 404"], "missing": [],
                    **{sid: monthly(100) for sid, _ in pages.load("freight").FRED[:-1]}, "gscpi": monthly(0.2)},
        "mlcc_lead": {"errors": [], "missing": [], "kr_mlcc": trade(3e8, "2018-01"),
                      "tw_latest": {"2327": {"ym": "2026-09", "name": "國巨", "rev": 1.2e7, "rev_ly": 1e7, "yoy": 20.0, "mom": 3.1}},
                      "tw_history": {"2327": {"2026-08": {"rev": 1.1e7, "yoy": 15.0, "mom": 1.0}, "2026-09": {"rev": 1.2e7, "yoy": 20.0, "mom": 3.1}}}},
        "solar": {"errors": [], "missing": ["EIA_API_KEY 미설정"], "us860m": _solar_subset(s860),
                  "kr_module": trade(5e7, "2022-01"), "kr_cell": trade(1e7, "2022-01")},
    }


class Parsers(unittest.TestCase):
    def test_sec_quarterly_from_ytd(self):
        facts = [  # FY: 7/1~6/30 (MSFT 형태) — Q1 단독, H1/9M 누적, 연간
            {"start": "2024-07-01", "end": "2024-09-30", "val": 10},
            {"start": "2024-07-01", "end": "2024-12-31", "val": 25},
            {"start": "2024-07-01", "end": "2025-03-31", "val": 45},
            {"start": "2024-07-01", "end": "2025-06-30", "val": 70},
        ]
        self.assertEqual(sec.quarterly(facts), {"2024-09-30": 10, "2024-12-31": 15, "2025-03-31": 20, "2025-06-30": 25})

    def test_customs_xml(self):
        xml = b"""<response><header><resultCode>00</resultCode></header><body><items>
          <item><year>2026.07</year><hsCd>8703</hsCd><expDlr>5,000</expDlr><impDlr>100</impDlr><expWgt>200</expWgt><impWgt>5</impWgt></item>
          <item><year>2026.07</year><hsCd>870380</hsCd><expDlr>1000</expDlr><impDlr>0</impDlr><expWgt>50</expWgt><impWgt>0</impWgt></item>
          <item><year>\xec\xb4\x9d\xea\xb3\x84</year><expDlr>999999</expDlr></item></items></body></response>"""
        out = customs.parse_xml(xml)
        self.assertEqual(list(out), ["2026-07"])
        self.assertEqual(out["2026-07"]["exp_usd"], 6000)

    def test_customs_error(self):
        with self.assertRaises(RuntimeError):
            customs.parse_xml(b"<response><header><resultCode>30</resultCode><resultMsg>KEY</resultMsg></header></response>")

    def test_fred_csv(self):
        self.assertEqual(fred.parse_csv("observation_date,X\n2026-01-01,1.5\n2026-02-01,.\n"), {"2026-01": 1.5})

    def test_twse(self):
        rows = [{"資料年月": "11509", "公司代號": "2327", "公司名稱": "國巨", "營業收入-當月營收": "12,000,000",
                 "營業收入-去年當月營收": "10,000,000", "營業收入-上月比較增減(%)": "3.1", "營業收入-去年同月增減(%)": "20"},
                {"資料年月": "11509", "公司代號": "2330", "公司名稱": "台積電"}]
        out = twse.parse(rows, {"2327"})
        self.assertEqual(out["2327"]["ym"], "2026-09")
        self.assertEqual(out["2327"]["rev"], 12e6)
        self.assertEqual(out["2327"]["yoy"], 20)

    def test_860m(self):
        s = eia860m.summarize(eia860m.parse(fake_860m()))
        self.assertIn("태양광", s["operating_by_tech"])
        self.assertIn("기타", s["operating_by_tech"])          # Landfill Gas
        self.assertTrue(s["planned_uc_by_year"])
        self.assertEqual(eia860m.status_code("(V) Under construction"), "V")

    def test_gscpi(self):
        b = xlsx({"GSCPI Monthly Data": [["Date", "GSCPI"], [datetime(2026, 8, 31), 0.42], [datetime(2026, 9, 30), 0.5]]})
        self.assertEqual(gscpi.parse(b), {"2026-08": 0.42, "2026-09": 0.5})

    def test_series(self):
        d = {"2025-01": 100, "2026-01": 110}
        self.assertAlmostEqual(S.yoy_pct(d)["2026-01"], 10)
        self.assertEqual(S.shift_year("2026Q3"), "2025Q3")
        self.assertEqual(S.rolling({"a": 1, "b": 2, "c": 3}, 2, "sum"), {"b": 3, "c": 5})

    def test_scrub(self):
        os.environ["EIA_API_KEY"] = "SECRETKEY123"
        self.assertNotIn("SECRETKEY123", scrub("https://api.eia.gov/v2/x?api_key=SECRETKEY123"))


class Pages(unittest.TestCase):
    def test_build_and_render_every_page(self):
        raws = fake_raw()
        for mod in pages.all_modules():
            with self.subTest(page=mod.KEY):
                page = mod.build(raws[mod.KEY])
                self.assertTrue(page["kpis"], "KPI 없음")
                self.assertTrue(page["charts"], "차트 없음")
                for c in page["charts"]:
                    for s in c["series"]:
                        self.assertEqual(len(s["data"]), len(c["x"]), f"{c['id']}/{s['name']} 길이 불일치")
                html = P.render(page)
                self.assertIn("<title>", html)
                self.assertNotIn("__DATA__", html)

    def test_empty_raw_does_not_crash(self):
        for mod in pages.all_modules():
            with self.subTest(page=mod.KEY):
                mod.build({"errors": [], "missing": []})


if __name__ == "__main__":
    unittest.main()
