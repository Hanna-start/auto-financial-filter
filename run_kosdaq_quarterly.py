#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""코스닥 분기 스크리너 — 실제 DART 분기 재무(financials_q) 기반.

코스피판(run_kospi_quarterly.py)의 검증된 엔진(누적차감·TTM·YoY·필터·렌더)을 그대로
재사용하고, 대상 시장만 코스닥으로 바꾼 별도 실행 파일.

코스피와의 차이(전부 main()의 파라미터로 처리):
  - 주가·거래대금·시총 = FinanceDataReader('KOSDAQ')
  - 대상 명단·회사명·종목코드 = dart-audit-extractor/data/kosdaq_index.json
    (financials_q에 코스피·코스닥이 섞여 있어도 이 명단으로 코스닥만 분리)
  - 기준은 코스피와 동일(원래 재무선배 엄격)

산출: 콘솔 리포트 + 코스닥_분기_결과_*.xlsx + dashboard_kosdaq.html
사용: py run_kosdaq_quarterly.py
"""
from run_kospi_quarterly import main

KOSDAQ_INDEX = "D:/Agent_Project/dart-audit-extractor/data/kosdaq_index.json"

if __name__ == "__main__":
    main(xlsx_prefix="코스닥_분기_결과",
         dash="dashboard_kosdaq.html",
         title="코스닥 분기 스크리너 결과",
         market="KOSDAQ",
         index_json=KOSDAQ_INDEX)
