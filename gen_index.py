"""대시보드 index.html 자동 생성 — 위젯형 (탈부착·드래그, localStorage 저장)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# (key, 제목, 설명, 기본 메인 포함 여부) — 특수 key(flows/calls)는 동적 처리
ITEMS = [
    ("signals.html", "🚦 시장 신호등 (국내·미국)", "Market Score · ADR · 모멘텀 · RSI · VIX · E-Ratio", True),
    ("kr-breadth.html", "📉 KOSPI 이격도·신용잔고", "60일 이격도(1990~) · 3개월 수익률 · 신용잔고/시총", True),
    ("funds.html", "💼 주체별 증시자금", "외국인 보유액·비중 · 국내(기관+개인) · 투자자예탁금 · 신용융자", True),
    ("cds.html", "🏦 빅테크 5년 CDS 트래커", "MSFT·GOOGL·AMZN·META·NVDA·ORCL·CRWV 신용위험", True),
    ("tanker.html", "🛢 탱커 운임 마켓", "VLCC·수에즈막스 WS · LPG/LNG · BCTI · 선가 · 픽스처", True),
    ("osc.html", "📊 수급 오실레이터", "종목·섹터 검색 — 시총 vs 수급 MACD · 주체별 상위 · 바닥 근접", True),
    ("flows", "💰 수급 주체별 시총대비 Top20", "", True),
    ("parts-trend.html", "📦 전자부품 리드타임 트렌드", "Future Electronics 월간 — 카테고리별 리드타임·가격 방향", True),
    ("fx-flow.html", "💱 환율×외국인 수급 공식", "원화 1% 절하당 외국인 순매도 효과", True),
    ("fx-flow-5y.html", "💱 환율×수급 5개년 백테스트", "연도별·환율구간별 민감도 매트릭스", True),
    ("kci.html", "📈 고려신용정보 급등 분석", "장중 +10% 이상 25회 전후 수익률 히트맵", False),
    ("lpddr.html", "🧠 LPDDR 백서 (Micron×Meta)", "AI 서버 LPDDR 채택 기술 분석", False),
    ("calls", "📞 어닝콜 분기 변화분석", "", False),
]


def main():
    registry = []
    for key, title, desc, on in ITEMS:
        href = key
        if key == "flows":
            flows = sorted(ROOT.glob("flows/*.html"), reverse=True)
            if not flows:
                continue
            href = f"flows/{flows[0].name}"
            title += f" ({flows[0].stem})"
            desc = ("사모·투신·연기금·외국인·프로그램 순매수/순매도 · 과거: "
                    + " · ".join(f"<a href='flows/{p.name}'>{p.stem}</a>" for p in flows[1:6]))
        elif key == "calls":
            calls = sorted(ROOT.glob("calls/*.html"), key=lambda p: p.stem.split("-", 1)[1], reverse=True)
            if not calls:
                continue
            href = f"calls/{calls[0].name}"
            desc = f"총 {len(calls)}건 · 최신: " + " · ".join(
                f"<a href='calls/{p.name}'>{p.stem.split('-',1)[0]}</a>" for p in calls[:6])
        elif not (ROOT / key).exists():
            continue
        registry.append({"k": key, "t": title, "d": desc, "h": href, "on": on})

    reg_json = json.dumps(registry, ensure_ascii=False)
    page = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>대시보드</title>
<style>
body{font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;max-width:1080px;margin:40px auto;padding:0 20px;color:#20262e;background:#f7f8fa}
h1{font-size:1.35rem}
.layout{display:grid;grid-template-columns:1fr 290px;gap:22px;align-items:start}
@media(max-width:860px){.layout{grid-template-columns:1fr}}
h2{font-size:.92rem;margin:0 0 10px;color:#6b7683}
.card{position:relative;display:block;padding:14px 40px 14px 18px;border:1.5px solid #dde3e9;border-radius:11px;margin:10px 0;color:#20262e;font-weight:600;background:#fff;cursor:pointer}
.card:hover{border-color:#b07d1e;background:#fffbf0}
.card small{color:#6b7683;font-weight:400;display:block;margin-top:3px;font-size:.78rem}
.card small a{color:#1f6fd6;text-decoration:none}
.x{position:absolute;top:8px;right:10px;border:0;background:none;color:#c2cad2;font-size:1.05rem;cursor:pointer;line-height:1}
.x:hover{color:#d63c2f}
#side{background:#fff;border:1.5px solid #dde3e9;border-radius:12px;padding:14px 16px;position:sticky;top:16px}
.sitem{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:9px 2px;border-bottom:1px solid #f0f3f6;font-size:.85rem}
.sitem:last-child{border-bottom:0}
.sitem .nm{color:#20262e}
.add{border:1.5px solid #1f6fd6;color:#1f6fd6;background:#fff;border-radius:8px;font-size:.95rem;width:26px;height:26px;cursor:pointer;font-weight:700;flex:none}
.add:hover{background:#eef5fe}
.hint{font-size:.72rem;color:#9aa4ad;margin-top:10px}
.empty{color:#9aa4ad;font-size:.82rem;padding:8px 0}
</style></head><body>
<h1>📊 쩜상리서치 대시보드</h1>
<div class='layout'>
<div><h2>메인 <small style='font-weight:400'>(드래그로 순서 변경 · ✕로 보관함으로 이동)</small></h2><div id='main'></div></div>
<div id='side'><h2>🗂 전체 위젯 보관함</h2><div id='sideList'></div>
<div class='hint'>＋를 누르면 메인에 추가됩니다. 구성은 이 브라우저에 저장됩니다.</div></div>
</div>
<script>
const REG=__REG__;
const KEY='dashLayout2';
let state=JSON.parse(localStorage.getItem(KEY)||'null');
if(!state||!Array.isArray(state.main)) state={main:REG.filter(x=>x.on).map(x=>x.k)};
state.main=state.main.filter(k=>REG.some(x=>x.k===k));
function save(){localStorage.setItem(KEY,JSON.stringify(state));}
function item(k){return REG.find(x=>x.k===k);}
function render(){
  const main=document.getElementById('main');
  main.innerHTML=state.main.map(k=>{const x=item(k);return `<div class='card' draggable='true' data-k='${x.k}' onclick='go(event,"${x.h}")'>${x.t}<small>${x.d}</small><button class='x' title='보관함으로' onclick='return rm(event,"${x.k}")'>✕</button></div>`;}).join('')||"<div class='empty'>보관함에서 ＋를 눌러 위젯을 추가하세요</div>";
  const rest=REG.filter(x=>!state.main.includes(x.k));
  document.getElementById('sideList').innerHTML=rest.map(x=>`<div class='sitem'><span class='nm'>${x.t}</span><button class='add' onclick='addW("${x.k}")'>＋</button></div>`).join('')||"<div class='empty'>모든 위젯이 메인에 있습니다</div>";
  wireDrag();
}
function go(e,h){if(e.target.closest('a,.x'))return;location.href=h;}
function rm(e,k){e.preventDefault();e.stopPropagation();state.main=state.main.filter(x=>x!==k);save();render();return false;}
function addW(k){state.main.push(k);save();render();}
function syncOrder(){
  state.main=[...document.querySelectorAll('#main .card[draggable]')].map(x=>x.dataset.k);
  save();  // 드래그 순간마다 즉시 저장 — 새로고침해도 마지막 배치 유지
}
function wireDrag(){
  const box=document.getElementById('main');let drag=null;
  box.addEventListener('dragover',e=>e.preventDefault());
  box.addEventListener('drop',e=>{e.preventDefault();syncOrder();});
  box.querySelectorAll('.card[draggable]').forEach(el=>{
    el.addEventListener('dragstart',()=>{drag=el;el.style.opacity=.4;});
    el.addEventListener('dragend',()=>{if(drag)drag.style.opacity=1;drag=null;syncOrder();});
    el.addEventListener('dragover',e=>{e.preventDefault();
      if(!drag||drag===el)return;
      const r=el.getBoundingClientRect();
      box.insertBefore(drag, e.clientY<r.top+r.height/2?el:el.nextSibling);
      syncOrder();});
  });
}
window.addEventListener('pageshow',()=>{ /* 뒤로가기 복원 시에도 저장된 배치 재적용 */
  const s2=JSON.parse(localStorage.getItem(KEY)||'null');
  if(s2&&Array.isArray(s2.main)){state=s2;state.main=state.main.filter(k=>REG.some(x=>x.k===k));render();}
});
render();
</script>
</body></html>"""
    page = page.replace("__REG__", reg_json)
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"index.html 생성 — 위젯 {len(registry)}개")


if __name__ == "__main__":
    main()
