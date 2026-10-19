#!/usr/bin/env python3
"""산업 트래커 실행기.

  python run.py                  # 7개 페이지 전부 수집 → HTML 생성
  python run.py grid freight     # 일부만 수집 (나머지는 저장된 데이터로 다시 렌더)
  python run.py --render-only    # 네트워크 없이 data/*.json 으로 HTML만 재생성
  python run.py --push           # 완료 후 industry/ 변경분 커밋·푸시
  python run.py --check          # 페이지별 필요 키 설정 상태
"""
import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import page as P                                      # noqa: E402
from core.env import DATA, REPO, ROOT, SITE, env, load_env, scrub  # noqa: E402
import pages                                                     # noqa: E402


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def collect(mod):
    path = DATA / f"{mod.KEY}.json"
    t0 = time.time()
    raw = mod.collect(load_json(path))
    raw["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_json(path, raw)
    print(f"  수집 {mod.KEY}: {time.time() - t0:.1f}s, 오류 {len(raw['errors'])}, 키 누락 {len(raw['missing'])}")
    return raw


def render(mod):
    raw = load_json(DATA / f"{mod.KEY}.json")
    try:
        page = mod.build(raw) if raw else P.new(mod.KEY, mod.TITLE, mod.SUBTITLE)
    except Exception as e:  # noqa: BLE001
        print(scrub(traceback.format_exc()))
        page = P.new(mod.KEY, mod.TITLE, mod.SUBTITLE)
        page["errors"].append(f"페이지 가공 실패: {type(e).__name__}: {scrub(e)}")
    page["updated"] = raw.get("collected_at", "수집 전")
    page["errors"] = raw.get("errors", []) + page["errors"]
    page["notes"] = raw.get("missing", []) + page["notes"]
    has = bool(page["charts"] or page["tables"])
    if not raw:
        page["status"] = "pending"
    elif not has and raw.get("missing"):
        page["status"] = "skipped"
    elif not has and page["errors"]:
        page["status"] = "error"
    elif page["errors"] or raw.get("missing"):
        page["status"] = "partial"
    else:
        page["status"] = "ok"
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / f"{mod.KEY}.html").write_text(P.render(page), encoding="utf-8")
    return {k: page[k] for k in ("key", "title", "subtitle", "updated", "status", "kpis")}


def push():
    def git(*a, check=True):
        return subprocess.run(["git", "-C", str(REPO), *a], check=check, capture_output=True, text=True)
    rel = ROOT.relative_to(REPO)
    git("add", f"{rel}/data", f"{rel}/site")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("변경 없음 — 푸시 생략")
        return
    git("commit", "-m", f"industry tracker {datetime.now():%Y-%m-%d}")
    branch = env("GIT_BRANCH") or git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    for i in range(4):
        r = git("pull", "--rebase", "--autostash", "origin", branch, check=False)
        if r.returncode == 0 and git("push", "origin", f"HEAD:{branch}", check=False).returncode == 0:
            print(f"푸시 완료 → {branch}")
            return
        time.sleep(2 ** (i + 1))
    raise SystemExit("푸시 실패 — 수동으로 git 상태를 확인하세요")


def check():
    for mod in pages.all_modules():
        needs = [n.split("(")[0] for n in mod.NEEDS]
        st = ", ".join(f"{n}{'✓' if env(n) else '✗'}" for n in needs) or "키 불필요"
        print(f"  {mod.KEY:13s} {st}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="*", help=f"수집할 페이지 (기본 전체): {', '.join(pages.ORDER)}")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-insights", action="store_true", help="목록 인사이트 갱신 생략(이전 값 사용 안 함)")
    a = ap.parse_args()
    load_env()
    if a.check:
        return check()
    if not a.render_only:
        for key in a.keys or pages.ORDER:
            collect(pages.load(key))
    cards = [render(m) for m in pages.all_modules()]
    from core import insights
    used = {k for _, ks in pages.GROUPS for k in ks}
    groups = list(pages.GROUPS) + ([("기타", [c["key"] for c in cards if c["key"] not in used])] if any(c["key"] not in used for c in cards) else [])
    ins = {} if a.no_insights else insights.make(cards, groups)
    (SITE / "index.html").write_text(P.render_hub({"cards": cards, "groups": groups, "ins": ins}), encoding="utf-8")
    print("  " + " · ".join(f"{c['key']}:{c['status']}" for c in cards))
    if a.push:
        push()


if __name__ == "__main__":
    main()
