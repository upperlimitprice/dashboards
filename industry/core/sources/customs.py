"""관세청 품목별 수출입실적 (공공데이터포털 data.go.kr, 키: DATA_GO_KR_KEY — '디코딩' 키).

https://www.data.go.kr/data/15100475/openapi.do  — 조회 기간은 1년 이내로 나눠 호출.
"""
import re
import xml.etree.ElementTree as ET
from datetime import date

from ..env import require
from ..http import get

URL = "https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"
YM = re.compile(r"^(\d{4})\.(\d{2})$")


def _num(s):
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_xml(content):
    root = ET.fromstring(content)
    code = root.findtext(".//resultCode")
    if code not in (None, "00"):
        raise RuntimeError(f"관세청 API 오류 {code}: {root.findtext('.//resultMsg')}")
    out = {}
    for it in root.iter("item"):
        m = YM.match((it.findtext("year") or "").strip())
        if not m:
            continue        # '총계' 행 제외
        ym = f"{m.group(1)}-{m.group(2)}"
        row = out.setdefault(ym, {"exp_usd": 0.0, "imp_usd": 0.0, "exp_kg": 0.0, "imp_kg": 0.0})
        for tag, k in (("expDlr", "exp_usd"), ("impDlr", "imp_usd"),
                       ("expWgt", "exp_kg"), ("impWgt", "imp_kg")):
            v = _num(it.findtext(tag))
            if v is not None:
                row[k] += v          # 하위 HS 여러 개가 오면 합산
    return out


def monthly(hs, start_year, end=None):
    """HS 코드 월별 {YYYY-MM: {exp_usd, imp_usd, exp_kg, imp_kg}}."""
    key = require("DATA_GO_KR_KEY")
    end = end or date.today()
    out = {}
    for y in range(start_year, end.year + 1):
        last_m = end.month if y == end.year else 12
        params = {"serviceKey": key, "strtYymm": f"{y}01", "endYymm": f"{y}{last_m:02d}", "hsSgn": hs}
        out.update(parse_xml(get(URL, params, timeout=60)))
    return out
