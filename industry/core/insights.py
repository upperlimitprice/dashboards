"""산업 트래커 목록 상단 인사이트 — 페이지 KPI(값·증감·기준일)를 근거로 종합·구역별 인사이트를 claude -p로 작성.
KPI가 바뀐 경우에만 다시 쓰고(해시 비교), 실패하면 이전 인사이트를 유지한다. 결과: data/_insights.json"""
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime

from .env import ROOT

PATH = ROOT / "data" / "_insights.json"
PROMPT = """너는 한국 주식 리서치 애널리스트다. 아래는 '산업 트래커'(미국 전력·데이터센터·가스·태양광, 한국 수출 등 공개 데이터 대시보드)의 페이지별 핵심 지표(KPI)다. 이 숫자만 근거로 JSON 하나만 출력하라(코드펜스·설명 금지).
{"headline":"전체를 관통하는 한 줄(30~55자)","bullets":["종합 인사이트 3~4개, 각 60~130자, 숫자 포함, 투자 함의(관련 한국·미국 종목군) 포함"],
 "groups":{"<구역명>":["2~3줄, 각 50~120자"]}}
- 구역명은 정확히 다음 키를 사용: {groups}
- 각 구역은 그 구역 페이지들의 KPI로만 쓴다. 증감 방향(가속/둔화)과 의미를 짚고, 데이터 기준일이 오래된 지표는 '(기준 YYYY-MM)'처럼 밝혀라.
- 문체: 모두 음슴체(~했음, ~임, ~됨, ~보임, ~필요). '~다/~습니다' 금지.
- 핵심 숫자·결론은 **굵게**, 가장 중요한 결론 2~3개(전체에서)만 __굵게+밑줄__.
- 데이터에 없는 수치·뉴스를 지어내지 말 것.

[KPI]
{kpis}"""


def _kpi_text(cards, groups):
    title = {c["key"]: c["title"] for c in cards}
    lines = []
    for gname, keys in groups:
        lines.append(f"## {gname}")
        for k in keys:
            c = next((x for x in cards if x["key"] == k), None)
            if not c:
                continue
            lines.append(f"- [{title[k]}] (상태 {c.get('status')})")  # 수집 시각은 넣지 않음 — 값이 바뀔 때만 재작성·알림
            for kp in c.get("kpis", []):
                d = "" if kp.get("delta") is None else f" ({kp['delta']:+}{kp.get('delta_unit', '%')} {kp.get('delta_label', '')})"
                lines.append(f"  · {kp['label']}: {kp.get('value')}{kp.get('unit', '')}{d}{' · ' + kp['asof'] if kp.get('asof') else ''}")
    return "\n".join(lines)


def _kpi_map(text):
    """KPI 텍스트 → {(페이지, 지표): 값 문자열}"""
    out, page = {}, ""
    for l in text.splitlines():
        if l.startswith("- ["):
            page = l[3:l.index("]")]
        elif l.startswith("  · ") and ":" in l:
            k, v = l[4:].split(":", 1)
            out[(page, k.strip())] = v.strip()
    return out


def _md_tg(t):
    t = (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"__(.+?)__", r"<b><u>\1</u></b>", t)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def notify(new, old, text):
    """인사이트가 바뀌면 거니봇(본인)으로: 종합 인사이트 + 변동 지표(이전→현재) + 바뀐 구역."""
    import urllib.request
    from pathlib import Path
    L = ["📊 <b>산업 트래커 인사이트 " + ("갱신" if old.get("headline") else "최초 작성") + f"</b> · {new['at']}", "",
         f"<b><u>{_md_tg(new['headline'])}</u></b>", "", "▪️ <b>종합</b>"]
    L += [f"- {_md_tg(b)}" for b in new["bullets"]]
    if old.get("kpis"):
        a, b = _kpi_map(old["kpis"]), _kpi_map(new["kpis"])
        ch = [(k, a.get(k), b[k]) for k in b if a.get(k) != b[k]]
        if ch:
            L += ["", f"▪️ <b>🔄 변동 지표 {len(ch)}건</b>"]
            for (pg, lab), o, n in ch[:15]:
                L.append(f"- {pg} · {lab}: {o or '신규'} → <b>{n}</b>")
        gch = [g for g in new["groups"] if new["groups"].get(g) != old.get("groups", {}).get(g)]
        if gch:
            L += ["", "▪️ <b>✏️ 인사이트가 바뀐 구역</b>"]
            for g in gch:
                L.append(f"<b>{g}</b>")
                L += [f"  · {_md_tg(x)}" for x in new["groups"][g]]
    else:
        L += [""] + sum([[f"<b>{g}</b>"] + [f"  · {_md_tg(x)}" for x in xs] for g, xs in new["groups"].items()], [])
    L += ["", "🔗 https://upperlimitprice.github.io/dashboards/industry.html (공개본은 수동 반영)"]
    msg = "\n".join(L)
    tok = re.search(r'token:\s*"([^"]+)"', (Path.home() / "analyst-bot/config.yaml").read_text()).group(1)
    for i in range(0, len(msg), 3900):  # 텔레그램 4096자 제한
        part = msg[i:i + 3900]
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=json.dumps(
                {"chat_id": 6206020319, "text": part, "parse_mode": "HTML", "disable_web_page_preview": True}).encode(),
                headers={"Content-Type": "application/json"}), timeout=30)
        except Exception as e:  # noqa: BLE001 — HTML 분할로 태그가 깨지면 평문 재시도
            urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=json.dumps(
                {"chat_id": 6206020319, "text": re.sub(r"</?[bu]>", "", part), "disable_web_page_preview": True}).encode(),
                headers={"Content-Type": "application/json"}), timeout=30)
            print("  알림 평문 재전송:", e)


def make(cards, groups, send=True):
    text = _kpi_text(cards, groups)
    h = hashlib.sha1(text.encode()).hexdigest()
    old = json.loads(PATH.read_text(encoding="utf-8")) if PATH.exists() else {}
    if old.get("hash") == h and old.get("groups"):
        return old
    pr = PROMPT.replace("{groups}", json.dumps([g for g, _ in groups], ensure_ascii=False)).replace("{kpis}", text)
    try:
        r = subprocess.run([shutil.which("claude") or "/opt/homebrew/bin/claude", "-p", pr, "--model", "claude-opus-5-5", "--disallowedTools", "*"],
                           capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
        out = json.loads(re.search(r"\{.*\}", r.stdout, re.S).group(0))
        assert out.get("bullets") and out.get("groups")
    except Exception as e:  # noqa: BLE001 — 실패 시 이전 인사이트 유지
        print("  인사이트 생성 실패 → 이전 유지:", str(e)[:120])
        return old
    out.update({"hash": h, "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "kpis": text})
    PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  인사이트 갱신:", out["headline"])
    if send:
        try:
            notify(out, old, text)
        except Exception as e:  # noqa: BLE001
            print("  인사이트 알림 실패:", e)
    return out
