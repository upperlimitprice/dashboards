"""summaries/*.json → youtube/<ch>/<date>_<id>.html + youtube/index.html

  python youtube/build.py
그 뒤 루트에서  python gen_index.py  하면 메인 대시보드 카드에 최신 요약이 걸린다.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SM = ROOT / "summaries"
CHANNELS = json.loads((ROOT / "channels.json").read_text(encoding="utf-8"))

STANCE = {"bullish": ("강세", "#0f6b5c"), "bearish": ("약세", "#d63c2f"),
          "neutral": ("중립", "#67737f"), "mixed": ("혼재", "#b07d1e")}
VIEW = {"positive": ("긍정", "#0f6b5c"), "negative": ("부정", "#d63c2f"),
        "neutral": ("중립", "#67737f"), "watch": ("관찰", "#b07d1e")}

CSS = """
:root{--ink:#1c2530;--sub:#67737f;--line:#dce3ea;--paper:#f5f7f9;--card:#fff;--acc:#0f6b5c;--up:#d63c2f;--gold:#b07d1e}
*{box-sizing:border-box}
body{font-family:'Apple SD Gothic Neo','Pretendard','Noto Sans KR',sans-serif;margin:0;background:var(--paper);color:var(--ink);line-height:1.6}
.wrap{max-width:860px;margin:0 auto;padding:30px 18px 80px}
.hero{background:linear-gradient(135deg,#0d3a32,#0f6b5c);color:#fff;border-radius:14px;padding:22px 26px;margin-bottom:10px}
.hero .eyebrow{font-size:.72rem;letter-spacing:.1em;color:#ffd47e;font-weight:800}
.hero h1{margin:6px 0 6px;font-size:1.3rem;line-height:1.4}
.hero .q{color:#cfe8e2;font-size:.83rem}
.hero a{color:#ffd47e;text-decoration:none}
.badge{display:inline-block;font-size:.7rem;font-weight:800;padding:2px 8px;border-radius:99px;color:#fff;margin-right:6px;vertical-align:middle}
.card{background:var(--card);border:1.5px solid var(--line);border-radius:12px;padding:6px 20px 14px;margin:14px 0}
.card h2{font-size:1rem;margin:12px 0 8px;padding-left:9px;border-left:4px solid var(--acc)}
.card.gold{border-color:#e2c98a;background:#fffaf0}.card.gold h2{border-left-color:var(--gold)}
.card.red h2{border-left-color:var(--up)}
ul{margin:6px 0;padding-left:20px}li{margin:8px 0;font-size:.92rem}
p{font-size:.92rem}
.one{font-size:1.02rem;font-weight:700;margin:10px 0 4px}
.sec{display:grid;grid-template-columns:56px 1fr;gap:10px;padding:8px 0;border-top:1px solid var(--line)}
.sec:first-of-type{border-top:0}
.sec .t{font-variant-numeric:tabular-nums;color:var(--acc);font-weight:800;font-size:.85rem;padding-top:2px}
.sec b{display:block;margin-bottom:2px}.sec span{font-size:.9rem;color:#2b3640}
table{width:100%;border-collapse:collapse;font-size:.88rem;margin:6px 0}
th{text-align:left;color:var(--sub);font-weight:700;font-size:.75rem;border-bottom:1px solid var(--line);padding:6px 4px}
td{padding:7px 4px;border-bottom:1px solid #eef2f6;vertical-align:top}
.v{font-weight:800;font-size:.75rem}
.chip{display:inline-block;background:#eef6f4;color:#0d4a3f;border-radius:6px;padding:2px 8px;font-size:.8rem;margin:3px 4px 3px 0;font-weight:600}
.quote{background:#eef6f4;border-left:3px solid var(--acc);padding:6px 10px;border-radius:4px;font-style:italic;color:#0d4a3f;margin:8px 0;font-size:.9rem}
.note{color:var(--sub);font-size:.75rem;margin-top:22px;border-top:1px solid var(--line);padding-top:10px}
.list a{display:block;background:var(--card);border:1.5px solid var(--line);border-radius:11px;padding:12px 16px;margin:9px 0;color:var(--ink);text-decoration:none}
.list a:hover{border-color:#3d5a80}
.list .d{color:var(--sub);font-size:.78rem;font-variant-numeric:tabular-nums}
.list .t{font-weight:700;margin:2px 0}.list .o{font-size:.85rem;color:#3a4652}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 4px}
.tabs button{border:1.5px solid var(--line);background:#fff;border-radius:99px;padding:5px 13px;font-size:.82rem;cursor:pointer;font-weight:600;color:var(--sub)}
.tabs button.on{border-color:var(--acc);color:var(--acc);background:#eef6f4}
"""
e = html.escape


def li(items):
    return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>" if items else "<p class='note'>—</p>"


def page(s: dict) -> str:
    ch = CHANNELS.get(s.get("channel"), {})
    st, sc = STANCE.get(s.get("stance"), ("", "#67737f"))
    lock = "<span class='badge' style='background:#b07d1e'>🔒 멤버십</span>" if s.get("members_only") else ""
    dur = f" · {(s.get('duration_sec') or 0)//60}분" if s.get("duration_sec") else ""
    tick = "".join(
        f"<tr><td><b>{e(t['name'])}</b> <span style='color:var(--sub);font-size:.78rem'>{e(t.get('code',''))}</span></td>"
        f"<td><span class='v' style='color:{VIEW.get(t['view'],VIEW['neutral'])[1]}'>{VIEW.get(t['view'],VIEW['neutral'])[0]}</span></td>"
        f"<td>{e(t['note'])}</td></tr>" for t in s.get("tickers", []))
    nums = "".join(f"<tr><td><b>{e(n['label'])}</b></td><td class='v' style='font-size:.9rem'>{e(n['value'])}</td><td>{e(n['context'])}</td></tr>"
                   for n in s.get("numbers", []))
    secs = "".join(f"<div class='sec'><div class='t'>{e(x['t'])}</div><div><b>{e(x['title'])}</b><span>{e(x['body'])}</span></div></div>"
                   for x in s.get("sections", []))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(s.get('title',''))} · {e(ch.get('name',''))} 요약</title><style>{CSS}</style></head><body><div class="wrap">
<div class="hero"><span class="eyebrow">{e(ch.get('emoji',''))} {e(ch.get('name',''))} · YOUTUBE SUMMARY</span>
<h1>{e(s.get('title',''))}</h1>
<div class="q">{lock}<span class='badge' style='background:{sc}'>{st}</span>{e(s.get('published',''))}{dur} · <a href="{e(s.get('url','#'))}" target="_blank">원본 영상 ↗</a> · <a href="../index.html">목록</a></div></div>
<div class="card gold"><h2>한 줄 요약</h2><p class="one">{e(s.get('one_liner',''))}</p>
{"".join(f"<span class='chip'>#{e(t)}</span>" for t in s.get('themes', []))}</div>
<div class="card"><h2>핵심 포인트</h2>{li(s.get('key_points', []))}</div>
<div class="card"><h2>흐름별 정리</h2>{secs}</div>
<div class="card"><h2>언급 종목·지수</h2>{f"<table><tr><th>종목</th><th>시각</th><th>맥락</th></tr>{tick}</table>" if tick else "<p class='note'>—</p>"}</div>
<div class="card"><h2>주요 수치·레벨</h2>{f"<table><tr><th>항목</th><th>값</th><th>맥락</th></tr>{nums}</table>" if nums else "<p class='note'>—</p>"}</div>
<div class="card gold"><h2>체크포인트 (앞으로 확인할 것)</h2>{li(s.get('checkpoints', []))}</div>
<div class="card red"><h2>리스크·반대 시나리오</h2>{li(s.get('risks', []))}</div>
<div class="card"><h2>원문 발언</h2>{"".join(f"<div class='quote'>“{e(q)}”</div>" for q in s.get('quotes', []))}</div>
<div class="note">자막 기반 자동 요약 ({e(s.get('model',''))}) — 수치·고유명사는 원본 영상으로 재확인. 유료 멤버십 콘텐츠의 요약은 개인 참고용.</div>
</div></body></html>"""


def index(all_s):
    by_ch = {}
    for s in all_s:
        by_ch.setdefault(s["channel"], []).append(s)
    items = "".join(
        f"<a href='{e(s['channel'])}/{e(s['_file'])}' data-ch='{e(s['channel'])}'>"
        f"<div class='d'>{e(s.get('published',''))} · {e(CHANNELS.get(s['channel'],{}).get('name',s['channel']))}"
        f"{' · 🔒' if s.get('members_only') else ''}</div>"
        f"<div class='t'>{e(s.get('title',''))}</div><div class='o'>{e(s.get('one_liner',''))}</div></a>"
        for s in all_s)
    tabs = "<button class='on' data-ch=''>전체</button>" + "".join(
        f"<button data-ch='{e(k)}'>{e(CHANNELS.get(k,{}).get('emoji',''))} {e(CHANNELS.get(k,{}).get('name',k))} ({len(v)})</button>"
        for k, v in by_ch.items())
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>유튜브 영상 요약 리포트</title><style>{CSS}</style></head><body><div class="wrap">
<div class="hero"><span class="eyebrow">YOUTUBE SUMMARY REPORTS</span><h1>📺 유튜브 영상 요약 리포트</h1>
<div class="q">총 {len(all_s)}건 · {' · '.join(e(c.get('name','')) for c in CHANNELS.values())} · <a href="../index.html">← 대시보드</a></div></div>
<div class="tabs">{tabs}</div>
<div class="list" id="list">{items or "<p class='note'>아직 요약이 없습니다. README 의 절차대로 fetch → summarize → build.</p>"}</div>
<script>
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
  document.querySelectorAll('#list a').forEach(a=>a.style.display=(!b.dataset.ch||a.dataset.ch===b.dataset.ch)?'':'none');}});
</script></div></body></html>"""


def main():
    all_s = []
    for p in sorted(SM.glob("*/*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        s.setdefault("channel", p.parent.name)
        s["_file"] = p.with_suffix(".html").name
        out = ROOT / s["channel"] / s["_file"]
        out.parent.mkdir(exist_ok=True)
        out.write_text(page(s), encoding="utf-8")
        all_s.append(s)
    all_s.sort(key=lambda s: (s.get("published", ""), s["_file"]), reverse=True)
    (ROOT / "index.html").write_text(index(all_s), encoding="utf-8")
    print(f"youtube/index.html + {len(all_s)}개 페이지 생성")


if __name__ == "__main__":
    main()
