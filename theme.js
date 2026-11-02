/* \ub300\uc2dc\ubcf4\ub4dc \uacf5\ud1b5 \ub77c\uc774\ud2b8/\ub2e4\ud06c \uc804\ud658 (\uc0ac\uc6a9\uc790 \uc9c0\uc2dc 2026-11-03) \u2014 \ubaa8\ub4e0 \ud398\uc774\uc9c0 <head> \ub05d\uc5d0 \uc790\ub3d9 \uc0bd\uc785(tools/inject_theme.py, git pre-commit \ud6c5)
 * \uc120\ud0dd: \ud83d\udda5 \uc2dc\uc2a4\ud15c(\uae30\uae30 \uc124\uc815) \u2192 \u2600 \ub77c\uc774\ud2b8 \u2192 \ud83c\udf19 \ub2e4\ud06c, localStorage 'dash-theme' \u00b7 \ubc84\ud2bc\uc740 \uc6b0\uce21 \uc0c1\ub2e8(2026-11-03)
 * \uc801\uc6a9 \ubc29\uc2dd(\ud398\uc774\uc9c0\ub9c8\ub2e4 \ub9cc\ub4e0 \ubc29\uc2dd\uc774 \ub2ec\ub77c 3\ub2e8\uacc4):
 *  \u2460 <html data-theme="light|dark"> \u2014 data-theme \uaddc\uce59\uc774 \uc788\ub294 \ud398\uc774\uc9c0
 *  \u2461 (prefers-color-scheme) \ubbf8\ub514\uc5b4 \uaddc\uce59\uc744 \uc120\ud0dd\ud55c \ubaa8\ub4dc\ub85c \uac15\uc81c \uc804\ud658 \u2014 \uae30\uae30 \uc124\uc815\ub9cc \ub530\ub974\ub358 \ud398\uc774\uc9c0
 *  \u2462 \uadf8\ub798\ub3c4 \ubc30\uacbd \ubc1d\uae30\uac00 \uc120\ud0dd\uacfc \ubc18\ub300\uba74(\ud55c \uac00\uc9c0 \ud14c\ub9c8\ub9cc \uc788\ub294 \ud398\uc774\uc9c0) \uc0c9 \ubc18\uc804 + \uc0ac\uc9c4\u00b7\uc601\uc0c1\uc740 \uc6d0\ub798 \uc0c9
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
  // \u2462 \ub77c\uc774\ud2b8 \uc804\uc6a9 \ud398\uc774\uc9c0\ub97c \ub2e4\ud06c\ub85c \ubcfc \ub54c: \uc0c9 \ubc18\uc804 \ub300\uc2e0 \uc0c9 \ud558\ub098\ud558\ub098\ub97c \ub2e4\ud06c \ud314\ub808\ud2b8\ub85c \ubcc0\ud658 (\uc0ac\uc6a9\uc790 \uc9c0\uc2dc 2026-11-03 \u2014 \ubc18\uc804\uc774 \ubd80\uc790\uc5f0\uc2a4\ub7ec\uc6c0)
  //    \ubc30\uacbd \ubc1d\uc740\uc0c9 \u2192 \uc9d9\uc740 \ub0a8\uc0c9 \uacc4\uc5f4 \u00b7 \uae00\uc790 \uc5b4\ub450\uc6b4\uc0c9 \u2192 \ud68c\ubc31\uc0c9 \u00b7 \uc5f0\ud55c \ud14c\ub450\ub9ac \u2192 \uc5b4\ub450\uc6b4 \ud68c\uc0c9 \u00b7 \uac15\uc870\uc0c9(\ube68\uac15\u00b7\ud30c\ub791 \ub4f1)\uc740 \uc0c9\uc0c1 \uc720\uc9c0\ud558\uace0 \ubc1d\uae30\ub9cc \uc870\uc815
  //    canvas \ucc28\ud2b8(\ubc1d\uc740 \ubc14\ud0d5\uc73c\ub85c \uadf8\ub824\uc9d0)\ub294 \ubc18\uc804\uc73c\ub85c \ub9de\ucd94\uace0, \uc0ac\uc9c4\u00b7\uc601\uc0c1\uc740 \uadf8\ub300\ub85c. \uc774\ud6c4 \uc2a4\ud06c\ub9bd\ud2b8\uac00 \ucd94\uac00\ud55c \uc694\uc18c\ub3c4 MutationObserver\ub85c \ub530\ub77c\uac10
  function hsl(r, g, b) { r /= 255; g /= 255; b /= 255; var mx = Math.max(r, g, b), mn = Math.min(r, g, b), h = 0, s = 0, l = (mx + mn) / 2, d = mx - mn;
    if (d) { s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn); h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h /= 6; } return [h, s, l]; }
  function rgbs(h, s, l) { function f(p, q, t) { if (t < 0) t += 1; if (t > 1) t -= 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; }
    var r, g, b; if (!s) r = g = b = l; else { var q = l < 0.5 ? l * (1 + s) : l + s - l * s, pp = 2 * l - q; r = f(pp, q, h + 1 / 3); g = f(pp, q, h); b = f(pp, q, h - 1 / 3); }
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)]; }
  var NAMED = { white: [255, 255, 255], black: [0, 0, 0], gray: [128, 128, 128], grey: [128, 128, 128], whitesmoke: [245, 245, 245], ghostwhite: [248, 248, 255], snow: [255, 250, 250], ivory: [255, 255, 240], lightgray: [211, 211, 211], lightgrey: [211, 211, 211], silver: [192, 192, 192], gainsboro: [220, 220, 220], darkgray: [169, 169, 169], dimgray: [105, 105, 105], aliceblue: [240, 248, 255], beige: [245, 245, 220], linen: [250, 240, 230], lavender: [230, 230, 250], navy: [0, 0, 128] };
  var CRE = /#([0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3,4})\b|rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,\/]+([\d.]+%?))?\s*\)|\b(white|black|gray|grey|whitesmoke|ghostwhite|snow|ivory|lightgr[ae]y|silver|gainsboro|darkgray|dimgray|aliceblue|beige|linen|lavender|navy)\b/gi;
  function parse(m, hx, r, g, b, a, nm) {
    if (nm) return NAMED[nm.toLowerCase()].concat([1]);
    if (hx) { var h = hx.length <= 4 ? hx.split('').map(function (c) { return c + c; }).join('') : hx;
      return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1]; }
    return [+r, +g, +b, a == null ? 1 : (/%$/.test(a) ? parseFloat(a) / 100 : +a)];
  }
  function conv(rgb, kind) {
    var x = hsl(rgb[0], rgb[1], rgb[2]), h = x[0], s = x[1], l = x[2], vivid = s > 0.35 && l > 0.15 && l < 0.85;
    if (kind === 'bg') { if (vivid && l < 0.7) { l = Math.max(0.28, Math.min(l, 0.42)); s *= 0.8; } else if (l >= 0.5) { l = 0.075 + (1 - l) * 0.55; s *= 0.55; } else l = Math.max(l, 0.12); }
    else if (kind === 'bd') { if (vivid) l = Math.max(l, 0.5); else if (l >= 0.5) { l = 0.2 + (1 - l) * 0.45; s *= 0.5; } else l = 0.3 + l * 0.3; }
    else { if (vivid) l = Math.max(l, 0.64); else if (l <= 0.6) { l = 0.93 - l * 0.55; s *= 0.6; } }
    var o = rgbs(h, s, Math.min(0.97, l)); return o;
  }
  function recolor(v, kind) { return v.replace(CRE, function (m, hx, r, g, b, a, nm) { if (/^#/.test(m) && !hx) return m; var c = parse(m, hx, r, g, b, a, nm), o = conv(c, kind);
    return c[3] < 1 ? 'rgba(' + o.join(',') + ',' + (+c[3].toFixed(3)) + ')' : 'rgb(' + o.join(',') + ')'; }); }
  var PK = { 'color': 'fg', 'background': 'bg', 'background-color': 'bg', 'background-image': 'bg', 'border-color': 'bd', 'border': 'bd', 'border-top': 'bd', 'border-bottom': 'bd', 'border-left': 'bd', 'border-right': 'bd',
    'border-top-color': 'bd', 'border-bottom-color': 'bd', 'border-left-color': 'bd', 'border-right-color': 'bd', 'outline': 'bd', 'outline-color': 'bd', 'box-shadow': 'sh', 'text-decoration-color': 'fg', 'caret-color': 'fg', 'fill': 'fill', 'stroke': 'stroke', 'column-rule-color': 'bd' };
  function svgKind(kind, v) { CRE.lastIndex = 0; var m = CRE.exec(v); CRE.lastIndex = 0; if (!m) return null; var c = parse.apply(null, m), l = hsl(c[0], c[1], c[2])[2]; return l > 0.82 ? 'bg' : l < 0.45 ? 'fg' : null; }  // SVG: \uc544\uc8fc \ubc1d\uc73c\uba74 \ubc14\ud0d5, \uc5b4\ub450\uc6b0\uba74 \uae00\uc790, \uc911\uac04(\ucc28\ud2b8 \uacc4\uc5f4\uc0c9)\uc740 \uc720\uc9c0
  function fixDecl(st) {
    for (var i = 0; i < st.length; i++) { var pn = st[i], k = PK[pn]; if (!k && /^--/.test(pn)) k = 'var'; if (!k) continue; var v = st.getPropertyValue(pn); if (!v || v.indexOf('var(') >= 0 && k !== 'var') { if (!/#|rgb|white|black/i.test(v)) continue; }
      var kk = k === 'sh' ? 'bd' : k === 'fill' || k === 'stroke' ? svgKind(k, v) : k === 'var' ? (/bg|back|card|panel|surface|paper|base|fill|bar|row|head|band|box/i.test(pn) ? 'bg' : /line|border|grid|rule|sep|divid/i.test(pn) ? 'bd' : 'fg') : k;
      if (!kk) continue; var nv = recolor(v, kk); if (nv !== v) st.setProperty(pn, nv, st.getPropertyPriority(pn)); }
  }
  function sheets() { for (var s = 0; s < document.styleSheets.length; s++) { var ss = document.styleSheets[s]; if (ss.ownerNode && ss.ownerNode.id === 'dt-dark') continue; var list; try { list = ss.cssRules; } catch (e) { continue; } walkStyle(list); } }
  function walkStyle(list) { for (var i = 0; i < list.length; i++) { var r = list[i]; if (r.__dk) continue; r.__dk = 1; if (r.style) fixDecl(r.style); if (r.cssRules) try { walkStyle(r.cssRules); } catch (e) {} } }
  function attrs(el) {
    if (el.nodeType !== 1 || el.id === 'dt-btn') return; if (el.__dk) return; el.__dk = 1;
    if (el.style && el.style.length) fixDecl(el.style);
    ['fill', 'stroke', 'color', 'bgcolor', 'stop-color'].forEach(function (a) { var v = el.getAttribute && el.getAttribute(a); if (v && CRE.test(v)) { CRE.lastIndex = 0; var k = a === 'bgcolor' ? 'bg' : a === 'color' ? 'fg' : svgKind(a, v); if (k) el.setAttribute(a, recolor(v, k)); } CRE.lastIndex = 0; });
  }
  function tree(n) { attrs(n); if (n.querySelectorAll) { var a = n.querySelectorAll('[style],[fill],[stroke],[bgcolor],[color],[stop-color]'); for (var i = 0; i < a.length; i++) attrs(a[i]); } }
  function darken() {
    root.classList.add('dt-dark');
    var st = document.createElement('style'); st.id = 'dt-dark';
    st.textContent = 'html.dt-dark{background:#0d131d;color-scheme:dark}html.dt-dark body{background-color:#0d131d;color:#dfe6ee}' +
      'html.dt-dark a{color:#8ab4ff}html.dt-dark canvas{filter:invert(.92) hue-rotate(180deg) saturate(1.1)}html.dt-dark input,html.dt-dark select,html.dt-dark textarea,html.dt-dark button:not(#dt-btn){background-color:#1a2333;color:#dfe6ee;border-color:#334055}';
    document.head.appendChild(st);
    sheets(); tree(document.body);
    var pend = false, q = [];
    new MutationObserver(function (ms) { ms.forEach(function (m) { if (m.type === 'attributes') { m.target.__dk = 0; q.push(m.target); } else m.addedNodes.forEach(function (n) { q.push(n); }); });
      if (!pend) { pend = true; requestAnimationFrame(function () { pend = false; var a = q; q = []; a.forEach(tree); sheets(); }); } })
      .observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'fill', 'stroke'] });
  }
  function fallback() {
    if (!pref || !document.body) return;
    var l = lum(document.body); if (l == null) l = lum(root); if (l == null) l = 1;  // \ubc30\uacbd \ubbf8\uc9c0\uc815 = \ube0c\ub77c\uc6b0\uc800 \uae30\ubcf8 \ud770\uc0c9
    if (pref === 'dark' && l > 0.5) { darken(); return; }  // \ub77c\uc774\ud2b8 \uc804\uc6a9 \ud398\uc774\uc9c0 \u2192 \ub2e4\ud06c \ud314\ub808\ud2b8 \ubcc0\ud658
    if (pref === 'light' && l < 0.5) {  // \ub2e4\ud06c \uc804\uc6a9 \ud398\uc774\uc9c0 \u2192 \ub77c\uc774\ud2b8: \ubc18\uc804(\ub4dc\ubb3e)
      var st = document.createElement('style');
      st.textContent = 'html.dt-inv{filter:invert(1) hue-rotate(180deg);background:#000}html.dt-inv img,html.dt-inv video,html.dt-inv picture,html.dt-inv iframe,html.dt-inv [style*="background-image"]{filter:invert(1) hue-rotate(180deg)}';
      document.head.appendChild(st); root.classList.add('dt-inv');
    }
  }

  function button() {
    if (document.getElementById('dt-btn') || document.getElementById('thm')) return;  // \uc790\uccb4 \uc804\ud658 \ubc84\ud2bc\uc774 \uc788\ub294 \ud398\uc774\uc9c0(\ud14c\ud06c \ubc38\ub958\uccb4\uc778\u00b7\ubbf8\uad6d \uce98\ub9b0\ub354)\ub294 \uadf8 \ubc84\ud2bc \uc0ac\uc6a9(\uac19\uc740 \uc124\uc815 \uacf5\uc720)
    var b = document.createElement('button'), L = { '': '\ud83d\udda5 \uc2dc\uc2a4\ud15c', light: '\u2600 \ub77c\uc774\ud2b8', dark: '\ud83c\udf19 \ub2e4\ud06c' };
    b.id = 'dt-btn'; b.type = 'button'; b.textContent = L[pref || ''];
    b.title = '\ud654\uba74 \ubaa8\ub4dc: \uc2dc\uc2a4\ud15c(\uae30\uae30 \uc124\uc815) \u2192 \ub77c\uc774\ud2b8 \u2192 \ub2e4\ud06c (\uc774 \ube0c\ub77c\uc6b0\uc800\uc5d0 \uae30\uc5b5)';
    b.setAttribute('style', 'position:fixed;right:12px;top:12px;z-index:2147483000;font:600 12px/1 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;' +
      'padding:7px 10px;border-radius:999px;border:1px solid rgba(128,128,128,.45);background:rgba(128,128,128,.18);color:inherit;cursor:pointer;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);opacity:.85');
    if (root.classList.contains('dt-inv')) b.style.filter = 'invert(1) hue-rotate(180deg)';
    b.onclick = function () {
      var nx = pref === null ? 'light' : pref === 'light' ? 'dark' : null;
      try { if (nx) { localStorage.setItem(K, nx); localStorage.setItem('semi-theme', nx); } else { localStorage.removeItem(K); localStorage.removeItem('semi-theme'); } } catch (e) {}
      location.reload();  // \ucc28\ud2b8\uac00 \ud14c\ub9c8 \uc0c9\uc744 \ub2e4\uc2dc \uc77d\ub3c4\ub85d \uc0c8\ub85c \uadf8\ub9bc
    };
    document.body.appendChild(b);
  }

  function ready() { media(); fallback(); button(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();
  window.dashTheme = { pref: function () { return pref; }, want: want };
})();
