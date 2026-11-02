/* \ub300\uc2dc\ubcf4\ub4dc \uacf5\ud1b5 \ub77c\uc774\ud2b8/\ub2e4\ud06c \uc804\ud658 (\uc0ac\uc6a9\uc790 \uc9c0\uc2dc 2026-11-03) \u2014 \ubaa8\ub4e0 \ud398\uc774\uc9c0 <head>\uc5d0 \uc790\ub3d9 \uc0bd\uc785(tools/inject_theme.py)
 * \ubc84\ud2bc: \uc6b0\uce21 \uc0c1\ub2e8 [\u2600 \ub77c\uc774\ud2b8 | \ud83c\udf19 \ub2e4\ud06c] \u2014 '\uc2dc\uc2a4\ud15c' \uc5c6\uc74c, \uc120\ud0dd\uc740 localStorage 'dash-theme'
 * \uae30\ubcf8(\uc120\ud0dd \uc804): \ud398\uc774\uc9c0 \uc6d0\ub798 \uae30\ubcf8 \u2014 \ub77c\uc774\ud2b8 \ud398\uc774\uc9c0\ub294 \ub77c\uc774\ud2b8, \uae30\uae30 \uc124\uc815\uc744 \ub530\ub974\ub358 \ud398\uc774\uc9c0\ub3c4 \ub77c\uc774\ud2b8, \uc6d0\ub798 \ub2e4\ud06c\uac00 \uae30\ubcf8\uc778 \ud398\uc774\uc9c0(\ud14c\ud06c \ubc38\ub958\uccb4\uc778 \ub4f1)\ub294 \ub2e4\ud06c
 * \uc801\uc6a9: \u2460 <html data-theme> \u2461 (prefers-color-scheme) \ubbf8\ub514\uc5b4 \uaddc\uce59\uc744 \uc120\ud0dd \ubaa8\ub4dc\ub85c \uace0\uc815
 *       \u2462 \ub77c\uc774\ud2b8 \uc804\uc6a9 \ud398\uc774\uc9c0\ub97c \ub2e4\ud06c\ub85c \u2192 \uc0c9\uc744 \ud558\ub098\ud558\ub098 \ub2e4\ud06c \ud314\ub808\ud2b8\ub85c \ubcc0\ud658(\ubc18\uc804 \uc544\ub2d8) \u00b7 \ub2e4\ud06c \uc804\uc6a9 \ud398\uc774\uc9c0\ub97c \ub77c\uc774\ud2b8\ub85c \u2192 \ubc18\uc804
 */
(function () {
  var K = 'dash-theme', root = document.documentElement, pref = null;
  try { pref = localStorage.getItem(K); } catch (e) {}
  if (pref !== 'light' && pref !== 'dark') pref = null;
  var eff = pref || 'light';  // \ubbf8\ub514\uc5b4 \uaddc\uce59 \uace0\uc815 \ubaa8\ub4dc(\uc120\ud0dd \uc804\uc5d0\ub294 \ub77c\uc774\ud2b8)

  if (pref) root.setAttribute('data-theme', pref);

  var ON = '(min-width: 0px)', OFF = '(max-width: -1px)';
  function walkMedia(list, cb) {
    for (var i = 0; i < list.length; i++) {
      var r = list[i];
      if (r.media && r.cssRules && /prefers-color-scheme/.test(r.media.mediaText)) cb(r);
      else if (r.cssRules) { try { walkMedia(r.cssRules, cb); } catch (e) {} }
    }
  }
  function media() {
    for (var s = 0; s < document.styleSheets.length; s++) {
      var list; try { list = document.styleSheets[s].cssRules; } catch (e) { continue; }
      walkMedia(list, function (r) {
        var t = r.media.mediaText;
        var n = t.replace(/\(\s*prefers-color-scheme\s*:\s*(dark|light)\s*\)/g, function (_, m) { return m === eff ? ON : OFF; });
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

  // \u2462 \ub2e4\ud06c \ud314\ub808\ud2b8 \ubcc0\ud658 \u2014 \ubc1d\uc740 \ubc30\uacbd \u2192 \uc9d9\uc740 \ub0a8\uc0c9 \u00b7 \uc5b4\ub450\uc6b4 \uae00\uc790 \u2192 \ud68c\ubc31\uc0c9 \u00b7 \uc5f0\ud55c \ud14c\ub450\ub9ac \u2192 \uc5b4\ub450\uc6b4 \ud68c\uc0c9 \u00b7 \uac15\uc870\uc0c9\uc740 \uc0c9\uc0c1 \uc720\uc9c0\u00b7\ubc1d\uae30\ub9cc \uc870\uc815
  function hsl(r, g, b) { r /= 255; g /= 255; b /= 255; var mx = Math.max(r, g, b), mn = Math.min(r, g, b), h = 0, s = 0, l = (mx + mn) / 2, d = mx - mn;
    if (d) { s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn); h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h /= 6; } return [h, s, l]; }
  function rgbOf(h, s, l) { function f(p, q, t) { if (t < 0) t += 1; if (t > 1) t -= 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; }
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
    return rgbOf(h, s, Math.min(0.97, l));
  }
  function recolor(v, kind) { return v.replace(CRE, function (m, hx, r, g, b, a, nm) { var c = parse(m, hx, r, g, b, a, nm), o = conv(c, kind);
    return c[3] < 1 ? 'rgba(' + o.join(',') + ',' + (+c[3].toFixed(3)) + ')' : 'rgb(' + o.join(',') + ')'; }); }
  function svgKind(v) { CRE.lastIndex = 0; var m = CRE.exec(v); CRE.lastIndex = 0; if (!m) return null; var c = parse.apply(null, m), l = hsl(c[0], c[1], c[2])[2]; return l > 0.82 ? 'bg' : l < 0.45 ? 'fg' : null; }
  var PK = { 'color': 'fg', 'background': 'bg', 'background-color': 'bg', 'background-image': 'bg', 'border-color': 'bd', 'border': 'bd', 'border-top': 'bd', 'border-bottom': 'bd', 'border-left': 'bd', 'border-right': 'bd',
    'border-top-color': 'bd', 'border-bottom-color': 'bd', 'border-left-color': 'bd', 'border-right-color': 'bd', 'outline': 'bd', 'outline-color': 'bd', 'box-shadow': 'bd', 'text-decoration-color': 'fg', 'caret-color': 'fg', 'fill': 'svg', 'stroke': 'svg', 'column-rule-color': 'bd' };
  function hasColor(v) { CRE.lastIndex = 0; var t = CRE.test(v); CRE.lastIndex = 0; return t; }
  function fixDecl(st) {
    for (var i = 0; i < st.length; i++) {
      var pn = st[i], k = PK[pn]; if (!k && /^--/.test(pn)) k = 'var'; if (!k) continue;
      var v = st.getPropertyValue(pn); if (!v || !hasColor(v)) continue;
      var kk = k === 'svg' ? svgKind(v) : k === 'var' ? (/bg|back|card|panel|surface|paper|base|fill|bar|row|head|band|box/i.test(pn) ? 'bg' : /line|border|grid|rule|sep|divid/i.test(pn) ? 'bd' : 'fg') : k;
      if (!kk) continue; var nv = recolor(v, kk); if (nv !== v) st.setProperty(pn, nv, st.getPropertyPriority(pn));
    }
  }
  function walkStyle(list) { for (var i = 0; i < list.length; i++) { var r = list[i]; if (r.__dk) continue; r.__dk = 1; if (r.style) fixDecl(r.style); if (r.cssRules) try { walkStyle(r.cssRules); } catch (e) {} } }
  function sheets() { for (var s = 0; s < document.styleSheets.length; s++) { var ss = document.styleSheets[s]; if (ss.ownerNode && ss.ownerNode.id === 'dt-dark') continue; var list; try { list = ss.cssRules; } catch (e) { continue; } walkStyle(list); } }
  function attrs(el) {
    if (el.nodeType !== 1 || el.__dk || (el.closest && el.closest('#dt-btn'))) return; el.__dk = 1;
    if (el.style && el.style.length) fixDecl(el.style);
    ['fill', 'stroke', 'color', 'bgcolor', 'stop-color'].forEach(function (a) {
      var v = el.getAttribute && el.getAttribute(a); if (!v || !hasColor(v)) return;
      var k = a === 'bgcolor' ? 'bg' : a === 'color' ? 'fg' : svgKind(v); if (k) el.setAttribute(a, recolor(v, k));
    });
  }
  function tree(n) { attrs(n); if (n.querySelectorAll) { var a = n.querySelectorAll('[style],[fill],[stroke],[bgcolor],[color],[stop-color]'); for (var i = 0; i < a.length; i++) attrs(a[i]); } }
  function darken() {
    root.classList.add('dt-dark');
    var st = document.createElement('style'); st.id = 'dt-dark';
    st.textContent = 'html.dt-dark{background:#0d131d;color-scheme:dark}html.dt-dark body{background-color:#0d131d;color:#dfe6ee}' +
      'html.dt-dark a{color:#8ab4ff}html.dt-dark canvas{filter:invert(.92) hue-rotate(180deg) saturate(1.1)}' +
      'html.dt-dark input,html.dt-dark select,html.dt-dark textarea,html.dt-dark button:not(.dt-b){background-color:#1a2333;color:#dfe6ee;border-color:#334055}';
    document.head.appendChild(st);
    sheets(); tree(document.body);
    var pend = false, q = [];
    new MutationObserver(function (ms) {
      ms.forEach(function (m) { if (m.type === 'attributes') { m.target.__dk = 0; q.push(m.target); } else m.addedNodes.forEach(function (n) { q.push(n); }); });
      if (!pend) { pend = true; requestAnimationFrame(function () { pend = false; var a = q; q = []; a.forEach(tree); sheets(); }); }
    }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'fill', 'stroke'] });
  }
  function fallback() {
    if (!pref || !document.body) return;
    var l = lum(document.body); if (l == null) l = lum(root); if (l == null) l = 1;  // \ubc30\uacbd \ubbf8\uc9c0\uc815 = \ube0c\ub77c\uc6b0\uc800 \uae30\ubcf8 \ud770\uc0c9
    if (pref === 'dark' && l > 0.5) { darken(); return; }
    if (pref === 'light' && l < 0.5) {  // \ub2e4\ud06c \uc804\uc6a9 \ud398\uc774\uc9c0 \u2192 \ub77c\uc774\ud2b8: \ubc18\uc804(\ub4dc\ubb3e)
      var st = document.createElement('style');
      st.textContent = 'html.dt-inv{filter:invert(1) hue-rotate(180deg);background:#000}html.dt-inv img,html.dt-inv video,html.dt-inv picture,html.dt-inv iframe,html.dt-inv [style*="background-image"]{filter:invert(1) hue-rotate(180deg)}html.dt-inv #dt-btn{filter:invert(1) hue-rotate(180deg)}';
      document.head.appendChild(st); root.classList.add('dt-inv');
    }
  }

  // \ubc84\ud2bc: \uc6b0\uce21 \uc0c1\ub2e8 [\u2600 \ub77c\uc774\ud2b8 | \ud83c\udf19 \ub2e4\ud06c] \u2014 \ud604\uc7ac \ubaa8\ub4dc \uac15\uc870, \ub204\ub974\uba74 \uadf8 \ubaa8\ub4dc\ub85c(\uc0c8\ub85c\uace0\uce68\ud574 \ucc28\ud2b8 \uc0c9\uae4c\uc9c0 \ubc18\uc601)
  function button() {
    if (document.getElementById('dt-btn') || document.getElementById('thm')) return;  // \uc790\uccb4 \uc804\ud658 \ubc84\ud2bc\uc774 \uc788\ub294 \ud398\uc774\uc9c0(\ud14c\ud06c \ubc38\ub958\uccb4\uc778\u00b7\ubbf8\uad6d \uce98\ub9b0\ub354)\ub294 \uadf8 \ubc84\ud2bc \uc0ac\uc6a9(\uac19\uc740 \uc124\uc815 \uacf5\uc720)
    var cur = pref; if (!cur) { var l = lum(document.body); if (l == null) l = lum(root); cur = l != null && l < 0.5 ? 'dark' : 'light'; }
    var w = document.createElement('div'); w.id = 'dt-btn';
    w.setAttribute('style', 'position:fixed;right:12px;top:12px;z-index:2147483000;display:flex;gap:2px;padding:3px;border-radius:999px;border:1px solid rgba(128,128,128,.45);background:rgba(128,128,128,.16);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)');
    [['light', '\u2600 \ub77c\uc774\ud2b8'], ['dark', '\ud83c\udf19 \ub2e4\ud06c']].forEach(function (o) {
      var b = document.createElement('button'); b.type = 'button'; b.className = 'dt-b'; b.textContent = o[1];
      var on = o[0] === cur;
      b.setAttribute('style', 'font:600 12px/1 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;padding:6px 10px;border:0;border-radius:999px;cursor:pointer;' +
        (on ? 'background:#3d6fd8;color:#fff' : 'background:transparent;color:inherit;opacity:.75'));
      b.onclick = function () { if (o[0] === cur) return; try { localStorage.setItem(K, o[0]); localStorage.setItem('semi-theme', o[0]); } catch (e) {} location.reload(); };
      w.appendChild(b);
    });
    document.body.appendChild(w);
  }

  function ready() { media(); fallback(); button(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();
})();
