/* 대시보드 공통 라이트/다크 전환 (사용자 지시 2026-11-03) — 모든 페이지 <head> 끝에 자동 삽입(tools/inject_theme.py, git pre-commit 훅)
 * 선택: 🖥 시스템(기기 설정) → ☀ 라이트 → 🌙 다크, localStorage 'dash-theme'
 * 적용 방식(페이지마다 만든 방식이 달라 3단계):
 *  ① <html data-theme="light|dark"> — data-theme 규칙이 있는 페이지
 *  ② (prefers-color-scheme) 미디어 규칙을 선택한 모드로 강제 전환 — 기기 설정만 따르던 페이지
 *  ③ 그래도 배경 밝기가 선택과 반대면(한 가지 테마만 있는 페이지) 색 반전 + 사진·영상은 원래 색
 */
(function () {
  var K = 'dash-theme', root = document.documentElement, pref = null;
  try { pref = localStorage.getItem(K); } catch (e) {}
  if (pref !== 'light' && pref !== 'dark') pref = null;
  var sys = function () { return window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; };
  var want = function () { return pref || sys(); };

  if (pref) root.setAttribute('data-theme', pref);
  try { if (pref) localStorage.setItem('semi-theme', pref); } catch (e) {}

  var ON = '(min-width: 0px)', OFF = '(max-width: -1px)';
  function walk(list, cb) {
    for (var i = 0; i < list.length; i++) {
      var r = list[i];
      if (r.media && r.cssRules && /prefers-color-scheme/.test(r.media.mediaText)) cb(r);
      else if (r.cssRules) { try { walk(r.cssRules, cb); } catch (e) {} }
    }
  }
  function media() {
    if (!pref) return;
    for (var s = 0; s < document.styleSheets.length; s++) {
      var list; try { list = document.styleSheets[s].cssRules; } catch (e) { continue; }
      walk(list, function (r) {
        var t = r.media.mediaText;
        var n = t.replace(/\(\s*prefers-color-scheme\s*:\s*(dark|light)\s*\)/g, function (_, m) { return m === pref ? ON : OFF; });
        if (n !== t) r.media.mediaText = n;
      });
    }
  }
  media();

  function lum(el) {
    var c = getComputedStyle(el).backgroundColor, m = c && c.match(/[\d.]+/g);
    if (!m || (m.length > 3 && +m[3] === 0)) return null;
    return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255;
  }
  function fallback() {
    if (!pref || !document.body) return;
    var l = lum(document.body); if (l == null) l = lum(root); if (l == null) l = 1;  // 배경 미지정 = 브라우저 기본 흰색
    if ((pref === 'dark' && l > 0.5) || (pref === 'light' && l < 0.5)) {
      var st = document.createElement('style');
      st.textContent = 'html.dt-inv{filter:invert(1) hue-rotate(180deg);background:' + (pref === 'dark' ? '#fff' : '#000') + '}' +
        'html.dt-inv img,html.dt-inv video,html.dt-inv picture,html.dt-inv iframe,html.dt-inv [style*="background-image"]{filter:invert(1) hue-rotate(180deg)}';
      document.head.appendChild(st);
      root.classList.add('dt-inv');
    }
  }

  function button() {
    if (document.getElementById('dt-btn') || document.getElementById('thm')) return;  // 자체 전환 버튼이 있는 페이지(테크 밸류체인·미국 캘린더)는 그 버튼 사용(같은 설정 공유)
    var b = document.createElement('button'), L = { '': '🖥 시스템', light: '☀ 라이트', dark: '🌙 다크' };
    b.id = 'dt-btn'; b.type = 'button'; b.textContent = L[pref || ''];
    b.title = '화면 모드: 시스템(기기 설정) → 라이트 → 다크 (이 브라우저에 기억)';
    b.setAttribute('style', 'position:fixed;right:12px;bottom:12px;z-index:2147483000;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;' +
      'padding:7px 10px;border-radius:999px;border:1px solid rgba(128,128,128,.45);background:rgba(128,128,128,.18);color:inherit;cursor:pointer;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);opacity:.85');
    if (root.classList.contains('dt-inv')) b.style.filter = 'invert(1) hue-rotate(180deg)';
    b.onclick = function () {
      var nx = pref === null ? 'light' : pref === 'light' ? 'dark' : null;
      try { if (nx) { localStorage.setItem(K, nx); localStorage.setItem('semi-theme', nx); } else { localStorage.removeItem(K); localStorage.removeItem('semi-theme'); } } catch (e) {}
      location.reload();  // 차트가 테마 색을 다시 읽도록 새로 그림
    };
    document.body.appendChild(b);
  }

  function ready() { media(); fallback(); button(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();
  window.dashTheme = { pref: function () { return pref; }, want: want };
})();
