#!/usr/bin/env python3
"""HTML에 검색·AI 크롤링 금지 메타 삽입 (2026-11-17 사용자 지시: 대시보드 전체 크롤링 금지).
사용: python3 noindex.py [파일...]  (인자 없으면 저장소 전체) — .git/hooks/pre-commit이 커밋마다 자동 실행"""
import re, sys
from pathlib import Path
META = '<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex,noai,noimageai">'
def fix(p):
    s = p.read_text(encoding="utf-8", errors="surrogateescape")
    if re.search(r'<meta[^>]+name=["\']?robots', s, re.I):
        return False
    m = re.search(r"<head[^>]*>", s, re.I) or re.search(r"<html[^>]*>", s, re.I) or re.match(r"\s*<!doctype[^>]*>", s, re.I)
    i = m.end() if m else 0  # head·doctype 없는 조각형 페이지는 맨 앞에 (브라우저가 head로 처리)
    p.write_text(s[:i] + META + s[i:], encoding="utf-8", errors="surrogateescape")
    return True
files = [Path(f) for f in sys.argv[1:]] or [f for f in Path(".").rglob("*.htm*") if ".git" not in f.parts]
n = sum(fix(f) for f in files if f.suffix in (".html", ".htm") and f.exists())
print(f"noindex: {n}개 삽입", file=sys.stderr)
