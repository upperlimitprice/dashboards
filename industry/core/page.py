"""페이지 모델(dict) → 단일 HTML 파일. 각 페이지 모듈은 build() 에서 이 헬퍼로 내용을 채운다.

page = {key, title, subtitle, updated, status, errors[], kpis[], charts[], tables[], sources[], notes[]}
chart = {id, title, kind(line|bar|area), x[], series[{name, data[], kind?, slot?}], unit, stack, note}
  · slot: 팔레트 고정 번호(0~7). 같은 대상은 모든 차트에서 같은 색. -1 = 회색(기타).
"""
import html
import json
from datetime import datetime

from .env import ROOT

TEMPLATES = ROOT / "templates"


def new(key, title, subtitle=""):
    return {"key": key, "title": title, "subtitle": subtitle,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "status": "ok",
            "errors": [], "kpis": [], "charts": [], "tables": [], "sources": [], "notes": []}


def kpi(page, label, value, unit="", delta=None, delta_label="YoY", digits=1, asof=None, delta_unit="%"):
    page["kpis"].append({
        "label": label, "value": None if value is None else round(value, digits), "unit": unit,
        "delta": None if delta is None else round(delta, 1), "delta_label": delta_label,
        "delta_unit": delta_unit, "asof": asof})


def series(name, data, kind=None, slot=None):
    s = {"name": name, "data": data}
    if kind:
        s["kind"] = kind
    if slot is not None:
        s["slot"] = slot
    return s


def chart(page, cid, title, x, series_list, kind="line", unit="", stack=False, note="", window=None):
    """window: 처음 보여줄 최근 구간 길이(포인트 수). 이전 구간은 확대/축소로 탐색."""
    series_list = [s for s in series_list if any(v is not None for v in s["data"])]
    if not x or not series_list:
        return
    page["charts"].append({"id": cid, "title": title, "kind": kind, "x": list(x),
                           "series": series_list, "unit": unit, "stack": stack,
                           "note": note, "window": window})


def table(page, title, columns, rows, note=""):
    if rows:
        page["tables"].append({"title": title, "columns": columns, "rows": rows, "note": note})


def source(page, name, url):
    page["sources"].append({"name": name, "url": url})


def error(page, msg):
    page["errors"].append(msg)
    page["status"] = "partial" if page["kpis"] or page["charts"] else "error"


def _embed(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render(page):
    tpl = (TEMPLATES / "page.html").read_text(encoding="utf-8")
    return (tpl.replace("__TITLE__", html.escape(page["title"]))
               .replace("__DATA__", _embed(page)))


def render_hub(cards):
    tpl = (TEMPLATES / "hub.html").read_text(encoding="utf-8")
    return tpl.replace("__DATA__", _embed(cards))
