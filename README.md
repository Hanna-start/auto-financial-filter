# Auto Financial Filter — 재무 기반 종목 스크리너

공개된 펀더멘털 선별 기준을 자동화한 종목 스크리너입니다.
**실제 재무 데이터**(한국 DART · 미국 SEC EDGAR)와 시세(FDR · yfinance)로,
한국(코스피·코스닥)과 미국(S&P500 + 전체 거래소 상장)을 객관·일관 기준으로 선별합니다.

> 분기 재무 기반(TTM·YoY)으로 판단합니다. 재무는 옆 프로젝트
> [`dart-audit-extractor`](https://github.com/Hanna-start/dart-audit-extractor)가 수집해
> `screener.db`에 적재하고, 이 프로젝트는 그걸 읽어 스크리닝합니다.

## 선별 기준 (3단계 + 가드)

`engine.py` 한 곳에 정의 — 한국(`KR_CRITERIA`)·미국(`US_CRITERIA`) 두 프로파일로 **이원화**.
한국은 원기준 그대로, 미국은 시장 특성에 맞춰 일부만 조정합니다.

| 단계 | 한국(코스피·코스닥) | 미국 — 차이만 |
|---|---|---|
| ① 유동성 | 최근 20거래일 평균 거래대금 ≥ 100억원 | ≥ **$30M** |
| ② 재무건전 | 부채비율 < 200% · 매출성장(YoY) ≥ 10% · TTM 영업현금 > 0 · 자본총계 > 0 | 자본총계 ≤ 0이어도 **이익잉여금 > 0이면 통과**(자사주매입 우량주) |
| ③ 품질성장 | TTM 영업이익률 ≥ 10% · 이익피크(최근 4분기 영업이익=과거 최고) · 원가율 개선 | **원가율 개선 면제** · 피크 판정에 16분기↑ 이력 요구 · 이력 최근 20분기(5년)로 절단 |

판단 원칙: 규모·수익성 = TTM(최근 4분기 합), 성장 = YoY(같은 분기 전년), 분기값 = 누적차감 환산.
미국 차이의 근거는 [기준_미국.md](기준_미국.md) 참고.

## 실행

```powershell
# 사전: dart-audit-extractor가 screener.db에 분기 재무를 적재해 둔 상태
py run_kospi_quarterly.py     # 코스피  → dashboards/dashboard_kospi.html
py run_kosdaq_quarterly.py    # 코스닥  → dashboards/dashboard_kosdaq.html
py run_us_quarterly.py        # 미국 S&P500       → dashboards/dashboard_us.html
py run_us_all_quarterly.py    # 미국 전체(거래소 상장) → dashboards/dashboard_us_all.html
```

각 실행은 콘솔 리포트 + `dashboards/*.html`(시각 대시보드) + `results/*.xlsx`(엑셀)를 생성합니다.
재무는 분기마다, 주가·밸류에이션(PER/PBR/PSR, 표시용)은 매 거래일 갱신됩니다.

## 구조

```
engine.py                  공유 엔진 = 기준·게이트·재무엔진 (기준 변경은 여기만)
run_kospi_quarterly.py     코스피 진입점 (+ KR 시세·렌더)
run_kosdaq_quarterly.py    코스닥 진입점 (코스피 엔진 재사용)
run_us_quarterly.py        미국 S&P500 진입점 (+ US 시세 bulk·렌더)
run_us_all_quarterly.py    미국 전체 진입점 (S&P500 ∪ 유동성통과)
screen_us_liquidity.py     미국 확장: EDGAR 수집 전 거래대금 선필터
market_cache.py            시세 캐시·라이브 실패 시 직전값 폴백
dashboards/                결과 HTML
results/                   엑셀·CSV 산출물
legacy/                    옛 '연간' 프레임워크(미사용·보존)
```

`run_*.py`는 `engine.py`를 import하고, 시장별 차이(시세 출처·통화·거래대금 기준)만 각자 둡니다.

## 데이터 소스

- **재무**: 한국 = DART, 미국 = SEC EDGAR companyfacts(us-gaap). `dart-audit-extractor`가 수집 → `screener.db`의 `financials_q`.
- **시세**: 한국 = KRX 일별 데이터(FinanceDataReader 캐시, 최근 거래일로 walk-back), 미국 = yfinance bulk. 둘 다 `market_cache`로 폴백.
- 키·승인 불필요(DART API 키는 수집기 측). 비율 기준이라 환율 무관 — 거래대금만 통화별 절대 기준(한국 100억원, 미국 $30M).

## 다른 PC에서 돌리려면 (경로 전제)

이 프로젝트는 **개인용**이며, 옆 프로젝트 `dart-audit-extractor`가 같은 디스크 위치(`D:/Agent_Project/...`)에 있다는 전제로 절대경로가 하드코딩돼 있습니다. 다른 환경에서 돌리려면 아래만 환경에 맞게 바꾸면 됩니다.

- `engine.py` — `DB` (재무 DB = `dart-audit-extractor/screener.db`)
- `app.py` — `DATA` (명단 json 폴더)
- `run_*.py` · `screen_us_liquidity.py` — 각 `*_INDEX` / `DATA_DIR` (대상 명단 json 경로)

`market_cache.db`는 이 폴더 기준 상대경로라 그대로 따라옵니다. 재무 DB(`screener.db`)는 읽기전용으로만 씁니다.

## 참고

- 미국 대형 ADR(TSM·ASML·Nokia 등)은 본국 IFRS로 20-F 제출 → EDGAR us-gaap이 비어 자연 제외됩니다(이 스크리너는 us-gaap 보고 기업만).
- PER/PBR 등 밸류에이션은 **표시용**이며 선별 기준이 아닙니다(yfinance 분모 오류로 이상치가 보일 수 있음).
- 모멘텀(주가추세) 단계는 보류 상태 — 이 스크리너는 backward-looking이며, 미래 판단(밸류트랩·해자 위협 등)은 사용자 몫입니다.
