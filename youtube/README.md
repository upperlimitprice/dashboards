# 유튜브 영상 요약 리포트 파이프라인

구독 채널(멤버십 포함)의 새 영상을 자막 기반으로 요약해 대시보드에 올린다.
자막 수집은 **본인 PC(로그인된 브라우저)** 에서만 가능하고, 요약·빌드는 어디서든 된다.

```
youtube/
├─ channels.json        채널 레지스트리 (키 · 핸들 URL · 탭 · 성격)
├─ fetch.py             [로컬] yt-dlp + 브라우저 쿠키 → transcripts/  (멤버십 영상 포함)
├─ summarize.py         transcripts/ → summaries/*.json  (Claude API, 구조화 스키마)
├─ build.py             summaries/*.json → <채널>/<날짜>_<id>.html + index.html
├─ transcripts/<ch>/    자막 원문 + 메타  ← .gitignore (커밋 금지: 유료 콘텐츠)
├─ summaries/<ch>/      요약 JSON        ← 커밋 (원본이 아니라 요약)
├─ <ch>/*.html          생성된 리포트     ← 커밋
└─ index.html           채널별 목록
```

## 1회 준비 (로컬 PC)

```bash
pip install -U yt-dlp anthropic
export ANTHROPIC_API_KEY=sk-ant-...      # 또는 ant auth login
```
- 구독 계정으로 YouTube에 로그인된 브라우저(Chrome 기본)가 있어야 함. `--browser edge|firefox|brave` 로 변경.
- 브라우저 쿠키를 못 읽는 환경이면 확장프로그램으로 `cookies.txt` 를 내보내 `--cookies youtube/cookies.txt` (gitignore 되어 있음).

## 매일 루틴

```bash
python youtube/fetch.py --channel infomkt --latest 3        # 새 영상 자막 (videos + membership 탭)
python youtube/fetch.py --channel unrealtech --latest 3
python youtube/summarize.py                                 # 아직 요약 없는 자막 전부
python youtube/build.py                                     # HTML 생성
python gen_index.py                                         # 메인 대시보드 카드 갱신
git add youtube/summaries youtube/*/ youtube/index.html index.html && git commit -m "youtube 요약 $(date +%F)" && git push
```

단일 영상: `python youtube/fetch.py https://www.youtube.com/watch?v=XXXX --channel infomkt`

## API 없이 (Claude Code 세션에서 수동 요약)

1. 로컬에서 `fetch.py` 로 자막을 받는다 (또는 YouTube 웹 `스크립트 표시` → 복사).
2. Claude Code 세션에 자막을 붙여넣고 "summarize.py 의 SCHEMA 형식으로 `youtube/summaries/infomkt/<날짜>_<id>.json` 작성" 요청.
3. `build.py` → `gen_index.py` → 커밋.

## 요약 JSON 스키마 (summarize.py `SCHEMA`)

| 필드 | 내용 |
|---|---|
| `one_liner` / `stance` | 한 줄 요약 · 전반 톤 (bullish/bearish/neutral/mixed) |
| `key_points[]` | 핵심 메시지 5~8개 (수치 포함) |
| `sections[]` | `{t, title, body}` 타임스탬프별 흐름 |
| `tickers[]` | `{name, code, view, note}` 언급 종목 (positive/negative/neutral/watch) |
| `themes[]` / `numbers[]` | 테마 키워드 · `{label, value, context}` 수치 |
| `checkpoints[]` / `risks[]` / `quotes[]` | 확인할 조건 · 리스크 · 원문 발언 |

메타(`video_id, channel, title, url, published, duration_sec, members_only`)는 fetch 메타에서 자동 병합.

## 채널 추가

`channels.json` 에 키 추가 → `tabs` 에 `"membership"` 넣으면 멤버십 탭도 스캔.

## 주의

- 공개 레포다. **자막 원문·쿠키는 절대 커밋하지 않는다** (.gitignore 확인). 멤버십 요약 페이지는 🔒 배지가 붙고 개인 참고용.
- 이 레포를 갱신하는 원격 서버/Claude Code 웹 세션에서는 youtube.com 이 차단돼 `fetch.py` 가 동작하지 않는다 → fetch 만 로컬, 나머지는 어디서든.
