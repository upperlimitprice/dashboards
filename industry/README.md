# 산업 트래커 (industry/)

발전설비·전력망·자동차·데이터센터·화물·MLCC·태양광 7개 페이지를 **공개 데이터로 자동 수집**해 HTML 대시보드로 만드는 프로젝트입니다.
맥미니에서 매일 정해진 시각에 `launchd` 가 실행하고, 결과(`site/`, `data/`)를 이 저장소에 커밋·푸시합니다.

```
industry/
├── run.py                  # 실행기: 수집 → data/<page>.json → site/<page>.html (+ site/index.html)
├── pages/                  # ★ 페이지별 프로젝트 — 파일 하나 = 페이지 하나
│   ├── gen_capacity.py     #   collect() 네트워크 수집 / build() 가공·차트 구성
│   ├── grid.py  auto.py  datacenter.py  freight.py  mlcc_lead.py  solar.py
├── core/
│   ├── sources/            # 데이터 출처 어댑터 (EIA, EIA-860M, FRED, SEC, 관세청, TWSE, NY Fed)
│   ├── page.py             # 페이지 모델 → HTML 렌더
│   ├── collect.py          # 소스별 실패 격리 + 실패 시 이전 데이터 유지
│   ├── series.py trade.py  # 시계열 계산 (YoY, 이동평균, 단가 등)
│   └── env.py http.py      # .env 로딩, 재시도·캐시 HTTP, API 키 가림(scrub)
├── templates/              # page.html(공용 차트 페이지), hub.html(목록)
├── manual/*.csv            # 무료 API가 없는 지표 직접 입력 (리드타임·스팟가)
├── data/                   # 수집 원자료 JSON (커밋됨 — 누적 이력 보존)
├── site/                   # 생성된 HTML (커밋됨 — GitHub Pages로 서비스)
├── deploy/                 # 맥미니 설치·launchd 스케줄
└── tests/                  # 오프라인 테스트 (파서 + 모든 페이지 렌더)
```

## 맥미니 설치 (1회)

```bash
cd ~/dashboards/industry          # 저장소를 clone 한 위치
./deploy/install_mac.sh 7 10      # venv·패키지 설치, .env 생성, 매일 07:10 자동 실행 등록
open -e .env                      # API 키 입력 (아래 표)
.venv/bin/python run.py --check   # 키 설정 확인
.venv/bin/python run.py           # 첫 수집 (몇 분 소요)
open site/index.html              # 결과 확인
```

| 환경변수 | 발급처 | 쓰는 페이지 |
|---|---|---|
| `EIA_API_KEY` | https://www.eia.gov/opendata/register.php (무료·즉시) | grid, datacenter(전력판매), solar(발전량) |
| `DATA_GO_KR_KEY` | 공공데이터포털 [관세청_품목별 수출입실적](https://www.data.go.kr/data/15100475/openapi.do) 활용신청 → **디코딩** 키 | auto, mlcc_lead, solar(교역) |
| `SEC_USER_AGENT` | 키 없음. `"이름 이메일"` 형식의 연락처 문자열 | datacenter |

키가 없는 페이지는 건너뛰고(목록에 '키 필요' 표시), 키가 필요 없는 페이지(gen_capacity, freight)는 바로 동작합니다.
`.env` 는 `.gitignore` 되어 있고, 에러 메시지에 섞인 키는 `***` 로 가려져 저장됩니다.

푸시는 맥미니의 git 인증(SSH 키 또는 credential helper)을 그대로 씁니다. 별도 브랜치에 올리려면 `.env` 의 `GIT_BRANCH` 를 지정하세요.

## 일상 사용

```bash
.venv/bin/python run.py                  # 전체 수집 + 렌더
.venv/bin/python run.py grid freight     # 일부만 수집 (나머지는 저장 데이터로 재렌더)
.venv/bin/python run.py --render-only    # 네트워크 없이 HTML만 재생성 (템플릿 수정 후)
.venv/bin/python run.py --push           # 수집 후 커밋·푸시 (launchd 가 쓰는 모드)
launchctl kickstart gui/$(id -u)/com.dashboards.industry   # 스케줄 작업 즉시 실행
tail -f logs/$(date +%F).log                               # 로그
python3 -m unittest discover -s tests -t .                 # 테스트
```

페이지 주소: `industry/site/index.html` (루트 `industry.html` 에서 이동). 원본 사이트처럼
`industry/site/index.html?t=/c/grid` 형태 링크도 해당 페이지로 연결됩니다.

## 페이지별 구성

| 페이지 | 핵심 질문 | 데이터 | 주요 지표 |
|---|---|---|---|
| **gen_capacity** 미국 발전설비 파이프라인 | 신규 발전설비가 얼마나, 무엇으로 들어오나 | EIA-860M 월간 엑셀 (키 불필요) | 기술별 가동 GW, 연도별 계획(전체/공사 중), 실제 신규, 폐지, 주별 상위, 월별 파이프라인 스냅샷 |
| **grid** 미국 전력망 수요 | 전력 수요가 구조적으로 늘고 있나 | EIA-930 일별 지역 수요 | 28일 합계 YoY(본토·PJM·ERCOT 등 9개), 연도별 겹쳐보기, 월별 수요 |
| **auto** 한국 자동차 수출 | 수출 금액·믹스·단가 방향 | 관세청 HS 8703/870380/870340/870360/8708/850760 | 승용차 구성(BEV·하이브리드·내연), YoY 3MMA, $/kg 단가, 부품·배터리 |
| **datacenter** 데이터센터 투자 사이클 | 하이퍼스케일러 capex가 아직 가속 중인가 | SEC XBRL (MSFT·AMZN·GOOGL·META·ORCL·CRWV), EIA 상업용 전력 판매 | 분기·TTM capex, 빅4 YoY, VA·TX·GA·AZ·OH 상업용 전력 12M YoY |
| **freight** 화물·물류 사이클 | 화물 경기 바닥/고점 | FRED(Cass·TSI·운송 PPI·철도), 뉴욕연은 GSCPI (키 불필요) | Cass 물동량·지출·암묵 운임 YoY, 모드별 PPI 지수, 철도 YoY, GSCPI |
| **mlcc_lead** MLCC 사이클 선행지표 | MLCC 업황이 타이트해지고 있나 | 관세청 HS 853224, TWSE 월매출(Yageo·Walsin·Holy Stone), `manual/mlcc_leadtime.csv` | 수출·수입, 금액/단가 YoY, 대만 월매출 YoY(실행마다 누적), 리드타임 |
| **solar** 태양광 수요·교역 | 미국 설치 수요와 한국 셀·모듈 교역 | EIA-860M, EIA 발전량, 관세청 HS 854143/854142, `manual/solar_prices.csv` | 태양광·ESS 실적+계획, 발전 비중, 모듈 수출입·수입 단가 |

### 새 페이지 추가

1. `pages/<key>.py` 를 만들고 `KEY, TITLE, SUBTITLE, NEEDS, collect(prev), build(raw)` 를 정의 (기존 파일 복사 추천)
2. `pages/__init__.py` 의 `ORDER` 에 key 추가
3. `tests/test_all.py` 의 `fake_raw()` 에 합성 데이터 추가 → 테스트 통과 확인
4. 새 데이터 출처가 필요하면 `core/sources/` 에 어댑터 추가 (HTTP는 반드시 `core.http` 경유)

### 설계 원칙

- **collect / build 분리** — 수집 결과는 `data/<key>.json` 에 저장되고, `build()` 는 네트워크 없이 그것만 읽습니다. 차트를 고칠 때 `--render-only` 로 즉시 확인.
- **실패 격리** — 소스 하나가 실패해도 페이지 나머지는 그려지고, 그 소스는 직전 데이터를 유지한 채 페이지 상단에 경고가 뜹니다.
- **누적 이력** — 최신값만 주는 소스(TWSE 월매출, 860M 파이프라인 총량)는 실행할 때마다 `data/` 에 쌓아 시계열을 만듭니다.
- **색 고정** — 같은 대상(예: 태양광, Microsoft)은 모든 차트에서 같은 색. 이중 y축 없음.

## 주의

- 공개 데이터와 직접 입력값만 씁니다. 다른 서비스의 화면·데이터를 가져오지 않습니다.
- 첫 실행 전에는 이 환경(클라우드)에서 외부 API에 접근할 수 없어 실데이터로 검증하지 못했습니다. 파서는 공식 응답 형식 기준으로 작성했고 테스트는 합성 데이터로 통과합니다. 맥미니 첫 실행 로그에서 출처별 오류를 확인하세요 — 오류는 페이지 상단과 `data/<key>.json` 의 `errors` 에 남습니다.
- FRED 시리즈 ID가 폐지·변경되면 해당 시리즈만 오류로 표시됩니다. `pages/freight.py` 의 `FRED` 목록에서 교체하세요.
