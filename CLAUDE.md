# CLAUDE.md — 프로젝트 컨텍스트 & 협업 메모리

> Claude가 이 폴더를 열 때 가장 먼저 읽는 맥락 파일. **현재 상태 + 구조 + 실행법 + 협업 규칙**만 둔다.
> 세션별 히스토리·의사결정 이력은 메모리([[project-kospi-quarterly]])와 git 로그에 보존.

## 1. 목적

'재무선배'가 공개한 펀더멘털 선별 기준을 코드로 자동화한 **종목 스크리너**.
한국(코스피·코스닥) + 미국(S&P500 + 전체 거래소 상장)을 **실데이터**로 객관·일관 선별.

## 2. 현재 상태 (코스닥 2026-06-11·그 외 06-10) — 세 시장 완성·실행 완료

대시보드 깔때기(대상 → ①유동성 → ②재무건전 → ③최종). 유동성은 한국 100억원·미국 $30M.
※ 한국 최종 수는 **거래일별 변동**(유동성=당일 거래대금) — 하락장엔 줄어든다. 미국은 재무 기반이라 안정(52/112).
※ 코스닥 명단 **1,312/1,816 적재**(잔여 504, §7) — 신규분은 시총 하위권이라 유동성에서 대부분 탈락.

| 시장 | 대상 | 유동성 | 재무건전 | **최종** | 산출 |
|---|---|---|---|---|---|
| 코스피 | 835 | 176 | 43 | **13** | dashboards/dashboard_kospi.html |
| 코스닥 | 1,312 | 126 | 39 | **12** | dashboards/dashboard_kosdaq.html |
| 미국 S&P500 | 499 | 499 | 108 | **52** | dashboards/dashboard_us.html |
| 미국 전체(거래소 상장) | 2,343 | 1,670 | 343 | **112** | dashboards/dashboard_us_all.html |

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
market_cache.py            시세 캐시(market_cache.db)·라이브 실패 시 직전값 폴백
dashboards/                결과 HTML(공유 스냅샷, git 추적)
results/                   xlsx·csv 산출물 (gitignore)
legacy/                    옛 '연간' 프레임워크(auto_financial_filter 패키지·tests·docs) — 미사용·보존
```

`run_*.py`는 **engine.py를 import**하고 시장별 부분(시세 출처·통화 표시·거래대금 기준)만 각자 둔다.

## 4. 필터 기준 — engine.py 한 곳 (한·미 이원화)

**기준을 바꾸려면 [engine.py]만 수정**(상수 + `KR_CRITERIA`/`US_CRITERIA` 프로파일 + `screen()`).
한국은 `KR_CRITERIA`(원래 재무선배 엄격), 미국은 `US_CRITERIA`(일부 토글). 거래대금 기준은 시장별 통화라 run 스크립트에(KRW=`MIN_TRADING_KRW`, USD=`MIN_TRADING_USD`) 표시용 별칭을 두고 `screen()`에 프로파일을 넘긴다.

7기준(한국=원래 재무선배 엄격) + `자본총계>0` 게이트:

1. 거래대금 ≥ 100억원(미국 $30M)  2. 부채비율 < 200%  3. 매출성장 YoY ≥ 10%  4. TTM 영업현금 > 0
5. TTM 영업이익률 ≥ 10%  6. 이익피크(최근 4분기 영업이익=과거 최고)  7. 원가율 개선  (+ 자본총계 > 0)

**미국만 다른 점**(`US_CRITERIA`, 문서 [기준_미국.md]): 거래대금 $30M · ⑦원가율 면제 · ⑥피크 16분기↑ 이력 요구 · 자본총계≤0이어도 이익잉여금>0이면 통과(자사주매입 우량주) · 이력 최근 20분기(5년)로 절단(`RECENT_QUARTERS=20`, '피크' 비교창을 한국과 동일하게).

판단 원칙: 규모·수익성=TTM(4분기 합), 성장=YoY, 분기값=누적차감 환산.

## 5. 데이터 파이프라인 (옆 프로젝트)

재무는 **`d:\Agent_Project\dart-audit-extractor`의 `screener.db`(`financials_q`)**를 읽기전용 사용. 수집기 코드도 거기:
- 한국: `collect_quarterly.py`(DART) + `build_kospi/kosdaq_universe.py`
- 미국: `collect_us.py`(SEC EDGAR companyfacts, corp_code=CIK) + `build_us_universe.py`(S&P500) / `build_us_all_universe.py`(전체 거래소)
- 미국 확장 순서(유동성 선필터 후 수집): build_us_all_universe → `screen_us_liquidity.py`(거래대금≥$10M) → `collect_us.py --index us_liquid_index.json` → `run_us_all_quarterly.py`

시세: 한국=KRX 일별 CSV(FDR 캐시 경로, 최근 거래일로 walk-back), 미국=yfinance bulk. 둘 다 `market_cache`로 폴백.

## 6. 협업 규칙

- **판단은 사용자(Hanna), 코드·데이터·구조화는 Claude.** "무엇이 필요한가"는 사용자 주도.
- 사용자는 **업무 맥락 설계 역량**이 강점. 코드 줄 단위보다 **의사결정에 필요한 형태**로 전달.
- 제안/기획/개선안은 **실행 전 텍스트로 계획을 먼저 제시하고 승인받은 뒤 실행.**
- 근거 있는 판단은 사용자 의견과 충돌해도 물러서지 말 것. 단 솔직하게, 사탕발림 없이.
- **최소 변경 원칙**: 요청 범위 밖 기능·추상화·"유연성" 추가 금지.
- **외과적 수정**: 내가 만든 잔해만 치운다. 인접 코드 임의 개선·리팩터 금지(발견 시 알리되 삭제는 지시받고).
- **git/push는 명시 지시 때만.** 리모트: 스크리너 `Hanna-start/auto-financial-filter`, 수집기 `Hanna-start/dart-audit-extractor`.

## 7. 후순위·보류

- 코스닥 잔여 수집: **504개**(1,312/1,816 적재, 2026-06-11). 다음 배치 `py screener/collect_quarterly.py --index data/kosdaq_index.json --limit 1816`(한도 리셋 후, ~17k콜). 끝나면 `run_kosdaq_quarterly.py` 재실행.
- 모멘텀(4단계) 보류(사용자 결정): 주가추세 휴리스틱이라 펀더멘털과 성격 다름. 이 스크리너는 backward-looking, 미래 판단은 사용자 몫.
- Streamlit 인터랙티브 앱(미착수): 기준을 슬라이더로 실시간 재스크리닝.
- 기준 개선(예정): engine.py에서 단일 수정으로 진행.
