"""관세청 월별 데이터({YYYY-MM: {exp_usd, ...}}) → 시계열 변환 공용 함수."""
from . import series as S


def field(m, name, scale=1.0):
    return {k: v[name] * scale for k, v in (m or {}).items() if v.get(name) is not None}


def unit_price(m, side="exp"):
    """$/kg — 단가(믹스·판가) 프록시."""
    return {k: v[f"{side}_usd"] / v[f"{side}_kg"] for k, v in (m or {}).items() if v.get(f"{side}_kg")}


def latest_complete(d):
    """관세청은 확정치만 주므로 마지막 키 = 최신 완료월."""
    return S.last(d)
