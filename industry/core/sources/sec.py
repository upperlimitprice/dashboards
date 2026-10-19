"""SEC EDGAR XBRL companyconcept API (키 불필요, User-Agent에 연락처 필수).

현금흐름표 항목은 10-Q 에서 누적(YTD)으로 공시되므로 분기 단독값을 차감으로 복원한다.
"""
from datetime import date

from ..env import env
from ..http import NotFound, get_json

URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"


def _d(s):
    return date.fromisoformat(s)


def concept_facts(cik, concept):
    ua = env("SEC_USER_AGENT")
    if not ua:
        from ..env import MissingKey
        raise MissingKey("SEC_USER_AGENT 미설정 — '이름 이메일' 형식으로 .env 에 추가하세요")
    j = get_json(URL.format(cik=cik, concept=concept), headers={"User-Agent": ua})
    return j.get("units", {}).get("USD", [])


def quarterly(facts):
    """facts → {분기말 'YYYY-MM-DD': 분기 단독값}."""
    spans = {}
    for f in facts:
        if "start" not in f or "end" not in f:
            continue
        spans[(f["start"], f["end"])] = float(f["val"])   # 같은 기간은 최신 공시가 덮어씀
    q = {}
    for (s, e), v in spans.items():
        days = (_d(e) - _d(s)).days
        if 80 <= days <= 100:
            q[e] = v
    for (s, e), v in spans.items():
        days = (_d(e) - _d(s)).days
        if days <= 100 or e in q:
            continue
        prev = [(e2, v2) for (s2, e2), v2 in spans.items() if s2 == s and e2 < e]
        if not prev:
            continue
        e2, v2 = max(prev)
        if 80 <= (_d(e) - _d(e2)).days <= 100:
            q[e] = v - v2
    return q


def quarterly_concepts(cik, concepts):
    """여러 concept 을 병합 (앞 concept 우선). 회사가 태그를 바꾼 경우 대비."""
    merged = {}
    for c in reversed(concepts):
        try:
            merged.update(quarterly(concept_facts(cik, c)))
        except NotFound:
            continue
    return merged
