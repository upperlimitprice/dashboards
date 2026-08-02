"""대시보드 index.html 자동 생성 — 저장소 파일 스캔. (launchd 매일 실행)"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DESC = {
    "signals.html": ("🚦 시장 신호등 (국내·미국)", "Market Score · ADR · 모멘텀 · RSI · VIX · E-Ratio"),
    "kr-breadth.html": ("📉 KOSPI 이격도·신용잔고", "60일 이격도(1990~) · 3개월 수익률 · 신용잔고/시총"),
    "cds.html": ("🏦 빅테크 5년 CDS 트래커", "MSFT·GOOGL·AMZN·META·NVDA·ORCL·CRWV 신용위험"),
    "osc.html": ("📊 수급 오실레이터", "종목 검색 — 시가총액 vs 외국인·기관 수급 MACD (2,455종목)"),
    "tanker.html": ("🛢 탱커 운임 마켓", "VLCC·수에즈막스 WS · LPG/LNG · BCTI · 선가 · 픽스처"),
    "funds.html": ("💼 주체별 증시자금", "외국인 보유액·비중 · 국내(기관+개인) · 투자자예탁금 · 신용융자"),
    "kci.html": ("📈 고려신용정보 급등 분석", "장중 +10% 이상 25회 전후 수익률 히트맵"),
    "parts-trend.html": ("📦 전자부품 리드타임 트렌드", "Future Electronics 월간 — 카테고리별 리드타임·가격 방향"),
    "fx-flow.html": ("💱 환율×외국인 수급 공식", "원화 1% 절하당 외국인 순매도 효과"),
    "fx-flow-5y.html": ("💱 환율×수급 5개년 백테스트", "연도별·환율구간별 민감도 매트릭스"),
    "lpddr.html": ("🧠 LPDDR 백서 (Micron×Meta)", "AI 서버 LPDDR 채택 기술 분석"),
}


def title_of(p):
    m = re.search(r"<title>([^<]+)</title>", p.read_text(encoding="utf-8", errors="ignore")[:2000])
    return m.group(1) if m else p.stem


def main():
    parts = ["""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>대시보드 목록</title>
<style>body{font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;max-width:680px;margin:50px auto;padding:0 20px;color:#20262e}
h1{font-size:1.35rem}h2{font-size:1rem;margin:28px 0 6px;color:#6b7683}
a{display:block;padding:13px 18px;border:1.5px solid #dde3e9;border-radius:10px;margin:9px 0;text-decoration:none;color:#20262e;font-weight:600}
a:hover{border-color:#b07d1e;background:#fffbf0}small{color:#6b7683;font-weight:400;display:block;margin-top:3px}</style></head><body>
<h1>📊 쩜상리서치 대시보드</h1>"""]

    parts.append("<h2>데일리 모니터 <small style='font-weight:400;color:#9aa4ad'>(드래그로 순서 변경 — 브라우저에 저장됨)</small></h2>")
    parts.append("<div id='daily'>")
    for f in ("signals.html", "kr-breadth.html", "funds.html", "cds.html", "tanker.html", "osc.html"):
        if (ROOT / f).exists():
            t, d = DESC[f]
            parts.append(f'<a draggable="true" data-k="{f}" href="{f}">{t}<small>{d}</small></a>')
    flows = sorted(ROOT.glob("flows/*.html"), reverse=True)
    if flows:
        latest = flows[0]
        parts.append(f'<a draggable="true" data-k="flows" href="flows/{latest.name}">💰 수급 주체별 시총대비 Top20 (최신 {latest.stem})'
                     f'<small>사모·투신·연기금·외국인·프로그램 순매수/순매도'
                     + (" · 과거: " + " · ".join(f'<a style="display:inline;border:0;padding:0" href="flows/{p.name}">{p.stem}</a>' for p in flows[1:6]) if len(flows) > 1 else "")
                     + "</small></a>")
    parts.append("</div>")
    parts.append("""<script>
(function(){
  const box=document.getElementById('daily');
  const KEY='dailyOrder';
  const saved=JSON.parse(localStorage.getItem(KEY)||'[]');
  if(saved.length){
    saved.forEach(k=>{const el=box.querySelector(`[data-k="${k}"]`);if(el)box.appendChild(el);});
  }
  let drag=null;
  box.querySelectorAll('a[draggable]').forEach(el=>{
    el.addEventListener('dragstart',e=>{drag=el;el.style.opacity=.4;});
    el.addEventListener('dragend',()=>{drag&&(drag.style.opacity=1);drag=null;
      localStorage.setItem(KEY,JSON.stringify([...box.querySelectorAll('a[draggable]')].map(x=>x.dataset.k)));});
    el.addEventListener('dragover',e=>{e.preventDefault();
      if(!drag||drag===el)return;
      const r=el.getBoundingClientRect();
      box.insertBefore(drag, e.clientY < r.top+r.height/2 ? el : el.nextSibling);});
  });
})();
</script>""")

    parts.append("<h2>분석 리포트</h2>")
    # 목록 제외: kci.html, lpddr.html, calls/ (2026-07-31 사용자 요청 — 직접 링크로는 접근 가능)
    for f in ("parts-trend.html", "fx-flow.html", "fx-flow-5y.html"):
        if (ROOT / f).exists():
            t, d = DESC[f]
            parts.append(f'<a href="{f}">{t}<small>{d}</small></a>')

    parts.append("</body></html>")
    (ROOT / "index.html").write_text("\n".join(parts), encoding="utf-8")
    print(f"index.html 생성 — flows {len(flows)}")


if __name__ == "__main__":
    main()
