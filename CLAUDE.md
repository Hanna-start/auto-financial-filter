# CLAUDE.md — 프로젝트 컨텍스트 & 협업 메모리

> 이 파일은 Claude가 이 폴더를 열 때 가장 먼저 읽는 맥락 파일입니다.
> 작업을 다시 시작할 때 처음부터 설명하지 않아도 되도록, 목적·현황·다음 할 일·협업 규칙을 기록합니다.
> 최초 작성: 2026-06-05

---

## 0. ▶ 다음 세션 시작점 (2026-06-08 기준)

**세 시장(코스피·코스닥·미국) 분기 스크리너 모두 완성·실행 완료.** (2026-06-08 기준. 미국은 S&P500 + 전체 거래소 상장으로 확장 완료. 코스닥 잔여 수집만 후순위로 남음.)

### ★ 현재 최종 결과 (전부 2026-06-08, 기준 글자그대로 동일 + `자본총계>0` 추가)

| 시장 | 대상 | 유동성 | 재무건전 | **최종** | 산출물 |
|---|---|---|---|---|---|
| 코스피 | 835 | 180 | 46 | **15** | `dashboard_kospi.html` |
| 코스닥(상위300) | 300 | 116 | 39 | **13** | `dashboard_kosdaq.html` |
| 미국 S&P500 | 502 | 502 | 104 | **27** | `dashboard_us.html` |
| **미국 전체(거래소 상장)** | 2,343 | 2,297 | 432 | **71** | `dashboard_us_all.html` |

재실행(주가·밸류 갱신):
```powershell
cd d:\Agent_Project\auto-financial-filter
py run_kospi_quarterly.py        # 코스피 → dashboard_kospi.html
py run_kosdaq_quarterly.py       # 코스닥 → dashboard_kosdaq.html
py run_us_quarterly.py           # 미국 S&P500 → dashboard_us.html
py run_us_all_quarterly.py       # 미국 전체(S&P500+유동성통과 확장) → dashboard_us_all.html
```

### 미국 전체 확장 파이프라인 (S&P500 밖, 2026-06-08) — "유동성 선필터 후 수집" 순서 역전

사용자 설계: 7천 개 재무를 EDGAR에서 다 받기 전에 **가장 싼 ①유동성(거래대금≥$10M)을 먼저** 적용해 수집 대상을 줄임. 순서:
1. `dart-audit-extractor/screener/build_us_all_universe.py` → FDR NYSE+NASDAQ+AMEX 6,980 → CIK 매칭·S&P500 제외 → `data/us_all_index.json`(**5,413 고유 CIK**).
2. `auto-financial-filter/screen_us_liquidity.py` → yfinance **bulk download**로 거래대금만 5,413개 조회 → ≥$10M **2,156개 통과** → `data/us_liquid_index.json`(EDGAR 수집 대상) + 검토 CSV.
3. `cd dart-audit-extractor; py screener/collect_us.py --index data/us_liquid_index.json` → EDGAR 재무 수집(ok 1,844/empty 306/error 6). empty 다수=대형 **ADR이 IFRS로 20-F 제출 → us-gaap companyfacts 빔**(TSM·ASML·Nokia 등 자연 제외; 이 스크리너는 us-gaap 보고 기업만).
4. `auto-financial-filter/run_us_all_quarterly.py` → S&P500 ∪ 유동성통과 = 2,343개 스크리닝 → **최종 71개**(S&P500 27 전부 + 신규 44: ARM·MRVL·Astera·Credo·HEICO·Reddit·Penumbra·Bentley 등 반도체·산업재·의료기기·SW 중소형 성장주).

### 2026-06-08 핵심 수정 (전부 로컬·미커밋)

- **`자본총계>0` 게이트 추가**(`run_kospi_quarterly.py:screen()` + `run_us_quarterly.py:screen_us()` 양쪽 — 미국은 거래대금 달러판이라 별도 함수). 음수 자본(자사주 매입 자본잠식, 부채비율이 음수라 `<200%`를 자동 통과하던) 회사 제외 → 미국 S&P500 29→27(TransDigm·Fair Isaac 탈락).
- **FDR 404 근본 수정 + 시세 캐시**: FDR `StockListing('KOSPI')`은 저자 GitHub의 **당일 marcap-cache CSV 미게시 시 404**(2026-06-08 발생). → ①`run_kospi_quarterly.fetch_krx_marcap()`로 교체: `max_work_dt`부터 거슬러 **실제 존재하는 최근 거래일 CSV**를 받음(=직전 거래일 값, 사용자 수용). ②신규 `market_cache.py`(`market_cache.db`): 시세를 날짜별 누적 저장, 라이브 실패 시 직전 저장값 폴백(KR/US 공용). `.gitignore`에 `market_cache.db` 추가.
- **코스피 진입점 버그 수정**: `run_kospi_quarterly.py`의 `main()`이 index_json 없이 호출돼 financials_q의 코스닥·미국까지 섞어 대상 1634로 오염 → `kospi_index.json` 넘기도록 수정(대상 835 정상화).
- **확장용 시세 bulk화**: `run_us_quarterly.fetch_market()`을 종목별 1콜→**청크 bulk download**로 교체(수천 개 대응), 시총은 재무건전 통과분만 per-ticker(`fetch_marcaps`). `main()`을 `index_paths`/`title`/`dash`/`xlsx_prefix` 파라미터화(S&P500 기본 동작 보존).
- **공유 엔진 None-부채 방어**: `compute()`의 부채비율이 `부채 None`(EDGAR Liabilities 태그+자산-자본 유도 모두 실패)일 때 `None/int` 에러 → 가드 추가(부채 None→재무건전 자연탈락). 확장 유니버스에서만 발생.
- **모멘텀(4단계)은 여전히 보류**(사용자 결정). 어도비가 모든 미국 결과의 단골 — backward-looking 한계(AI 해자 위협 미반영)를 사용자가 정확히 지적, 미래 판단은 사용자 몫(value trap은 PER에 이미 드러남).

### 미국 표시값 주의(필터 아님): ANET PER 5,547만·LOAR 8.3만 등 yfinance EPS 분모 오류, 일부 `PER —`(시총 조회 실패). PER/PBR은 표시 전용이라 선별 무관.

### (후순위·보존) 코스닥 나머지 수집 (500개/일 × 화·수·목) — 미국 다음으로 미룸

코스닥 1,816개사 중 **상위 300개는 수집 완료(2026-06-08)**. 남은 1,516개를 3일에 나눠 받는다(회사당 34콜, 500개=17,000콜 < DART 일한도 2만). **매일 한 줄씩(누적 --limit, 이미 받은 건 skip):**

```powershell
cd d:\Agent_Project\dart-audit-extractor
py screener/collect_quarterly.py --index data/kosdaq_index.json --limit 806    # 6/9 화: 301~806
py screener/collect_quarterly.py --index data/kosdaq_index.json --limit 1312   # 6/10 수: 807~1312
py screener/collect_quarterly.py --index data/kosdaq_index.json --limit 1816   # 6/11 목: 1313~1816(완료)
cd d:\Agent_Project\auto-financial-filter
py run_kosdaq_quarterly.py     # 그날까지 늘어난 코스닥 후보 재스크리닝 → dashboard_kosdaq.html
```

- 안전장치: `empty`가 비정상적으로 많으면(한도 닿음 신호) 다음 날 `--recheck-empty` 붙여 보완.
- 수집은 2026-06-08 새벽에 시작됐으므로, 같은 날 추가 수집 말고 **날짜를 바꿔서**(한도 리셋) 진행.

### 코스닥 1차 결과(상위 300, 2026-06-08) — 동일 기준

300 → 유동성 116 → 재무건전 39 → **최종 13개**(리노공업·이오테크닉스·피에스케이·파마리서치·에스티팜·티에스이·비츠로셀·하나머티리얼즈·GST·RFHIC·엘티씨·한선엔지니어링·저스템). **반도체 장비·소재 + 바이오 클러스터로 코스피 15개와 안 겹침.** 기준은 코스피와 **글자 그대로 동일**(코스닥용 조정 없음 — `run_kosdaq_quarterly.py`는 코스피 엔진 import만, 기준값·screen()은 `run_kospi_quarterly.py`에 1벌). 통과율 코스닥 4.3% > 코스피 1.8%(코스닥에 성장+흑자주 비중 높음). 13개 전부 코스닥 명단O·코스피 명단X로 검증됨(섞임 0).

### 오늘 만든 코드(전부 로컬·미커밋)

- `dart-audit-extractor/screener/build_kosdaq_universe.py`(코스피판 미러, 'KOSDAQ') → `data/kosdaq_index.json`(1,816개, 시총순)
- `dart-audit-extractor/screener/collect_quarterly.py`에 `--index` 옵션 추가(코스피 기본·하위호환)
- `auto-financial-filter/run_kospi_quarterly.py`의 `main()`을 `market`/`index_json` 파라미터로 일반화(인자 없으면 코스피 그대로)
- `auto-financial-filter/run_kosdaq_quarterly.py`(신규, 코스닥 전용 진입) + `dashboard_kosdaq.html`

### 판단 기록: 미국 보류 / 금융위 API 기각

- **미국**: 가능하지만 EDGAR 새 파이프라인 = 며칠짜리 별도 프로젝트. 국내(코스닥) 먼저 넓히는 게 ROI 우위 → 보류.
- **금융위 data.go.kr 재무 API 기각**: ①현금흐름표 없음(요약/BS/IS뿐 → TTM영업현금 기준 불가) ②일한도 1만(<DART 2만) ③법인등록번호(crno) 매핑 필요. data.go.kr '단일회사 전체재무제표'는 사실상 DART 재배포. → 코스닥도 DART가 우월.

---

### (이력) 코스피 분기 스크리너 — 완료

실데이터 분기 재무로 코스피를 TTM·YoY 기준 스크리닝. 상세는 메모리 `project-kospi-quarterly`·`reference-korea-data-sources`.

- **명단**: FinanceDataReader('KOSPI') 보통주 **838개**(상폐 없음, 시총순) → 옆 프로젝트 `data/kospi_index.json`.
- **분기 수집 현황**: **Day 1 완료(시총 상위 280개, 2022~2026Q1)** → `screener.db`의 `financials_q` 테이블(연간 `financials`와 분리). 남은 배치(하루 한도 때문에 날 나눔):

```powershell
cd d:\Agent_Project\dart-audit-extractor
py screener/collect_quarterly.py --limit 560    # 다음 날: 281~560위 (앞 280 skip)
py screener/collect_quarterly.py --limit 838    # 그 다음 날: 561~838위
cd d:\Agent_Project\auto-financial-filter
py run_kospi_quarterly.py                        # 분기 스크리닝 → 코스피_분기_결과_*.xlsx + dashboard_kospi.html
```

- **기준 = 원래 재무선배(엄격)**: 거래대금≥100억·부채비율<200%·매출성장YoY≥10%·TTM영업이익률≥10%·이익피크·원가율개선·TTM영업현금>0. (과거 완화=거래대금50억·성장0%·이익률5%는 2025·2026 분기 미수집 시절 통과 0을 피하려던 임시 우회였고, 데이터가 채워져 2026-06-06 원래 기준으로 복귀. 완화 산출물·`run_kospi_strict.py`는 제거.)
- **1차 결과(280개)**: 유동성 169 → 재무건전성 46 → 최종 **15개**(삼성·SK하이닉스, HD현대 조선·중공업 6, 셀트리온·SK바이오팜, 에이피알·달바, 삼양식품, 이수페타시스, GS피앤엘). 삼성+69%·하이닉스+198%는 실제 메모리 업황 급등 — 데이터·환산 정확성 방증.
- **밸류에이션·주가 추가(2026-06-06)**: PER·PBR·PSR·시총/TTM영업이익 + 현재가·등락률·주가 기준일을 콘솔/엑셀/대시보드에 표시(필터 아님). 당기순이익이 `financials_q`에 이미 있어 재수집 불필요(수집기가 `fnlttSinglAcntAll`=전체 계정). 재무=분기 갱신, 주가=매 거래일 갱신.
- **GitHub 게시(2026-06-06, 명시 지시로)**: 두 repo push 완료 — 스크리너 `Hanna-start/auto-financial-filter`(d370b39), 수집기 `Hanna-start/dart-audit-extractor`(3df3b9f). `screener.db`·`.env`·`data/`는 .gitignore 제외. (밸류에이션·주가 추가분은 아직 미push.)
- **다음 단계 = Streamlit 앱(사용자 OK, 미착수)**: `streamlit_app.py` 신규, 기존 엔진 import, 기준 4개를 슬라이더로 실시간 재스크리닝. 탭(스크리닝/전체테이블/밸류에이션 산점도/회사상세/비교). 미정: 핵심3탭 먼저 vs 5탭 / 주가차트 포함. `pip install streamlit`부터. 상세 [[project-kospi-quarterly]].
- **핵심 학습**: 분기 `thstrm_amount`=3개월/`thstrm_add_amount`=누적, 순수분기=누적차감. 공시달력 게이트로 재실행 시 새 분기만 받음(무낭비). `financials_q`엔 전 계정 적재돼 새 지표는 재수집 불필요.
- **상태**: 밸류에이션·주가·Streamlit 작업분은 **미커밋·미push**(로컬만). git/push는 명시 지시 때만.

### (참고) 옛 연간 경로 — 보류

연간(`financials`, ~65개사, `run_listed_screener.py`)은 그대로 둠. 분기 코스피 작업이 우선.

---

## 1. 프로젝트 목적

"재무선배"라는 분이 공개한 펀더멘털 선별 기준을 코드로 자동화하여,
**상장주식을 객관적·일관된 기준으로 걸러내는 종목 스크리너**를 만드는 것.

- 원래 의도: 재무선배 기준으로 상장주식 필터
- 설계 범위: 한국 + 미국 (둘 다 설계됨)
- 실제 결과를 받아본 범위: **한국 주식만**
- 기준 적용 흐름: 유동성 → 재무건전성 → 품질성장 (+ 모멘텀, 사후 추가)

---

## 2. 현재 상태 & 핵심 한계 (★중요★)

### ✅ 2026-06-05 업데이트 — 실제 데이터 경로 연결됨
옆 프로젝트 `dart-audit-extractor`의 `screener.db`(실제 DART 재무, SQLite)를 **읽기 전용**으로
연결하는 하이브리드 경로를 새로 만들었다. 이제 가짜 데이터 없이 진짜 재무로 스크리닝이 된다.
- 진입점: **`run_listed_screener.py`** (가짜 생성기 미사용)
- 가격(1·4단계 유동성·모멘텀) = yfinance / 재무(2·3단계) = screener.db (연 단위)
- 신규 코드: `data_access/screener_db_adapter.py`, `data_access/hybrid_manager.py`,
  `filters/annual_financial_filters.py` (연 단위 전용 필터)
- 검증: 파일럿 13개사 실데이터로 2·3단계 통과/탈락이 손계산과 일치 확인 (최종 노루홀딩스·비트컴퓨터).

### ✅ 2026-06-05 추가 — 데이터 100개 표본 확대 + 전체 4단계 검증
`dart-audit-extractor`에서 `collect.py --pilot 100`을 1회 실행해 실재무 보유 회사를
**13개 → 65개**로 늘렸다(100개 시도 중 65개에 표준 재무 존재, 나머지는 스팩·리츠라 자연 제외).
이어 `run_listed_screener.py`(옵션 없이) 전체 4단계(유동성→재무→품질→모멘텀)를 65개사로 검증:
구조·연결 모두 정상 작동(98초, 엑셀 산출). 최종 후보 예: 에스엘·한국콜마.

- 이 과정에서 **yfinance 티커 버그를 발견·수정**: 전 종목에 `.KS`를 붙여 KOSDAQ이 404로
  1단계 탈락하던 것을 시장별(`.KS`/`.KQ`)+폴백으로 고침. 이제 KOSPI·KOSDAQ을 공정하게 거른다.
- 수집기 체크포인트는 안전: 네트워크 에러는 `'error'`로 기록돼 다음 실행 때 재시도(영구누락 없음).

### 남은 한계

1. **실제 재무가 수집된 회사가 현재 65개(수집량에 따라 변동).** `screener.db`의 `companies`엔
   상장사 3,965개가 있으나 `financials`엔 표본 수집분만 존재(2022~2024). 전체 시장을 돌리려면
   **dart-audit-extractor에서 `screener/collect.py`를 더 큰 범위로 적재**해야 한다
   (그 프로젝트는 독립 유지 — 그쪽 DB를 채우는 별개 단계).
2. **데이터가 연(年) 단위.** 분기용 기존 필터는 못 씀 → 연 단위 필터로 기준 재정의함
   (매출성장=YoY, 이익피크=보유연도 중 최고, 원가율추세=연간 비교).
3. ~~구식 가짜 경로 잔존~~ ✅ **정리 완료(2026-06-05, cleanup 브랜치)** — `WebScrapingFinancialAdapter`
   가짜 생성기와 이를 쓰던 스크립트 제거, 가짜 미국 경로(`us_adapters.py` 등) 삭제,
   품질필터의 US 16분기 위조 시뮬 제거. 상세는 아래 §2.1.

### ✅ 2026-06-05 추가 — 한국 전용으로 방향 확정 + 가짜/미국 정리
방향: **지금은 한국만 완성한다.** 미국은 어차피 전부 가짜(`random.uniform()` 합성)였고,
뼈대(모델·파이프라인·연 단위 필터)는 남으므로 향후 진짜 데이터(yfinance/EDGAR)로
재연결 가능. 들어낸 것:

- 가짜 미국 경로: `us_adapters.py`, `run_us_*.py`(3), `run_vectorized_us_analysis.py`, `debug_us_stage3.py`, `test_vectorized_us_analysis.py`
- 가짜 재무 생성기: `alternative_adapters.py`의 `WebScrapingFinancialAdapter`/`AlternativeDataAccessManager`(진짜 `YFinanceKoreanAdapter`만 유지) + 이를 쓰던 `run_real_data_analysis.py`·빈 `run_real_analysis.py`·`debug_samsung.py`·`check_data_date{,2,3}.py`
- 품질필터 결함: `quality_growth_filter.py`의 4→16·4→6분기 위조 시뮬(피크 판정 편향) 제거
- 가짜 산출물·대시보드: `_archive_fake/`로 격리(삭제 아님, 복구 가능)
- ⚠️ 알려진 잠재 이슈: `test_cash_flow_health_validation`(property test)이 fresh 실행 시 간헐 실패 — 손대지 않은 `financial_health_filter`의 현금흐름 로직. 별도 조사 대상.

### 산출물의 의미

- `상장사_스크리너_결과_*.xlsx`(`run_listed_screener.py` 산출)는 **실제 재무 기반** — 단 현재 대상 약 65개사(수집량에 따라 변동) 한정. **유일하게 신뢰할 산출물.**
- 과거 가짜 데이터 산출물(`재무건전성_필터링_결과_*.xlsx` 등)은 `_archive_fake/`로 격리됨 — 신뢰 불가.

---

## 3. 평가 요약

| 항목 | 평가 |
|---|---|
| 설계·아키텍처 | ★★★★★ 실무급, 확장 고려 (포트/어댑터 분리) |
| 테스트·검증 | ★★★★☆ 109개 + property-based test |
| 문서화 | ★★★★☆ 기획(.kiro)~정리본까지 풍부 |
| 실행 사용성 | ★★☆☆☆ CLI 방치, run 스크립트 분산(정리 후 감소) |
| 버전 관리 | ★★★☆☆ cleanup 브랜치에서 의미 단위 커밋 시작(2026-06-05) |
| **데이터 신뢰성** | ★★★☆☆ **가짜 경로 제거 + 티커 버그 수정 → 진짜 경로만 남음. 실데이터 65개사로 확대 중** |

본질: "거의 완성된 스크리너"가 아니라 "거의 완성된 스크리너의 틀". 가짜는 걷어냈고 4단계 작동도 검증됐다. 남은 빈 칸은 **① 진짜 재무 데이터 범위 확대(65→전체)** 하나로 좁혀졌다.

---

## 4. 다음 할 일 (우선순위)

1. ~~[최우선] 진짜 데이터 연결~~ ✅ **완료(2026-06-05)** — screener.db 하이브리드 경로(`run_listed_screener.py`)
2. **[최우선] 종목 범위 확대** — dart-audit-extractor에서 `screener/collect.py`로 적재 확대 →
   현재 65개사 → 더 큰 표본(300/500…) → 활성 상장사 전체(~2,600). 그 프로젝트는 독립이므로 그쪽에서 수행. (현재 유일한 핵심 과제)
   - ⚠️ 1,000개 이상 = 일 한도(20,000콜) 도달 가능. 그 전에 `collect.py`의 한도 감지(020/021)·재개 처리(README TODO)를 붙여야 'empty' 오염을 막는다. 100개 표본은 무관.
3. ~~구식 가짜 경로 정리~~ ✅ **완료(2026-06-05)** — §2.1 참조.
4. **실행 통로 통합** — 남은 run 스크립트(`run_listed_screener`/`run_relaxed_criteria`/`run_unlisted_company_analysis`)를 CLI/설정 프리셋으로 통합.
5. **남은 정리(선택)** — `cli.py` 방치 상태 처리, 벡터화/일반 필터 중복, `_archive_fake/` 최종 삭제 여부.
6. ~~미국 품질필터 16분기 시뮬 결함~~ ✅ **해결(2026-06-05)** — 위조 시뮬 제거(미국 경로 자체 삭제).
7. **버전 관리** — cleanup 브랜치 → `main` 병합 결정. 이후 의미 단위 커밋 유지.
8. **(신규) 잠재 이슈 조사** — `test_cash_flow_health_validation` property 테스트 간헐 실패 원인.

---

## 5. 협업 규칙

- **판단은 사용자(Hanna), 코드·데이터·구조화는 Claude.** "무엇이 필요한가"는 사용자가 주도.
- 사용자는 개발 지식보다 **업무 맥락 설계 역량**이 강점. 코드 줄 단위 설명보다 **의사결정에 필요한 형태**로 전달.
- 제안/기획/개선안 요청 시 — **실행 전 텍스트로 계획을 먼저 제시하고 승인받은 뒤 실행.**
- 근거 있는 판단은 사용자 의견과 충돌해도 물러서지 말 것. 단, 솔직하고 사탕발림 없이.
- **최소 변경 원칙**: 요청 범위 밖 기능·추상화·"유연성" 추가 금지. 200줄을 50줄로 줄일 수 있으면 다시 쓴다. (과거 가짜 데이터·미국 경로·위조 시뮬이 이 원칙 위반의 산물.)
- **외과적 수정**: 내가 만든 잔해만 치운다. 인접 코드 임의 "개선"·리팩터 금지. 기존 dead code는 발견 시 알리되 삭제는 지시받고.

---

## 6. 기술 메모

- 패키지: `auto_financial_filter/` (~5,200 LOC). 레이어: models → data_access → filters → pipeline → cli/utils
- 진짜 경로(권장): 가격=yfinance(`YFinanceKoreanAdapter`) / 재무=screener.db(`ScreenerDBAdapter`), `HybridDataAccessManager`로 결합. 진입점 `run_listed_screener.py`.
  - (가짜 `alternative`(WebScraping) 폴백은 제거됨. 남은 비실데이터 경로는 테스트·데모용 `mock_adapters`뿐.)
- 정식 진입점 `cli.py`는 1단계(유동성)에서 멈춰 방치됨(미해결). 실질 진입점은 루트의 `run_listed_screener.py`.
- 테스트: `tests/` 24파일 109함수, pytest + Hypothesis. 설계서 13개 correctness property와 매핑.
- 스펙: `.kiro/specs/financial-stock-filter/` (requirements/design/tasks). 단 `.gitignore`에 포함됨.
