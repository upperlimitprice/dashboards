"""대시보드 index.html 자동 생성 — 위젯형 (탈부착·드래그, localStorage 저장)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# (key, 제목, 설명, 기본 메인 포함 여부) — 특수 key(flows/calls)는 동적 처리
ITEMS = [
    ("signals.html", "🚦 시장 신호등 (국내·미국)", "Market Score · ADR · 모멘텀 · RSI · VIX · E-Ratio", True),
    ("kr-breadth.html", "📉 KOSPI 이격도·신용잔고", "60일 이격도(1990~) · 3개월 수익률 · 신용잔고/시총", True),
    ("kospi-ff.html", "🌏 KOSPI 외국인 현·선물 추이", "현물+선물 순매수 합산 20/60/120MA · 수급 방향/모멘텀 시그널", True),
    ("funds.html", "💼 주체별 증시자금", "외국인 보유액·비중 · 국내(기관+개인) · 투자자예탁금 · 신용융자", True),
    ("cds.html", "🏦 빅테크 5년 CDS 트래커", "MSFT·GOOGL·AMZN·META·NVDA·ORCL·CRWV 신용위험", True),
    ("tanker.html", "🛢 탱커 운임 마켓", "VLCC·수에즈막스 WS · LPG/LNG · BCTI · 선가 · 픽스처", True),
    ("us-liq.html", "💵 미국 유동성 (US Liquidity)", "연준BS−TGA−RRP · 국채금리 3M/2Y/10Y/30Y · DXY · WTI/브렌트 · 재무부 경매일정", True),
    ("valuation.html", "🌡 밸류에이션 온도", "금리·물가·예탁금 조합 지표 vs KOSPI 밸류 (r=0.78) · 금리 12M 선행 경보", True),
    ("tval.html", "💹 거래대금", "전체·회전율 Top30 · 섹터별 Top10 (상품 제외)", True),
    ("etf.html", "🧺 ETF", "거래대금 순위 · 자금 순증/순유출 Top10 · 인사이트", True),
    ("osc.html", "📊 수급 오실레이터", "종목·섹터 검색 — 시총 vs 수급 MACD · 주체별 상위 · 바닥 근접", True),
    ("leaders.html", "🎯 주도 섹터·주도주 포착", "RS(가중)·자금·신고가·눌림·수급·펀더 스코어 — 추세추종 아카이브 기준 계량화 · 일정 캘린더", True),
    ("taiwan-revenue.html", "🇹🇼 대만 AI 밸류체인 월매출", "MOPS 의무공시 — 26그룹 128종목 · 월별 매출·MoM·YoY (매일 갱신)", True),
    ("sector-toppick.html", "🏆 섹터 탑픽 보고서 (2026-08-10)", "30개 섹터 모멘텀 랭킹 · 탑픽 TOP15 · 종목별 3줄 요약", True),
    ("orders.html", "📋 수주잔고 트래커", "DART 정기보고서 수주상황 전수 파싱 — 기업 검색·분기 추이 · QoQ/YoY 증가 상위", True),
    ("util.html", "🏭 가동률 트래커", "정기보고서 가동률 전수 파싱 — 부문별 라인차트 · YoY/QoQ 상승·고가동 랭킹", True),
    ("hs.html", "🚢 HS코드 월 수출 모니터", "관세청 품목별 수출(USD) — 제품별 실적 선행 프록시 · YoY 모멘텀", True),
    ("cost.html", "🧮 비용구조 모델", "비용의 성격별 분류 전수 파싱 — 기업 검색 · 분기 flow·연간 매트릭스 · 엑셀 다운로드", True),
    ("vs.html", "📊 VS 재무·비용 리포트", "기업 검색 → 손익·비용 세부(%of Sales)·판관비·세그먼트·수주 통합 섹션 리포트", True),
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
            href = f"flows/{flows[0].name}?v={int(flows[0].stat().st_mtime)}"
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
.rf{position:absolute;bottom:8px;right:10px;border:1px solid #dde3e9;background:#fff;color:#6b7683;font-size:.72rem;border-radius:7px;padding:2px 7px;cursor:pointer;font-weight:600}
.rf:hover{border-color:#1f6fd6;color:#1f6fd6}
.rf:disabled{opacity:.6;cursor:default}
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1c2530;color:#fff;font-size:.82rem;padding:9px 16px;border-radius:9px;opacity:0;transition:opacity .3s;pointer-events:none;z-index:99}
#toast.show{opacity:.95}
#side{background:#fff;border:1.5px solid #dde3e9;border-radius:12px;padding:14px 16px;position:sticky;top:16px}
.sitem{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:9px 2px;border-bottom:1px solid #f0f3f6;font-size:.85rem}
.sitem:last-child{border-bottom:0}
.sitem .nm{color:#20262e}
.add{border:1.5px solid #1f6fd6;color:#1f6fd6;background:#fff;border-radius:8px;font-size:.95rem;width:26px;height:26px;cursor:pointer;font-weight:700;flex:none}
.add:hover{background:#eef5fe}
.hint{font-size:.72rem;color:#9aa4ad;margin-top:10px}
.empty{color:#9aa4ad;font-size:.82rem;padding:8px 0}
body:not(.admin) .x,body:not(.admin) #side,body:not(.admin) h2 small{display:none}
body:not(.admin) .layout{grid-template-columns:1fr}
body:not(.admin) .card{cursor:pointer}
</style></head><body>
<h1>📊 쩜상리서치 대시보드</h1>
<div class='layout'>
<div><h2>메인 <small style='font-weight:400'>(드래그로 순서 변경 · ✕로 보관함으로 이동)</small></h2><div id='main'></div></div>
<div id='side'><h2>🗂 전체 위젯 보관함</h2><div id='sideList'></div>
<div class='hint'>＋를 누르면 메인에 추가됩니다. 구성은 이 브라우저에 저장됩니다.</div></div>
</div>
<script>
const REG=__REG__;
// 카드 → 갱신 서버 잡 매핑 (수동 갱신 버튼)
const JOB={"signals.html":"signals","kr-breadth.html":"breadth","funds.html":"breadth","valuation.html":"breadth",
"kospi-ff.html":"kospiff","cds.html":"cds","tanker.html":"tanker","us-liq.html":"usliq","tval.html":"tval",
"etf.html":"tval","osc.html":"osc","leaders.html":"leaders","taiwan-revenue.html":"taiwan","flows":"flows",
"orders.html":"orders","cost.html":"cost","util.html":"util","hs.html":"hs","vs.html":"vsr"};
let EP=null;
async function ep(){if(EP!==null)return EP;try{EP=(await fetch('endpoint.json?'+Date.now()).then(r=>r.json())).url;}catch(e){EP='';}return EP;}
async function refresh(e,k){
  e.preventDefault();e.stopPropagation();
  const btn=e.target;const job=JOB[k];if(!job)return false;
  const url=await ep();
  if(!url){btn.textContent='서버꺼짐';setTimeout(()=>btn.textContent='↻',2500);return false;}
  btn.textContent='…';btn.disabled=true;
  try{
    const r=await fetch(url+'/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job})}).then(x=>x.json());
    if(r.status==='started'){btn.textContent='갱신중';setTimeout(()=>{btn.textContent='↻';btn.disabled=false;},120000);
      toast(`${job} 갱신 시작 — 1~3분 후 해당 페이지를 새로고침하세요`);}
    else if(r.status==='cooldown'){btn.textContent='↻';btn.disabled=false;toast(`쿨다운: ${r.wait}초 후 다시 시도`);}
    else if(r.status==='busy'){btn.textContent='↻';btn.disabled=false;toast('이미 갱신 중입니다');}
    else{btn.textContent='↻';btn.disabled=false;}
  }catch(err){btn.textContent='실패';setTimeout(()=>{btn.textContent='↻';btn.disabled=false;},2500);}
  return false;
}
function toast(msg){
  let t=document.getElementById('toast');
  if(!t){t=document.createElement('div');t.id='toast';document.body.appendChild(t);}
  t.textContent=msg;t.className='show';setTimeout(()=>t.className='',4000);
}
const KEY='dashLayout2';
const ADMIN_IPS=['222.108.214.107'];
const ADMIN_PASS='jjeomsang-only';
let ADMIN=localStorage.getItem('dashAdmin')==='1';
const q=new URLSearchParams(location.search);
if(q.get('admin')===ADMIN_PASS){ADMIN=true;localStorage.setItem('dashAdmin','1');}
if(q.get('admin')==='off'){ADMIN=false;localStorage.removeItem('dashAdmin');}
let PUB=null;   // 관리자가 발행한 공개 배치 (layout.json)
let GH=localStorage.getItem('dashGH')||'';
if(q.get('ghtoken')){GH=q.get('ghtoken');localStorage.setItem('dashGH',GH);history.replaceState(null,'',location.pathname);}
let state=JSON.parse(localStorage.getItem(KEY)||'null');
if(!state||!Array.isArray(state.main)) state={main:REG.filter(x=>x.on).map(x=>x.k)};
state.main=state.main.filter(k=>REG.some(x=>x.k===k));
async function publish(){
  if(!GH)return;
  try{
    const api='https://api.github.com/repos/upperlimitprice/dashboards/contents/layout.json';
    const h={'Authorization':'Bearer '+GH,'Accept':'application/vnd.github+json'};
    const cur=await fetch(api,{headers:h}).then(r=>r.ok?r.json():null);
    await fetch(api,{method:'PUT',headers:h,body:JSON.stringify({
      message:'layout update',
      content:btoa(unescape(encodeURIComponent(JSON.stringify({main:state.main})))),
      sha:cur?cur.sha:undefined})});
  }catch(e){}
}
let pubT=null;
function save(){localStorage.setItem(KEY,JSON.stringify(state));
  if(GH){clearTimeout(pubT);pubT=setTimeout(publish,2500);}}
function item(k){return REG.find(x=>x.k===k);}
function render(){
  const main=document.getElementById('main');
  main.innerHTML=state.main.map(k=>{const x=item(k);const rf=JOB[x.k]?`<button class='rf' title='데이터 수동 갱신' onclick='return refresh(event,"${x.k}")'>↻</button>`:'';return `<div class='card' draggable='true' data-k='${x.k}' onclick='go(event,"${x.h}")'>${x.t}<small>${x.d}</small>${rf}<button class='x' title='보관함으로' onclick='return rm(event,"${x.k}")'>✕</button></div>`;}).join('')||"<div class='empty'>보관함에서 ＋를 눌러 위젯을 추가하세요</div>";
  const rest=REG.filter(x=>!state.main.includes(x.k));
  document.getElementById('sideList').innerHTML=rest.map(x=>`<div class='sitem'><span class='nm'>${x.t}</span><button class='add' onclick='addW("${x.k}")'>＋</button></div>`).join('')||"<div class='empty'>모든 위젯이 메인에 있습니다</div>";
  wireDrag();
}
function go(e,h){if(e.target.closest('a,.x,.rf'))return;location.href=h;}
function rm(e,k){e.preventDefault();e.stopPropagation();state.main=state.main.filter(x=>x!==k);save();render();return false;}
function addW(k){state.main.push(k);save();render();}
function syncOrder(){
  state.main=[...document.querySelectorAll('#main .card[draggable]')].map(x=>x.dataset.k);
  save();  // 드래그 순간마다 즉시 저장 — 새로고침해도 마지막 배치 유지
}
function wireDrag(){
  if(!ADMIN)return;
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
function applyAdmin(){
  if(ADMIN){document.body.classList.add('admin');return;}
  // 방문자: 관리자가 발행한 배치(layout.json) 적용, 없으면 기본 배치
  const base=(PUB&&Array.isArray(PUB.main))?PUB.main.filter(k=>REG.some(x=>x.k===k)):REG.filter(x=>x.on).map(x=>x.k);
  state={main:base};
  document.body.classList.remove('admin');
  render();
}
render();
fetch('layout.json?v='+Date.now()).then(r=>r.ok?r.json():null).then(j=>{PUB=j;
  // 발행 배치에 새로 추가된 카드는 관리자 로컬 배치에도 자동 합류
  if(PUB&&Array.isArray(PUB.main))PUB.main.forEach(k=>{if(REG.some(x=>x.k===k)&&!state.main.includes(k))state.main.push(k);});
  applyAdmin();}).catch(()=>applyAdmin());
if(!ADMIN){
  fetch('https://api.ipify.org?format=json').then(r=>r.json()).then(d=>{
    if(ADMIN_IPS.includes(d.ip)){ADMIN=true;localStorage.setItem('dashAdmin','1');
      state=JSON.parse(localStorage.getItem(KEY)||'null')||{main:REG.filter(x=>x.on).map(x=>x.k)};
      state.main=(state.main||[]).filter(k=>REG.some(x=>x.k===k));
      document.body.classList.add('admin');render();}
  }).catch(()=>{});
}
</script>
</body></html>"""
    page = page.replace("__REG__", reg_json)
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"index.html 생성 — 위젯 {len(registry)}개")


if __name__ == "__main__":
    main()
