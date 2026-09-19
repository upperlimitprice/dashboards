#!/usr/bin/env bash
# 매일 루틴 한 방: 자막 수집 → 요약 → HTML → 커밋/푸시 → 텔레그램 전송
# launchd/cron 예:  0 8 * * *  cd ~/dashboards && bash youtube/run.sh >> youtube/.cache/run.log 2>&1
set -uo pipefail
cd "$(dirname "$0")/.."
# anthropic SDK 1.x 는 Python 3.10+ — Mac 기본 python3(3.9) 대신 Homebrew 3.12 우선
PY=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3)
mkdir -p youtube/.cache
echo "== $(date '+%F %T') =="
for ch in $($PY -c "import json;print(' '.join(json.load(open('youtube/channels.json'))))"); do
  $PY youtube/fetch.py --channel "$ch" --latest "${LATEST:-3}" || echo "fetch $ch 실패"
done
$PY youtube/summarize.py || { echo "summarize 실패"; exit 1; }
$PY youtube/build.py && $PY gen_index.py
if ! git diff --quiet -- youtube index.html; then
  git add youtube/summaries youtube/*/ youtube/index.html index.html
  git commit -qm "youtube 요약 $(date +%F)" && git push -q || echo "push 실패 (전송은 계속)"
fi
$PY youtube/send.py
