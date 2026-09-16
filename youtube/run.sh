#!/usr/bin/env bash
# 매일 루틴 한 방: 자막 수집 → 요약 → HTML → 커밋/푸시 → 텔레그램 전송
# launchd/cron 예:  0 8 * * *  cd ~/dashboards && bash youtube/run.sh >> youtube/.cache/run.log 2>&1
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p youtube/.cache
echo "== $(date '+%F %T') =="
for ch in $(python3 -c "import json;print(' '.join(json.load(open('youtube/channels.json'))))"); do
  python3 youtube/fetch.py --channel "$ch" --latest "${LATEST:-3}" || echo "fetch $ch 실패"
done
python3 youtube/summarize.py || { echo "summarize 실패"; exit 1; }
python3 youtube/build.py && python3 gen_index.py
if ! git diff --quiet -- youtube index.html; then
  git add youtube/summaries youtube/*/ youtube/index.html index.html
  git commit -qm "youtube 요약 $(date +%F)" && git push -q || echo "push 실패 (전송은 계속)"
fi
python3 youtube/send.py
