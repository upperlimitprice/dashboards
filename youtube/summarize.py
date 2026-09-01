"""자막 → 구조화 요약 JSON (Claude API).

  pip install anthropic
  export ANTHROPIC_API_KEY=...   (또는 `ant auth login`)

사용:
  python youtube/summarize.py                     # transcripts/ 중 요약 없는 것 전부
  python youtube/summarize.py --channel infomkt   # 채널 한정
  python youtube/summarize.py --force youtube/transcripts/infomkt/2026-09-01_XXXX.txt

입력:  youtube/transcripts/<ch>/<date>_<id>.txt (+ .json 메타)
출력:  youtube/summaries/<ch>/<date>_<id>.json   ← 커밋 대상 (원문 아님)

API 없이 수동으로 할 때는 SCHEMA 와 동일한 형태로 JSON 을 써서 summaries/ 에 넣으면
build.py 가 똑같이 페이지를 만든다 (Claude Code 세션에 자막 붙여넣고 요청해도 됨).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TR, SM = ROOT / "transcripts", ROOT / "summaries"
CHANNELS = json.loads((ROOT / "channels.json").read_text(encoding="utf-8"))
MODEL = "claude-opus-5"

# build.py 가 그대로 렌더링하는 요약 스키마 — 필드 추가/삭제 시 build.py 도 맞춘다
SCHEMA = {
    "type": "object",
    "properties": {
        "one_liner": {"type": "string", "description": "영상 전체를 한 문장으로 (60자 내외)"},
        "stance": {"type": "string", "enum": ["bullish", "bearish", "neutral", "mixed"],
                   "description": "시장/주제에 대한 화자의 전반적 톤"},
        "key_points": {"type": "array", "items": {"type": "string"},
                       "description": "핵심 메시지 5~8개, 각 1~2문장, 수치 포함"},
        "sections": {"type": "array", "items": {"type": "object", "properties": {
            "t": {"type": "string", "description": "시작 타임스탬프 mm:ss"},
            "title": {"type": "string"},
            "body": {"type": "string", "description": "3~6문장 요약"}},
            "required": ["t", "title", "body"], "additionalProperties": False},
            "description": "영상 흐름대로 4~10개 구간"},
        "tickers": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "code": {"type": "string", "description": "종목코드/티커, 모르면 빈 문자열"},
            "view": {"type": "string", "enum": ["positive", "negative", "neutral", "watch"]},
            "note": {"type": "string", "description": "언급 맥락 1문장"}},
            "required": ["name", "code", "view", "note"], "additionalProperties": False},
            "description": "언급된 종목·ETF·지수"},
        "themes": {"type": "array", "items": {"type": "string"}, "description": "섹터/테마 키워드"},
        "numbers": {"type": "array", "items": {"type": "object", "properties": {
            "label": {"type": "string"}, "value": {"type": "string"}, "context": {"type": "string"}},
            "required": ["label", "value", "context"], "additionalProperties": False},
            "description": "언급된 구체 수치·레벨·목표치"},
        "checkpoints": {"type": "array", "items": {"type": "string"},
                        "description": "투자 관점에서 앞으로 확인해야 할 조건·이벤트·레벨"},
        "risks": {"type": "array", "items": {"type": "string"}, "description": "화자가 짚은 리스크·반대 시나리오"},
        "quotes": {"type": "array", "items": {"type": "string"}, "description": "인상적인 원문 발언 2~4개 (그대로)"},
    },
    "required": ["one_liner", "stance", "key_points", "sections", "tickers", "themes",
                 "numbers", "checkpoints", "risks", "quotes"],
    "additionalProperties": False,
}

SYSTEM = """당신은 국내 증권사 리서치센터의 시니어 애널리스트다. 유튜브 투자·산업 채널 영상의 자막을 읽고,
바쁜 펀드매니저가 영상을 보지 않고도 핵심을 파악할 수 있는 한국어 요약 리포트를 작성한다.

원칙:
- 자막에 실제로 나온 내용만 쓴다. 추측·외부지식으로 채우지 않는다. 자막 오인식(고유명사·숫자)은 문맥으로 바로잡되 확신 없으면 원문 표기 유지.
- 수치·레벨·날짜·종목명은 빠짐없이 보존한다. "많이 올랐다"보다 "+12% (8월 한 달)"처럼.
- 화자의 주장과 근거를 구분하고, 확신 표현의 강도(단정/조건부/가능성)를 살린다.
- 광고·잡담·인사는 제외. 자막의 [mm:ss] 타임스탬프를 sections.t 에 활용한다.
- 문체: 개조식, 건조하게. 존댓말 금지."""


def summarize(txt_path: Path, client):
    meta_p = txt_path.with_suffix(".json")
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    transcript = txt_path.read_text(encoding="utf-8")
    ch = CHANNELS.get(meta.get("channel", ""), {})
    header = (f"채널: {meta.get('channel_name') or ch.get('name','')} — {ch.get('focus','')}\n"
              f"제목: {meta.get('title','')}\n게시일: {meta.get('published','')}\n"
              f"길이: {(meta.get('duration_sec') or 0)//60}분\n")
    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"{header}\n<transcript>\n{transcript}\n</transcript>"}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"refusal: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("max_tokens 도달 — 출력이 잘림")
    data = json.loads(next(b.text for b in msg.content if b.type == "text"))
    out = {k: meta.get(k) for k in ("video_id", "channel", "channel_name", "title", "url",
                                     "published", "duration_sec", "members_only")}
    out.update(data)
    out["model"] = MODEL
    out["usage"] = {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="특정 transcript .txt 만")
    ap.add_argument("--channel")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    try:
        import anthropic
    except ImportError:
        sys.exit("pip install anthropic")
    client = anthropic.Anthropic()

    files = [Path(f) for f in args.files] if args.files else sorted(
        TR.glob(f"{args.channel or '*'}/*.txt"))
    n = 0
    for f in files:
        out = SM / f.parent.name / f.with_suffix(".json").name
        if out.exists() and not args.force:
            continue
        print(f"요약중: {f.parent.name}/{f.name}")
        try:
            data = summarize(f, client)
        except anthropic.RateLimitError as e:
            print(f"  rate limit — {e.response.headers.get('retry-after','?')}s 후 재시도", file=sys.stderr); continue
        except anthropic.APIStatusError as e:
            print(f"  API {e.status_code}: {e.message}", file=sys.stderr); continue
        except anthropic.APIConnectionError:
            print("  네트워크 오류", file=sys.stderr); continue
        except RuntimeError as e:
            print(f"  {e}", file=sys.stderr); continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  → {out.relative_to(ROOT)}  (in {data['usage']['in']:,} / out {data['usage']['out']:,} tok)")
        n += 1
    print(f"완료 {n}건")


if __name__ == "__main__":
    main()
