#!/bin/zsh
# launchd 가 매일 호출 — 가상환경에서 전체 수집 후 푸시. 로그: industry/logs/
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DIR/logs"
LOG="$DIR/logs/$(date +%Y-%m-%d).log"
cd "$DIR" || exit 1
{
  echo "=== $(date '+%F %T') 시작"
  "$DIR/.venv/bin/python" run.py   # 자동 푸시 제외(2026-10-19 사용자 지시) — 공개 반영은 수동: run.py --push
  echo "=== $(date '+%F %T') 종료 (exit $?)"
} >> "$LOG" 2>&1
# 30일 지난 로그 정리
find "$DIR/logs" -name '*.log' -mtime +30 -delete
