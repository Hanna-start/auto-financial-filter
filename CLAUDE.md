# CLAUDE.md — 프로젝트 컨텍스트 & 협업 메모리

> Claude가 이 폴더를 열 때 가장 먼저 읽는 맥락 파일. **현재 상태 + 구조 + 실행법 + 협업 규칙**만 둔다.
> 세션별 히스토리·의사결정 이력은 메모리([[project-kospi-quarterly]])와 git 로그에 보존.

## 1. 목적

공개된 펀더멘털 선별 기준을 코드로 자동화한 **종목 스크리너**.
한국(코스피·코스닥) + 미국(S&P500 + 전체 거래소 상장)을 **실데이터**로 객관·일관 선별.

## 2. 현재 상태 (주가 2026-06-12 기준) — 세 시장 완성·실행 완료

대시보드 깔때기(대상 → ①유동성 → ②재무건전 → ③최종). 유동성은 한국 100억원·미국 $30M.
※ 거래대금은 **최근 20거래일 평균**(업계 표준; `engine.TRADING_AVG_DAYS`). 현재가·시총은 최근 거래일 종가(EOD). 하루치→평균화로 거래일별 변동이 완화됨(과거 '당일 거래대금' 대비). 시세 기준=최근 확정 거래일 EOD(장중 실시간 불필요).
※ 코스닥 명단 **1,816/1,816 전량 적재 완료**(2026-06-11).

| 시장 | 대상 | 유동성 | 재무건전 | **최종** | 산출 |
|---|---|---|---|---|---|
| 코스피 | 835 | 204 | 49 | **17** | dashboards/dashboard_kospi.html |
| 코스닥 | 1,816 | 200 | 62 | **19** | dashboards/dashboard_kosdaq.html |
| 미국 S&P500 | 499 | 499 | 108 | **52** | dashboards/dashboard_us.html |
| 미국 전체(거래소 상장) | 2,343 | 1,664 | 344 | **113** | dashboards/dashboard_us_all.html |

재실행(재무=분기 갱신, 주가·밸류=매 거래일):
```powershell
cd d:\Agent_Project\auto-financial-filter
py run_kospi_quarterly.py     # 코스피
py run_kosdaq_quarterly.py    # 코스닥
py run_us_quarterly.py        # 미국 S&P500
py run_us_all_quarterly.py    # 미국 전체(S&P500 + 유동성통과 확장)
```

## 3. 폴더 구조

```
engine.py                  ★ 공유 엔진 = 기준·게이트·재무엔진 단일 출처 ★
run_kospi_quarterly.py     코스피 진입점 (+ KR 시세 fetch_krx_marcap·렌더)
run_kosdaq_quarterly.py    코스닥 진입점 (run_kospi.main 재사용, index만 다름)
run_us_quarterly.py        미국 S&P500 진입점 (+ US 시세 bulk fetch·렌더)
run_us_all_quarterly.py    미국 전체 진입점 (run_us.main 재사용, 명단 합집합)
screen_us_liquidity.py     미국 확장: EDGAR 수집 전 거래대금 선필터
market_cache.py            시세 캐시(market_cache.db)·라이브 실패 시 직전값 폴백·시총 이월
refresh_prices.py          시세만 갱신(거래일 단위 EOD): KR 자동(launch)·US 버튼(app)·거래일 인지 스킵
app.py                     ★ 로컬 인터랙티브 앱 = 기준 슬라이더 실시간 재스크리닝·통과만 표시 (+미국 🔄시세 새로고침) ★
launch.py                  독립 창 런처(pywebview): 한국 시세 자동 갱신→streamlit 기동→스플래시 창→앱
재무스크리너.bat            더블클릭 진입점(pythonw, 콘솔·브라우저 없이)
.streamlit/config.toml     토스 블루 테마(앱 위젯 강조색)
dashboards/                결과 HTML(공유 스냅샷, git 추적)
results/                   xlsx·csv 산출물 (gitignore)
legacy/                    옛 '연간' 프레임워크(auto_financial_filter 패키지·tests·docs) — 미사용·보존
```

`run_*.py`는 **engine.py를 import**하고 시장별 부분(시세 출처·통화 표시·거래대금 기준)만 각자 둔다.

## 4. 필터 기준 — engine.py 한 곳 (한·미 이원화)

**기준을 바꾸려면 [engine.py]만 수정**(상수 + `KR_CRITERIA`/`US_CRITERIA` 프로파일 + `screen()`).
한국은 `KR_CRITERIA`(원래 엄격 기준), 미국은 `US_CRITERIA`(일부 토글). 거래대금 기준은 시장별 통화라 run 스크립트에(KRW=`MIN_TRADING_KRW`, USD=`MIN_TRADING_USD`) 표시용 별칭을 두고 `screen()`에 프로파일을 넘긴다.

7기준(한국=원래 엄격) + `자본총계>0` 게이트:

1. 거래대금(최근 20거래일 평균) ≥ 100억원(미국 $30M)  2. 부채비율 < 200%  3. 매출성장 YoY ≥ 10%  4. TTM 영업현금 > 0
5. TTM 영업이익률 ≥ 10%  6. 이익피크(최근 4분기 영업이익=과거 최고)  7. 원가율 개선  (+ 자본총계 > 0)

**미국만 다른 점**(`US_CRITERIA`, 문서 [기준_미국.md]): 거래대금 $30M · ⑦원가율 면제 · ⑥피크 16분기↑ 이력 요구 · 자본총계≤0이어도 이익잉여금>0이면 통과(자사주매입 우량주) · 이력 최근 20분기(5년)로 절단(`RECENT_QUARTERS=20`, '피크' 비교창을 한국과 동일하게).

판단 원칙: 규모·수익성=TTM(4분기 합), 성장=YoY, 분기값=누적차감 환산.

## 5. 데이터 파이프라인 (옆 프로젝트)

재무는 **`d:\Agent_Project\dart-audit-extractor`의 `screener.db`(`financials_q`)**를 읽기전용 사용. 수집기 코드도 거기:
- 한국: `collect_quarterly.py`(DART) + `build_kospi/kosdaq_universe.py`
- 미국: `collect_us.py`(SEC EDGAR companyfacts, corp_code=CIK) + `build_us_universe.py`(S&P500) / `build_us_all_universe.py`(전체 거래소)
- 미국 확장 순서(유동성 선필터 후 수집): build_us_all_universe → `screen_us_liquidity.py`(거래대금≥$10M) → `collect_us.py --index us_liquid_index.json` → `run_us_all_quarterly.py`

시세: 한국=KRX 일별 CSV(FDR 캐시 경로), 미국=yfinance bulk. **거래대금=최근 20거래일 평균(EOD), 현재가·시총=최근 거래일 종가.** 둘 다 `market_cache`로 폴백. `재무스크리너.bat` 실행 시 **한국 시세 자동 갱신**(거래일 인지→이미 최신이면 스킵), **미국은 앱 '🔄 시세 새로고침' 버튼**(둘 다 `refresh_prices.py`).

## 6. 협업 규칙

- **판단은 사용자(Hanna), 코드·데이터·구조화는 Claude.** "무엇이 필요한가"는 사용자 주도.
- 사용자는 **업무 맥락 설계 역량**이 강점. 코드 줄 단위보다 **의사결정에 필요한 형태**로 전달.
- 제안/기획/개선안은 **실행 전 텍스트로 계획을 먼저 제시하고 승인받은 뒤 실행.**
- 근거 있는 판단은 사용자 의견과 충돌해도 물러서지 말 것. 단 솔직하게, 사탕발림 없이.
- **최소 변경 원칙**: 요청 범위 밖 기능·추상화·"유연성" 추가 금지.
- **외과적 수정**: 내가 만든 잔해만 치운다. 인접 코드 임의 개선·리팩터 금지(발견 시 알리되 삭제는 지시받고).
- **git/push는 명시 지시 때만.** 리모트: 스크리너 `Hanna-start/auto-financial-filter`, 수집기 `Hanna-start/dart-audit-extractor`.

## 7. 후순위·보류

- ✅ 코스닥 전량 적재 완료(2026-06-11): 잔여 504개 수집(ok 12,269·empty 4,867·**error 0**) → **1,816/1,816**. `run_kosdaq_quarterly.py` 재실행으로 대시보드 반영(최종 12→20). 향후 신규 상장분만 `collect_quarterly.py --index data/kosdaq_index.json` 재실행 시 증분 추가(나머지 skip).
- 모멘텀(4단계) 보류(사용자 결정): 주가추세 휴리스틱이라 펀더멘털과 성격 다름. 이 스크리너는 backward-looking, 미래 판단은 사용자 몫.
- ✅ 인터랙티브 앱 완료(2026-06-11): `app.py`+`launch.py`+`재무스크리너.bat`. 기준 슬라이더 실시간 재스크리닝·통과만·독립 창(pywebview)·오프라인(market_cache)·디스크 캐시. 실행=`재무스크리너.bat` 더블클릭(또는 `streamlit run app.py`). 상세·성능개선 과정은 메모리 [[project-interactive-app]]. 남은 확장: 이익피크·영업현금 on/off 토글(engine.py 플래그 2개), 바탕화면 바로가기.
- ✅ 거래대금 N일 평균(2026-06-12): 하루치→**최근 20거래일 평균**(업계 표준, `engine.TRADING_AVG_DAYS=20`; 60일=3개월로 한 줄 변경 가능). 임계(100억/$30M) 유지, 통과 수 소폭 변동(코스피13→17·코스닥20→19·미국전체112→113·S&P52 불변). 근거·검증은 메모리 [[project-kospi-quarterly]].
- ✅ 시세 거래일 단위 EOD 갱신(2026-06-12): `재무스크리너.bat` 실행 시 한국 자동 갱신(거래일 인지→이미 최신이면 스킵·빠른 실행), 미국은 앱 '🔄 시세 새로고침' 버튼(수천 종목이라 수동). `refresh_prices.py`. 시총은 시세만 갱신 시 `market_cache` 이월(같은날 보존+직전일 carry-forward 2겹)로 유지.
- ✅ 미국 시총 결측 해소(2026-06-12): `fetch_marcaps` 견고화(재시도+현재가×발행주식수 폴백)+`market_cache.update_marcap`로 캐시 반영 → 앱·대시보드 미국 PER/PBR 표시(잔여 '—'는 시총 아닌 순이익 데이터 이슈).
- 토스 API: ✅ 탐색 종결(2026-06-15) — 재무 통과 종목은 위험회사 확률 ~0이라 토스 위험배지/게이트 무의미. 상세 메모리 [[project-toss-api]].
- 기준 개선(예정): engine.py에서 단일 수정으로 진행.
