"""모든 대시보드 HTML에 공통 라이트/다크 전환 스크립트(theme.js) 삽입 — 멱등 (사용자 지시 2026-11-03).
사용: python3 tools/inject_theme.py [파일 ...]  (인자 없으면 저장소 전체)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = '<script src="/dashboards/theme.js"></script>'


def inject(p):
    try:
        s = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return False
    low = s.lower()
    head = low.lstrip()[:200]
    if "/dashboards/theme.js" in s or ("<html" not in low[:5000] and "<!doctype" not in low[:300] and not head.startswith(("<title", "<meta", "<style"))):
        return False  # 다른 페이지에 끼워 쓰는 조각 파일 제외 (<html> 없이 <title>/<style>로 시작하는 완결 페이지는 포함)
    i = low.find("</head>")
    if i < 0:
        j = low.find("<body")
        i = j if j >= 0 else 0
    p.write_text(s[:i] + TAG + s[i:], encoding="utf-8")
    return True


if __name__ == "__main__":
    fs = [Path(a).resolve() for a in sys.argv[1:]] or [p for p in ROOT.rglob("*.html") if ".git" not in p.parts]
    n = sum(inject(p) for p in fs)
    print(f"theme.js 삽입 {n}개 / {len(fs)}개")
