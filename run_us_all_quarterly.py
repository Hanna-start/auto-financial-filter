#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미국 '전체 거래소 상장(유동성 통과)' 분기 스크리너 — S&P500 확장판.

run_us_quarterly.py의 검증된 엔진(EDGAR 재무·TTM·YoY·필터·렌더)을 그대로 쓰되, 대상 명단만
넓힌 별도 진입점. 한국에서 코스피 다음 코스닥으로 넓힌 것과 같은 의미.

대상 = S&P500(us_index) ∪ S&P500밖 유동성통과(us_liquid_index, 거래대금≥$10M 선필터).
  → 두 명단의 CIK 합집합 중 EDGAR 재무가 적재된 회사만 스크리닝.
  순서 역전: 7천 개 재무를 다 받기 전에 거래대금으로 선필터(screen_us_liquidity.py) → 수집 대상
  2,156개로 축소 → collect_us.py로 재무 수집 → 여기서 펀더멘털 7기준 적용.

산출: 콘솔 + 미국전체_분기_결과_*.xlsx + dashboard_us_all.html
사용: py run_us_all_quarterly.py
"""
from run_us_quarterly import main

US_INDEX = "D:/Agent_Project/dart-audit-extractor/data/us_index.json"
US_LIQUID = "D:/Agent_Project/dart-audit-extractor/data/us_liquid_index.json"

if __name__ == "__main__":
    main(index_paths=[US_INDEX, US_LIQUID],
         label="미국 거래소 상장(유동성통과)",
         title="미국 전체(거래소 상장) 분기 스크리너 결과",
         dash="dashboard_us_all.html",
         xlsx_prefix="미국전체_분기_결과")
