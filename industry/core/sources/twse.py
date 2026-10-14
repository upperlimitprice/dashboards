"""대만 상장사 월매출 — TWSE OpenAPI (최근 1개월분만 제공 → 실행마다 누적 저장해 이력을 만든다)."""
from ..http import get_json

URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"


def _pick(row, needle):
    for k, v in row.items():
        if needle in k:
            return v
    return None


def _f(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse(rows, codes):
    """→ {code: {"ym": 'YYYY-MM', "name", "rev", "rev_ly", "yoy", "mom"}} (매출 단위: 천 TWD)."""
    out = {}
    for r in rows:
        code = str(_pick(r, "公司代號") or "").strip()
        if code not in codes:
            continue
        roc = str(_pick(r, "資料年月") or "").strip()      # 民國 연월, 예: 11509 → 2026-09
        if len(roc) < 4:
            continue
        y, m = int(roc[:-2]) + 1911, int(roc[-2:])
        out[code] = {
            "ym": f"{y:04d}-{m:02d}",
            "name": _pick(r, "公司名稱"),
            "rev": _f(_pick(r, "當月營收")),
            "rev_ly": _f(_pick(r, "去年當月營收")),
            "yoy": _f(_pick(r, "去年同月增減")),
            "mom": _f(_pick(r, "上月比較增減")),
        }
    return out


def monthly_revenue(codes):
    return parse(get_json(URL, timeout=60), set(codes))
