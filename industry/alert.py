# -*- coding: utf-8 -*-
"""산업 트래커 수집 실패 알림 — run.py 이후 실행. 페이지 상태가 error/partial이거나 feeds_sync 오류가 있으면 거니봇(본인)으로 보고.
상태는 data/<key>.json의 errors·missing으로 판정(run.render와 같은 기준). 문제 없으면 조용히 종료.
실행: .venv/bin/python alert.py [--dry]"""
import json
import re
import sys
import urllib.request
from pathlib import Path

from core.env import ROOT
import pages

CHAT = 6206020319


def main():
    bad = []
    for mod in pages.all_modules():
        p = ROOT / "data" / f"{mod.KEY}.json"
        raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        errs = raw.get("errors", [])
        if not raw:
            bad.append(f"- <b>{mod.TITLE}</b>: 수집 데이터 없음")
        elif errs:
            first = re.sub(r"\s+", " ", str(errs[0]))[:160]
            bad.append(f"- <b>{mod.TITLE}</b>: 오류 {len(errs)}건 ({raw.get('collected_at', '')})\n  └ {first.replace('<', '&lt;')}")
    fe = ROOT / "logs" / "feeds_sync_errors.json"
    for e in (json.loads(fe.read_text(encoding="utf-8")) if fe.exists() else []):
        bad.append(f"- <b>자동 입력(feeds_sync)</b>: {str(e)[:160].replace('<', '&lt;')}")
    if not bad:
        print("이상 없음")
        return
    msg = "⚠️ <b>산업 트래커 수집 이상</b>\n\n" + "\n".join(bad) + "\n\n이전 데이터는 유지됨 · 로그: ~/industry-dash/industry/logs/"
    if "--dry" in sys.argv:
        print(msg)
        return
    tok = re.search(r'token:\s*"([^"]+)"', (Path.home() / "analyst-bot/config.yaml").read_text()).group(1)
    r = urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=json.dumps(
        {"chat_id": CHAT, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}).encode(),
        headers={"Content-Type": "application/json"}), timeout=30)
    print("알림 발송", json.loads(r.read()).get("ok"))


if __name__ == "__main__":
    main()
