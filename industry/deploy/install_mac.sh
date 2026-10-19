#!/bin/zsh
# 맥미니 1회 설정: 가상환경 + 패키지 + .env + launchd 매일 자동 실행 등록
#   사용: ./deploy/install_mac.sh [시] [분]     (기본 07:10)
set -eu
DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOUR="${1:-7}"; MIN="${2:-10}"
LABEL="com.dashboards.industry"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

cd "$DIR"
mkdir -p logs
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "→ $DIR/.env 를 열어 API 키를 채우세요"; }
chmod +x deploy/run_daily.sh

mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__LABEL__|$LABEL|" -e "s|__SCRIPT__|$DIR/deploy/run_daily.sh|" \
    -e "s|__DIR__|$DIR|" -e "s|__HOUR__|$HOUR|" -e "s|__MIN__|$MIN|" \
    deploy/launchd.plist.template > "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "✓ 매일 $(printf '%02d:%02d' "$HOUR" "$MIN") 자동 실행 등록 ($PLIST)"
echo "  지금 한 번 실행: launchctl kickstart gui/$(id -u)/$LABEL"
echo "  해제:           launchctl bootout gui/$(id -u)/$LABEL"
