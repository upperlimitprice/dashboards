"""관세청 국가별 품목별 수출입실적 (data.go.kr, 키: DATA_GO_KR_KEY — 품목별 API와 같은 키로 동작 확인).

https://www.data.go.kr/data/15100475/openapi.do 계열 — getNitemtradeList(cntyCd=국가코드). 응답 형식이 품목별
API와 같아 customs.parse_xml 을 그대로 쓴다('총계' 행 제외, 하위 HS 합산).
"""
from datetime import date

from ..env import require
from ..http import get
from .customs import parse_xml

URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"


def monthly(hs, country, start_year, end=None):
    """HS 코드 × 국가 월별 {YYYY-MM: {exp_usd, imp_usd, exp_kg, imp_kg}}."""
    key = require("DATA_GO_KR_KEY")
    end = end or date.today()
    out = {}
    for y in range(start_year, end.year + 1):
        last_m = end.month if y == end.year else 12
        params = {"serviceKey": key, "strtYymm": f"{y}01", "endYymm": f"{y}{last_m:02d}",
                  "hsSgn": hs, "cntyCd": country}
        out.update(parse_xml(get(URL, params, timeout=60)))
    return out
