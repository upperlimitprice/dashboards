#!/usr/bin/env python
"""수출 대시보드 3종 업데이트 — 친구가 보내준 새 파일(HTML 또는 zip)을 대시보드에 반영.

사용법:
  python update_exports.py                # ~/Downloads/Telegram Desktop 에서 최신 파일 자동 탐색
  python update_exports.py <경로>          # 특정 zip 또는 폴더 지정

친구 파일명(한글) → 배포명 매핑:
  수출데이터.html   → exports.html
  기업별수출.html   → exports-corp.html
  수출입데이터.html → trade-stats.html
zip으로 오면 CP949 파일명 복원 후 추출. 갱신분만 교체 후 git push.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

DEPLOY = Path.home() / "dashboards-anon"
SRC_DIR = Path.home() / "Downloads" / "Telegram Desktop"
MAP = {
    "수출데이터": "exports.html",
    "기업별수출": "exports-corp.html",
    "수출입데이터": "trade-stats.html",
}


def fix(n):
    for enc in ("utf-8", "cp949"):
        try:
            return n.encode("cp437").decode(enc)
        except Exception:
            continue
    return n


def target_for(name):
    stem = Path(name).stem
    for kw, dst in MAP.items():
        if kw in stem:
            return dst
    return None


def collect(src):
    """(target_filename, bytes) 목록 반환."""
    src = Path(src)
    out = []
    if src.is_file() and src.suffix.lower() == ".zip":
        z = zipfile.ZipFile(src)
        for raw in z.namelist():
            name = fix(raw)
            if not name.lower().endswith(".html"):
                continue
            dst = target_for(name)
            if dst:
                out.append((dst, z.read(raw)))
    else:
        base = src if src.is_dir() else SRC_DIR
        for f in base.glob("*.html"):
            dst = target_for(f.name)
            if dst:
                out.append((dst, f.read_bytes()))
        # zip도 탐색
        for zf in base.glob("*수출*.zip"):
            out.extend(collect(zf))
    # 같은 target 중복 시 최신(뒤) 우선
    dedup = {}
    for dst, data in out:
        dedup[dst] = data
    return list(dedup.items())


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SRC_DIR
    files = collect(src)
    if not files:
        print("업데이트할 파일을 못 찾음 (수출데이터/기업별수출/수출입데이터 .html 또는 zip)")
        sys.exit(1)
    changed = []
    for dst, data in files:
        (DEPLOY / dst).write_bytes(data)
        changed.append(dst)
        print(f"갱신: {dst} ({len(data):,} bytes)")
    # 날짜 추출 (수출데이터 built)
    tag = ""
    ex = DEPLOY / "exports.html"
    if ex.exists():
        m = re.search(r'"lastUpdate":"([\d-]+)"', ex.read_text(errors="ignore")[:400000])
        if m:
            tag = m.group(1)
    subprocess.run(["git", "-C", str(DEPLOY), "add", *changed], check=True)
    subprocess.run(["git", "-C", str(DEPLOY), "commit", "-qm",
                    f"exports update {tag}".strip()], check=False)
    subprocess.run(["git", "-C", str(DEPLOY), "push", "-q"], check=False)
    print(f"배포 완료 — {len(changed)}개 ({tag})")


if __name__ == "__main__":
    main()
