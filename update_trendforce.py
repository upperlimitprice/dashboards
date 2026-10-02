#!/usr/bin/env python3
"""트렌드포스 가격 전망 트래커(trendforce.html) 수집 스크립트.

TrendForce 보도자료(presscenter)에서 메모리 계약가 QoQ 전망 범위를 뽑아
trendforce.html 안의 <script id='tfd'> JSON(src·f 배열)에 추가한다. 표준 라이브러리만 사용.

사용법:
  python update_trendforce.py                      # 보도자료 목록 스캔 → 후보 추출 → trendforce/pending.json 저장 (HTML 미수정)
  python update_trendforce.py --apply              # 후보를 trendforce.html에 바로 반영
  python update_trendforce.py --apply --commit     # 반영 후 git add/commit/push
  python update_trendforce.py --url URL [URL ...]  # 특정 보도자료만 파싱
  python update_trendforce.py --html 저장파일.html --date 2026-09-30 --url 원문URL   # 저장해 둔 HTML 파싱(오프라인)
  python update_trendforce.py --apply-pending      # 검토(불필요 항목 삭제)한 pending.json을 HTML에 반영
  python update_trendforce.py --since 2026-07-01 --pages 3 --dry-run

동작:
  1) 보도자료 목록 페이지에서 /presscenter/news/YYYYMMDD-NNNNN.html 링크 수집 (제목에 메모리 가격 키워드가 있는 것만)
  2) 본문 문장별로 [품목 키워드] + [분기 토큰] + [% 범위] + [상승/하락 동사]를 찾아 레코드 생성
     품목: 범용/전체 DRAM·PC·서버·모바일·그래픽·컨슈머 DRAM / NAND·eSSD·cSSD·eMMC·UFS·웨이퍼
  3) 기존 레코드와 비교해 신규만 추가. 같은 품목·분기에 기존 전망이 있으면 '수정(r)', 매출 보도자료의 과거형이면 '실적(a)'
  4) 원문 직접 파싱이므로 u(2차 출처) 플래그는 붙이지 않음. 같은 품목·분기·범위의 2차 레코드가 있으면 원문 레코드로 교체.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "trendforce.html"
PENDING = ROOT / "trendforce" / "pending.json"
LIST_URLS = [
    "https://www.trendforce.com/presscenter/news",
    "https://www.trendforce.com/presscenter/news?page={page}",
    "https://www.trendforce.com/presscenter/news/page/{page}",
]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}

# 제목 필터 — 메모리 가격 관련 보도자료만
TITLE_KW = re.compile(r"DRAM|NAND|Memory Price|Contract Price|SSD|eMMC|UFS|HBM|Memory Contract|Wafer", re.I)
TITLE_SKIP = re.compile(r"Foundry|Panel|LED|MLCC|Smartphone Production|Notebook Shipment|Server Shipment|Wafer Fab|Automotive|Display", re.I)

# 품목 키워드 (앞에 있는 것이 우선 매칭)
ITEM_PAT = [
    ("dram_all", r"(?:including|incl\.?|with) HBM|overall DRAM(?: prices| pricing| contract)|DRAM (?:prices |pricing )?including HBM|total DRAM|blended DRAM"),
    ("essd", r"enterprise[- ]SSD|eSSD"),
    ("cssd", r"(?:PC[- ])?client[- ]SSD|cSSD|PC OEM SSD"),
    ("emmc", r"\beMMC\b"),
    ("ufs", r"\bUFS\b"),
    ("wafer", r"(?:NAND(?: Flash)? )?wafers?\b"),
    ("nand", r"NAND(?: Flash)?(?: contract)?(?: prices| pricing| price)?|NAND Flash overall|overall NAND"),
    ("pc", r"PC DRAM|PC memory|DDR5 (?:PC|module)"),
    ("server", r"server DRAM|server DDR[45]|server memory"),
    ("mobile", r"mobile DRAM|LPDDR[45]X?|LPDDR"),
    ("gfx", r"graphics DRAM|graphic DRAM|GDDR[67]X?"),
    ("cons", r"consumer DRAM|consumer DDR[2-4]|DDR[23]\b"),
    ("dram_conv", r"conventional DRAM|commodity DRAM|general DRAM|\bDRAM\b"),
]
ITEM_RE = [(k, re.compile(p, re.I)) for k, p in ITEM_PAT]
ITEM_KO = {"dram_conv": "범용 DRAM", "dram_all": "DRAM 전체(HBM 포함)", "pc": "PC DRAM", "server": "서버 DRAM", "mobile": "모바일 DRAM",
           "gfx": "그래픽 DRAM", "cons": "컨슈머 DRAM", "nand": "NAND 전체", "essd": "엔터프라이즈 SSD", "cssd": "클라이언트 SSD",
           "emmc": "eMMC", "ufs": "UFS", "wafer": "NAND 웨이퍼"}

Q_RE = re.compile(r"\b([1-4])Q(\d{2})\b|\bQ([1-4])\s+(?:of\s+)?(?:20)?(\d{2})\b|\b(first|second|third|fourth)\s+quarter(?:\s+of)?\s+(?:20)?(\d{2})\b", re.I)
Q_BARE = re.compile(r"\bQ([1-4])\b|\b([1-4])Q\b|\b(first|second|third|fourth)[- ]quarter\b", re.I)
QWORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}
RANGE_RE = re.compile(r"(?<![\d.])(\d{1,3})\s*%?\s*(?:–|-|~|—|to)\s*(\d{1,3})\s*%(?!\s*[–\-~]\s*\d)")
SINGLE_RE = re.compile(r"(?:over|more than|above|around|approximately|about|nearly|up to|at least)?\s*(?<![\d.])(\d{1,3})\s*%(?!\s*[–\-~]|\s*to\s*\d)")
FLAT_RE = re.compile(r"\b(flat|stable|unchanged|steady|remain(?:s|ed)? (?:roughly |largely |mostly )?(?:flat|stable|unchanged)|hold(?:s|ing)? steady|hold flat)\b", re.I)
DOWN_RE = re.compile(r"\b(declin\w*|drop\w*|fall\w*|fell|decreas\w*|down\w*|lower|contract\w* by|slide|slip\w*|retreat\w*|dip\w*)\b", re.I)
UP_RE = re.compile(r"\b(ris\w*|rose|increas\w*|grow\w*|grew|climb\w*|surg\w*|jump\w*|hike\w*|up\b|higher|gain\w*|expand\w*|soar\w*)\b", re.I)
PAST_RE = re.compile(r"\b(rose|increased|grew|climbed|jumped|surged|fell|dropped|declined|reached|hit|recorded|posted)\b", re.I)
FCST_RE = re.compile(r"\b(expect\w*|project\w*|forecast\w*|estimat\w*|anticipat\w*|predict\w*|will|likely|poised|set to|outlook|revis\w*|upgrad\w*)\b", re.I)
PRICE_RE = re.compile(r"\b(price|prices|pricing|ASP|contract)\b", re.I)
NOISE_RE = re.compile(r"\b(revenue|market share|bit shipments?|bit output|capacity|capex|wafer input|sufficiency|penetration|ranking)\b", re.I)


# ── HTML → 텍스트 ──────────────────────────────────────────────────────────────
class _Text(HTMLParser):
    """본문 텍스트 추출. 제목(<title>/<h1>)과 문단을 모은다."""
    SKIP = {"script", "style", "nav", "footer", "header", "noscript"}

    def __init__(self):
        super().__init__()
        self.parts, self.title, self._skip, self._tag = [], "", 0, ""
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        if tag in ("p", "li", "br", "div", "h1", "h2", "h3", "tr", "td"):
            self._flush()
        self._tag = tag

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in ("p", "li", "div", "h1", "h2", "h3", "tr"):
            self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        if self._tag == "title" and not self.title:
            self.title = unescape(data).strip()
        self._buf.append(data)

    def _flush(self):
        t = unescape(" ".join(self._buf)).strip()
        self._buf = []
        if t:
            self.parts.append(re.sub(r"\s+", " ", t))


def html_to_text(html):
    p = _Text()
    p.feed(html)
    p._flush()
    title = re.sub(r"\s*[|｜-]\s*TrendForce.*$", "", p.title).strip()
    body = "\n".join(p.parts)
    return title, body


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ── 보도자료 목록 ─────────────────────────────────────────────────────────────
LINK_RE = re.compile(r"/presscenter/news/(\d{8})-(\d+)\.html")


def list_releases(pages=2, since=None):
    """[(date, url)] — 목록 페이지에서 링크 수집. 어떤 URL 패턴이 살아있는지 모르므로 차례로 시도."""
    found = {}
    for page in range(1, pages + 1):
        for pat in LIST_URLS:
            if page > 1 and "{page}" not in pat:
                continue
            if page == 1 and "{page}" in pat:
                continue
            url = pat.format(page=page)
            try:
                html = fetch(url)
            except Exception as e:  # noqa: BLE001
                print(f"  목록 실패 {url}: {e}", file=sys.stderr)
                continue
            n = 0
            for m in LINK_RE.finditer(html):
                d = m.group(1)
                dd = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                if since and dd < since:
                    continue
                u = f"https://www.trendforce.com/presscenter/news/{d}-{m.group(2)}.html"
                found[u] = dd
                n += 1
            if n:
                break
    return sorted(((d, u) for u, d in found.items()), reverse=True)


# ── 문장 → 레코드 ─────────────────────────────────────────────────────────────
def pub_quarter(pub):
    y, m = int(pub[:4]), int(pub[5:7])
    return y, (m - 1) // 3 + 1


def norm_q(m, pub, is_actual):
    if m.group(1):
        return f"{m.group(1)}Q{m.group(2)}"
    if m.group(3):
        return f"{m.group(3)}Q{m.group(4)[-2:]}"
    return f"{QWORD[m.group(5).lower()]}Q{m.group(6)[-2:]}"


def bare_q(m, pub, is_actual):
    q = int(m.group(1) or m.group(2) or QWORD[m.group(3).lower()])
    y, pq = pub_quarter(pub)
    if q < pq and not is_actual:
        y += 1
    return f"{q}Q{str(y)[-2:]}"


def split_sentences(text):
    """(문장, 문단에 가격 단어 있음) — 'Including HBM, ... 15% to 20%'처럼 문장엔 price가 없어도 문단 맥락으로 허용."""
    for para in text.split("\n"):
        pp = bool(PRICE_RE.search(para))
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"(])", para):
            s = s.strip()
            if len(s) > 25:
                yield s, pp


def extract(text, title, pub):
    """본문에서 후보 레코드 추출. 반환: [{item,q,lo,hi,k,note,ev}]"""
    out = []
    is_rev_release = bool(re.search(r"revenue", title, re.I))
    ctx_q = None  # 제목 분기 (문장에 분기가 없을 때 사용)
    mt = Q_RE.search(title)
    if mt:
        ctx_q = norm_q(mt, pub, is_rev_release)
    for s, para_price in split_sentences(text):
        if not (PRICE_RE.search(s) or (para_price and re.search(r"QoQ|quarter|increase|decline", s, re.I))):
            continue
        if NOISE_RE.search(s) and not re.search(r"contract price|ASP", s, re.I):
            continue
        if not (RANGE_RE.search(s) or FLAT_RE.search(s) or SINGLE_RE.search(s)):
            continue
        is_actual = bool(PAST_RE.search(s)) and not FCST_RE.search(s)
        # 분기
        qs = [(m.start(), norm_q(m, pub, is_actual)) for m in Q_RE.finditer(s)]
        if not qs:
            qb = [(m.start(), bare_q(m, pub, is_actual)) for m in Q_BARE.finditer(s)]
            qs = qb or ([(0, ctx_q)] if ctx_q else [])
        if not qs:
            continue
        # 품목 위치
        items = []
        taken = []
        has_all = bool(ITEM_RE[0][1].search(s))
        for key, rx in ITEM_RE:
            for m in rx.finditer(s):
                if any(a <= m.start() < b for a, b in taken):
                    continue
                if key == "dram_conv" and has_all and m.group(0).strip().upper() == "DRAM":
                    continue  # "Including HBM, the broader DRAM increase ..." 의 맨 DRAM은 HBM 포함 전체를 가리킴
                taken.append((m.start(), m.end()))
                items.append((m.start(), key, m.end()))
        if not items:
            continue
        items.sort()
        # % 범위 위치
        pcts = []
        for m in RANGE_RE.finditer(s):
            pcts.append((m.start(), int(m.group(1)), int(m.group(2)), m.group(0)))
        covered = [(p[0], p[0] + len(p[3])) for p in pcts]
        for m in SINGLE_RE.finditer(s):
            if any(a <= m.start(1) < b for a, b in covered):
                continue
            v = int(m.group(1))
            pcts.append((m.start(1), v, v, m.group(0).strip()))
        for m in FLAT_RE.finditer(s):
            pcts.append((m.start(), 0, 0, m.group(0)))
        if not pcts:
            continue
        pcts.sort()
        for pos, lo, hi, raw in pcts:
            # 가장 가까운 선행 품목(없으면 후행)
            prev = [i for i in items if i[0] <= pos]
            keys = [(prev[-1] if prev else items[0])[1]]
            # "eMMC and UFS", "DDR4/DDR5" 처럼 접속사로 묶인 선행 품목은 같은 수치 공유
            j = len(prev) - 1
            while j > 0:
                between = s[prev[j - 1][2]:prev[j][0]]  # 앞 품목 끝 ~ 뒤 품목 시작
                if re.fullmatch(r"\s*(?:,?\s*and|or|/|&|,)\s*(?:the\s+)?", between):
                    keys.insert(0, prev[j - 1][1])
                    j -= 1
                else:
                    break
            key = keys[0]
            # 가장 가까운 선행 분기
            qprev = [q for q in qs if q[0] <= pos]
            q = (qprev[-1] if qprev else qs[0])[1]
            # 방향: 해당 %와 품목 사이 구간의 동사
            lo_i = min(pos, (prev[-1] if prev else items[0])[0])
            seg = s[max(0, lo_i - 40): pos + len(raw) + 40]
            if lo == hi == 0:
                pass
            elif DOWN_RE.search(seg) and not UP_RE.search(seg):
                lo, hi = -hi, -lo
            elif DOWN_RE.search(seg) and UP_RE.search(seg):
                # 둘 다 있으면 %에 더 가까운 동사
                d = min((abs(m.start() - (pos - max(0, lo_i - 40))) for m in DOWN_RE.finditer(seg)), default=999)
                u = min((abs(m.start() - (pos - max(0, lo_i - 40))) for m in UP_RE.finditer(seg)), default=999)
                if d < u:
                    lo, hi = -hi, -lo
            if hi - lo > 40 and not (lo == hi):
                continue  # 비정상 범위
            if abs(lo) > 300:
                continue
            k = "a" if (is_actual or (is_rev_release and not FCST_RE.search(s))) else "f"
            note = ""
            if re.search(r"over|more than|above|at least", raw, re.I):
                note = raw.strip() + " 이상"
            for key in keys:
                out.append({"item": key, "q": q, "lo": lo, "hi": hi, "k": k, "note": note, "ev": s})
    # 같은 (item,q) 중복: 범위형(lo<hi) 우선, 그다음 먼저 나온 것
    best = {}
    for r in out:
        kk = (r["item"], r["q"], r["k"])
        if kk not in best or (best[kk]["lo"] == best[kk]["hi"] and r["lo"] < r["hi"]):
            best[kk] = r
    return list(best.values())


# ── trendforce.html JSON 입출력 ──────────────────────────────────────────────
BLOCK_RE = re.compile(r"(<script id='tfd' type='application/json'>\n)(.*?)(\n</script>)", re.S)


def load_data():
    html = HTML.read_text(encoding="utf-8")
    m = BLOCK_RE.search(html)
    if not m:
        sys.exit("trendforce.html에서 tfd JSON 블록을 찾지 못함")
    return html, m, json.loads(m.group(2))


def dump_data(d):
    """원본 스타일 유지: items·src·f는 한 줄에 하나, f는 분기별 묶음."""
    j = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    lines = ["{", '"items":[']
    lines.append(",\n".join(" " + j(i) for i in d["items"]))
    lines.append("],")
    lines.append('"quarters":' + j(d["quarters"]) + ",")
    if "meta" in d:
        lines.append('"meta":' + j(d["meta"]) + ",")
    lines.append('"src":{')
    lines.append(",\n".join(f" {j(k)}:{j(v)}" for k, v in sorted(d["src"].items())))
    lines.append("},")
    lines.append('"f":[')
    qorder = {q: i for i, q in enumerate(d["quarters"])}
    recs = sorted(d["f"], key=lambda r: (qorder.get(r[1], 99), 0))  # 분기 순, 안정 정렬로 입력 순서 유지
    groups, cur = [], None
    for r in recs:
        if r[1] != cur:
            groups.append([])
            cur = r[1]
        groups[-1].append(" " + j(r))
    lines.append(",\n\n".join(",\n".join(g) for g in groups))
    lines.append("],")
    lines.append('"other":' + json.dumps(d["other"], ensure_ascii=False, indent=1))
    lines.append("}")
    return "\n".join(lines)


def save_data(html, m, d, today):
    new = m.group(1) + dump_data(d) + m.group(3)
    html = html[:m.start()] + new + html[m.end():]
    html = re.sub(r"기준 \d{4}-\d{2}-\d{2}", f"기준 {today}", html, count=1)
    HTML.write_text(html, encoding="utf-8")


def src_key(pub, src):
    k = pub[2:4] + pub[5:7] + pub[8:10]
    base = k
    i = 0
    while k in src:
        i += 1
        k = base + "bcdefg"[i - 1]
    return k


def merge(d, releases, today):
    """releases: [{date,url,title,recs}] → d 갱신. 반환: 추가된 레코드 목록."""
    added = []
    if any(q not in d["quarters"] for rel in releases for q in {r["q"] for r in rel["recs"]}):
        for rel in releases:
            for r in rel["recs"]:
                if r["q"] not in d["quarters"] and re.fullmatch(r"[1-4]Q\d{2}", r["q"]):
                    d["quarters"].append(r["q"])
        d["quarters"].sort(key=lambda q: (q[2:], q[0]))
    for rel in releases:
        if not rel["recs"]:
            continue
        # 같은 URL이 이미 src에 있으면 그 키 재사용
        key = next((k for k, v in d["src"].items() if v[2] == rel["url"]), None) or src_key(rel["date"], d["src"])
        d["src"].setdefault(key, [rel["date"], rel["title"], rel["url"]])
        for r in rel["recs"]:
            same = [x for x in d["f"] if x[0] == r["item"] and x[1] == r["q"]]
            # 2차 출처(u) 레코드와 같은 범위면 원문 레코드로 교체 (출처 키 갱신 + u 제거)
            dup2 = [x for x in same if x[2] == r["lo"] and x[3] == r["hi"] and len(x) > 7 and x[7]]
            if dup2:
                x = dup2[0]
                x[5] = key
                del x[7:]
                added.append(("교체", r, key))
                continue
            # 완전 중복
            if any(x[2] == r["lo"] and x[3] == r["hi"] and x[5] == key for x in same):
                continue
            if any(x[2] == r["lo"] and x[3] == r["hi"] for x in same):
                continue
            kind = r["k"]
            if kind == "f" and any(x[4] in ("f", "r") for x in same):
                kind = "r"
            rec = [r["item"], r["q"], r["lo"], r["hi"], kind, key, r["note"]]
            d["f"].append(rec)
            added.append(("추가", r, key))
    d.setdefault("meta", {})
    d["meta"]["updated"] = today
    d["meta"]["collector"] = "update_trendforce.py"
    return added


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", nargs="*", help="특정 보도자료 URL만 파싱")
    ap.add_argument("--html", help="저장된 보도자료 HTML 파일 파싱 (--date 필요)")
    ap.add_argument("--date", help="--html 사용 시 발표일 YYYY-MM-DD")
    ap.add_argument("--since", help="이 날짜 이후 보도자료만 (기본: 기존 src 최신일)")
    ap.add_argument("--pages", type=int, default=2, help="목록 페이지 수 (기본 2)")
    ap.add_argument("--apply", action="store_true", help="trendforce.html에 바로 반영")
    ap.add_argument("--apply-pending", action="store_true", help="pending.json(검토본)을 반영")
    ap.add_argument("--commit", action="store_true", help="반영 후 git add/commit/push")
    ap.add_argument("--dry-run", action="store_true", help="후보만 출력, 파일 미생성")
    a = ap.parse_args()
    today = date.today().isoformat()
    html, m, d = load_data()

    if a.apply_pending:
        releases = json.loads(PENDING.read_text(encoding="utf-8"))
    else:
        since = a.since or max(v[0] for v in d["src"].values())
        targets = []
        if a.html:
            if not a.date:
                sys.exit("--html 에는 --date YYYY-MM-DD 가 필요")
            targets.append((a.date, a.url[0] if a.url else f"file://{a.html}", Path(a.html).read_text(encoding="utf-8", errors="replace")))
        elif a.url:
            for u in a.url:
                mm = LINK_RE.search(u)
                dd = f"{mm.group(1)[:4]}-{mm.group(1)[4:6]}-{mm.group(1)[6:]}" if mm else today
                targets.append((dd, u, None))
        else:
            print(f"보도자료 목록 스캔 (since {since}, {a.pages}페이지)")
            known = {v[2] for v in d["src"].values()}
            for dd, u in list_releases(a.pages, since):
                if u not in known:
                    targets.append((dd, u, None))
            print(f"  신규 후보 {len(targets)}건")
        releases = []
        for dd, u, raw in targets:
            try:
                raw = raw if raw is not None else fetch(u)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                print(f"  실패 {u}: {e}", file=sys.stderr)
                continue
            title, body = html_to_text(raw)
            if not a.html and not a.url and (not TITLE_KW.search(title) or TITLE_SKIP.search(title)):
                continue
            recs = extract(body, title, dd)
            releases.append({"date": dd, "url": u, "title": title, "recs": recs})
            print(f"\n[{dd}] {title}\n  {u}")
            for r in recs:
                sign = "+" if r["lo"] > 0 else ""
                print(f"   {r['q']:>4} {ITEM_KO[r['item']]:<14} {sign}{r['lo']}~{sign if r['hi']>0 else ''}{r['hi']}%  ({'실적' if r['k']=='a' else '전망'})  ← {r['ev'][:110]}")
            if not recs:
                print("   (수치 범위 없음)")

    if a.dry_run:
        return
    if not (a.apply or a.apply_pending):
        PENDING.parent.mkdir(exist_ok=True)
        PENDING.write_text(json.dumps(releases, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n후보를 {PENDING.relative_to(ROOT)} 에 저장 — 검토 후 `--apply-pending`, 또는 바로 `--apply`")
        return

    added = merge(d, releases, today)
    if not added:
        print("\n추가할 신규 레코드 없음")
        return
    save_data(html, m, d, today)
    for how, r, key in added:
        print(f"  {how}: {r['q']} {ITEM_KO[r['item']]} {r['lo']}~{r['hi']}% [{key}]")
    print(f"\ntrendforce.html 갱신 — {len(added)}건 (기준 {today})")
    if a.commit:
        subprocess.run(["git", "-C", str(ROOT), "add", "trendforce.html"], check=True)
        subprocess.run(["git", "-C", str(ROOT), "commit", "-qm", f"trendforce {today}"], check=False)
        subprocess.run(["git", "-C", str(ROOT), "push", "-q"], check=False)
        print("git push 완료")


if __name__ == "__main__":
    main()
