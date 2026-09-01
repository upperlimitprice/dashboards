"""유튜브 자막 수집 (로컬 실행 전용).

멤버십 영상은 로그인한 브라우저 쿠키가 필요하므로 이 스크립트는 반드시
본인 PC(구독 계정으로 YouTube에 로그인된 브라우저가 있는 곳)에서 실행한다.

  pip install yt-dlp

사용:
  python youtube/fetch.py <영상 URL 또는 ID>            # 단일 영상
  python youtube/fetch.py --channel infomkt --latest 5   # 채널 최신 N개 (videos + membership 탭)
  python youtube/fetch.py --channel infomkt --since 2026-08-01

옵션:
  --browser chrome|edge|firefox|brave|safari   (기본 chrome) yt-dlp --cookies-from-browser
  --cookies youtube/cookies.txt                 브라우저 대신 쿠키 파일 사용
  --force                                       이미 받은 영상도 다시 받기

출력:  youtube/transcripts/<channel>/<YYYY-MM-DD>_<video_id>.txt   ([mm:ss] 텍스트 라인)
       youtube/transcripts/<channel>/<YYYY-MM-DD>_<video_id>.json  (메타)
transcripts/ 는 .gitignore — 원문(특히 멤버십)은 커밋하지 않는다.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHANNELS = json.loads((ROOT / "channels.json").read_text(encoding="utf-8"))
TR = ROOT / "transcripts"


def ytdlp_base(args):
    cmd = ["yt-dlp", "--no-warnings", "--ignore-config"]
    if args.cookies:
        cmd += ["--cookies", args.cookies]
    else:
        cmd += ["--cookies-from-browser", args.browser]
    return cmd


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])} 실패:\n{r.stderr.strip()[-1500:]}")
    return r.stdout


def list_channel(args, key):
    """채널의 videos(+membership) 탭에서 영상 id·제목·업로드일을 평탄 목록으로."""
    ch = CHANNELS[key]
    items = {}
    for tab in ch.get("tabs", ["videos"]):
        url = f"{ch['url'].rstrip('/')}/{tab}"
        cmd = ytdlp_base(args) + ["--flat-playlist", "--dump-single-json", "--playlist-end", str(args.scan), url]
        try:
            data = json.loads(run(cmd))
        except RuntimeError as e:
            print(f"  [{tab}] 목록 실패 — {e}", file=sys.stderr)
            continue
        for e in data.get("entries") or []:
            if not e or not e.get("id"):
                continue
            items[e["id"]] = {
                "id": e["id"],
                "title": e.get("title"),
                "tab": tab,
                "availability": e.get("availability"),
                "duration": e.get("duration"),
                "timestamp": e.get("timestamp"),
            }
    return list(items.values())


def already(key, vid):
    return any(TR.joinpath(key).glob(f"*_{vid}.json"))


def vtt_to_lines(vtt: str):
    """VTT → [(sec, text)] — 자동자막의 롤링 중복 라인 제거."""
    out, last = [], ""
    ts_re = re.compile(r"(\d+):(\d+):(\d+)[.,](\d+)\s+-->")
    cur = None
    for raw in vtt.splitlines():
        m = ts_re.match(raw)
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            cur = h * 3600 + mi * 60 + s
            continue
        if raw.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or not raw.strip() or cur is None:
            continue
        txt = re.sub(r"<[^>]+>", "", raw).replace("&nbsp;", " ").strip()
        txt = re.sub(r"\s+", " ", txt)
        if not txt or txt == last:
            continue
        # 롤링 자막: 이전 줄이 현재 줄의 접두면 이전 줄을 대체
        if out and txt.startswith(out[-1][1]):
            out[-1] = (out[-1][0], txt)
        else:
            out.append((cur, txt))
        last = txt
    return out


def fmt_ts(sec):
    return f"{sec // 60:02d}:{sec % 60:02d}"


def fetch_one(args, key, vid_or_url):
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/live/)([\w-]{11})", vid_or_url)
    vid = m.group(1) if m else vid_or_url
    url = f"https://www.youtube.com/watch?v={vid}"
    lang = CHANNELS.get(key, {}).get("lang", "ko")

    with tempfile.TemporaryDirectory() as td:
        cmd = ytdlp_base(args) + [
            "--skip-download", "--write-info-json",
            "--write-subs", "--write-auto-subs",
            "--sub-langs", f"{lang}.*,{lang},en", "--sub-format", "vtt",
            "-o", f"{td}/%(id)s.%(ext)s", url,
        ]
        run(cmd)
        td = Path(td)
        info_p = td / f"{vid}.info.json"
        if not info_p.exists():
            raise RuntimeError("info.json 없음 — 접근 권한(멤버십/로그인) 확인")
        info = json.loads(info_p.read_text(encoding="utf-8"))
        subs = sorted(td.glob(f"{vid}*.vtt"), key=lambda p: (lang not in p.name, "auto" in p.name))
        if not subs:
            raise RuntimeError("자막 없음 (자동자막도 없음) — 나중에 다시 시도")
        lines = vtt_to_lines(subs[0].read_text(encoding="utf-8"))

    up = info.get("upload_date") or datetime.now().strftime("%Y%m%d")
    date = f"{up[:4]}-{up[4:6]}-{up[6:]}"
    ch_dir = TR / key
    ch_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date}_{vid}"
    (ch_dir / f"{stem}.txt").write_text(
        "\n".join(f"[{fmt_ts(s)}] {t}" for s, t in lines), encoding="utf-8")
    meta = {
        "video_id": vid, "channel": key, "channel_name": CHANNELS.get(key, {}).get("name", info.get("channel")),
        "title": info.get("title"), "url": url, "published": date,
        "duration_sec": info.get("duration"),
        "members_only": info.get("availability") in ("subscriber_only", "premium_only"),
        "availability": info.get("availability"),
        "sub_file": subs[0].name, "lines": len(lines),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    (ch_dir / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    tag = "🔒" if meta["members_only"] else "  "
    print(f"{tag} {stem}  {meta['title']}  ({len(lines)}줄)")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="영상 URL/ID")
    ap.add_argument("--channel", help="channels.json 키 (예: infomkt)")
    ap.add_argument("--latest", type=int, default=3, help="채널 모드: 최신 N개")
    ap.add_argument("--since", help="채널 모드: 이 날짜(YYYY-MM-DD) 이후만")
    ap.add_argument("--scan", type=int, default=30, help="채널 탭당 스캔할 항목 수")
    ap.add_argument("--browser", default="chrome")
    ap.add_argument("--cookies")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not shutil.which("yt-dlp"):
        sys.exit("yt-dlp 가 없습니다:  pip install -U yt-dlp")

    if args.target:
        key = args.channel or "misc"
        fetch_one(args, key, args.target)
        return

    if not args.channel or args.channel not in CHANNELS:
        sys.exit(f"--channel 은 {list(CHANNELS)} 중 하나")

    key = args.channel
    items = list_channel(args, key)
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").timestamp()
        items = [i for i in items if (i.get("timestamp") or 0) >= since]
    items.sort(key=lambda i: i.get("timestamp") or 0, reverse=True)
    todo = [i for i in items if args.force or not already(key, i["id"])][: args.latest]
    print(f"[{key}] 목록 {len(items)}개 · 새로 받을 영상 {len(todo)}개")
    for it in todo:
        try:
            fetch_one(args, key, it["id"])
        except RuntimeError as e:
            print(f"✗ {it['id']} {it.get('title')} — {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
