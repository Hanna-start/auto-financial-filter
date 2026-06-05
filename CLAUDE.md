# CLAUDE.md — 프로젝트 컨텍스트 & 협업 메모리

> 이 파일은 Claude가 이 폴더를 열 때 가장 먼저 읽는 맥락 파일입니다.
> 작업을 다시 시작할 때 처음부터 설명하지 않아도 되도록, 목적·현황·다음 할 일·협업 규칙을 기록합니다.
> 최초 작성: 2026-06-05

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

---

## 6. 기술 메모

- 패키지: `auto_financial_filter/` (~5,200 LOC). 레이어: models → data_access → filters → pipeline → cli/utils
- 진짜 경로(권장): 가격=yfinance(`YFinanceKoreanAdapter`) / 재무=screener.db(`ScreenerDBAdapter`), `HybridDataAccessManager`로 결합. 진입점 `run_listed_screener.py`.
  - (가짜 `alternative`(WebScraping) 폴백은 제거됨. 남은 비실데이터 경로는 테스트·데모용 `mock_adapters`뿐.)
- 정식 진입점 `cli.py`는 1단계(유동성)에서 멈춰 방치됨(미해결). 실질 진입점은 루트의 `run_listed_screener.py`.
- 테스트: `tests/` 24파일 109함수, pytest + Hypothesis. 설계서 13개 correctness property와 매핑.
- 스펙: `.kiro/specs/financial-stock-filter/` (requirements/design/tasks). 단 `.gitignore`에 포함됨.
