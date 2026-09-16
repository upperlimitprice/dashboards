"""새 요약을 텔레그램 요약봇으로 전송.

설정 (둘 중 하나, 커밋 금지):
  환경변수  TG_BOT_TOKEN=123456:ABC...  TG_CHAT_ID=-100xxxx  (또는 개인 chat id)
  파일      youtube/telegram.json  →  {"bot_token": "...", "chat_id": "..."}   (.gitignore 됨)

사용:
  python youtube/send.py              # 아직 안 보낸 요약 전부 전송
  python youtube/send.py --dry-run    # 메시지만 출력
  python youtube/send.py --test       # 연결 테스트 메시지 1건
  python youtube/send.py --file youtube/example-summary.json --dry-run   # 특정 JSON 미리보기
  python youtube/send.py --resend <video_id>

전송 기록: youtube/.cache/sent.json (gitignore) — 같은 영상은 다시 보내지 않는다.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SM = ROOT / "summaries"
CACHE = ROOT / ".cache"
SENT = CACHE / "sent.json"
CHANNELS = json.loads((ROOT / "channels.json").read_text(encoding="utf-8"))
PAGES = "https://upperlimitprice.github.io/dashboards/youtube"
VIEW = {"positive": "▲", "negative": "▼", "neutral": "―", "watch": "◎"}
STANCE = {"bullish": "강세", "bearish": "약세", "neutral": "중립", "mixed": "혼재"}
TG_LIMIT = 4096


def creds():
    tok, cid = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    f = ROOT / "telegram.json"
    if (not tok or not cid) and f.exists():
        j = json.loads(f.read_text(encoding="utf-8"))
        tok, cid = tok or j.get("bot_token"), cid or j.get("chat_id")
    if not tok or not cid:
        sys.exit("텔레그램 설정 없음: TG_BOT_TOKEN/TG_CHAT_ID 환경변수 또는 youtube/telegram.json")
    return tok, str(cid)


def tg_send(tok, cid, text):
    body = urllib.parse.urlencode({"chat_id": cid, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=body)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as ex:
        raise RuntimeError(f"telegram {ex.code}: {ex.read().decode(errors='replace')[:300]}")


def compose(s: dict) -> str:
    ch = CHANNELS.get(s.get("channel"), {})
    lock = "🔒 " if s.get("members_only") else ""
    page = f"{PAGES}/{s.get('channel')}/{s.get('published')}_{s.get('video_id')}.html"
    lines = [
        f"{ch.get('emoji','📺')} <b>{e(ch.get('name') or s.get('channel_name',''))}</b> · {e(s.get('published',''))} · {STANCE.get(s.get('stance'),'')}",
        f"{lock}<b>{e(s.get('title',''))}</b>",
        "",
        f"<i>{e(s.get('one_liner',''))}</i>",
        "",
        "<b>핵심</b>",
    ]
    lines += [f"• {e(p)}" for p in s.get("key_points", [])[:6]]
    if s.get("tickers"):
        lines += ["", "<b>종목</b> " + " · ".join(
            f"{VIEW.get(t.get('view'),'')}{e(t['name'])}" for t in s["tickers"][:8])]
    if s.get("checkpoints"):
        lines += ["", "<b>체크포인트</b>"] + [f"☐ {e(c)}" for c in s["checkpoints"][:4]]
    lines += ["", f"📄 <a href=\"{page}\">리포트</a> · <a href=\"{e(s.get('url',''))}\">원본 영상</a>"]
    text = "\n".join(lines)
    if len(text) > TG_LIMIT:
        text = text[:TG_LIMIT - 40].rsplit("\n", 1)[0] + f"\n…\n📄 <a href=\"{page}\">리포트 전문</a>"
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--file", help="특정 요약 JSON 하나만")
    ap.add_argument("--resend", help="video_id 재전송")
    args = ap.parse_args()

    if args.test:
        tok, cid = creds()
        r = tg_send(tok, cid, "✅ 유튜브 요약봇 연결 테스트")
        print("ok" if r.get("ok") else r); return

    CACHE.mkdir(exist_ok=True)
    sent = set(json.loads(SENT.read_text()) if SENT.exists() else [])
    files = [Path(args.file)] if args.file else sorted(SM.glob("*/*.json"))
    todo = []
    for f in files:
        s = json.loads(f.read_text(encoding="utf-8"))
        s.setdefault("channel", f.parent.name)
        vid = s.get("video_id")
        if args.resend and vid != args.resend:
            continue
        if not args.resend and not args.file and vid in sent:
            continue
        todo.append(s)
    todo.sort(key=lambda s: s.get("published", ""))
    if not todo:
        print("보낼 새 요약 없음"); return

    tok = cid = None
    if not args.dry_run:
        tok, cid = creds()
    for s in todo:
        msg = compose(s)
        if args.dry_run:
            print("=" * 60 + "\n" + msg + "\n"); continue
        try:
            r = tg_send(tok, cid, msg)
        except RuntimeError as ex:
            print(f"✗ {s.get('video_id')} {ex}", file=sys.stderr); continue
        if r.get("ok"):
            sent.add(s.get("video_id"))
            SENT.write_text(json.dumps(sorted(sent)))
            print(f"✓ 전송: {s.get('title')}")
        else:
            print(f"✗ {s.get('video_id')} {r}", file=sys.stderr)


if __name__ == "__main__":
    main()
