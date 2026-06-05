#!/usr/bin/env python3
"""
완화된 기준으로 재무 건전성 기반 종목 필터링 실행
Relaxed criteria version for more realistic results
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from run_real_data_analysis import main as original_main
from auto_financial_filter.config import FilterConfig
import logging

def main():
    """Main function with relaxed criteria."""
    
    print("🚀 재무 건전성 기반 종목 필터링 시스템 - 완화된 기준")
    print("=" * 70)
    
    # 더 현실적이고 완화된 기준
    global config
    config = FilterConfig(
        min_trading_volume_krw=1_000_000_000,    # 10억 KRW (더 완화)
        trading_volume_period_days=30,           # 30일 평균
        max_debt_ratio_percent=300.0,            # 부채비율 300% 이하 (완화)
        min_revenue_growth_percent=0.0,          # 매출성장률 0% 이상 (완화)
        cash_flow_quarters=4,                    # 4분기 현금흐름 분석
        min_operating_margin_percent=0.0,        # 영업이익률 0% 이상 (완화)
        profit_trend_years=4,                    # 4년 수익성 트렌드
        cogs_trend_quarters=6,                   # 6분기 매출원가 트렌드
        data_cache_enabled=True,                 # 캐싱 활성화
        data_cache_ttl_hours=24,                 # 24시간 캐시
        api_retry_attempts=3,                    # 3회 재시도
        api_timeout_seconds=30,                  # 30초 타임아웃
        verbose_output=True,                     # 상세 출력
        log_level="INFO"
    )
    
    print(f"📊 완화된 필터링 기준:")
    print(f"   💰 최소 거래량: {config.min_trading_volume_krw:,} KRW (완화)")
    print(f"   💳 최대 부채비율: {config.max_debt_ratio_percent}% (완화)")
    print(f"   📊 최소 매출성장률: {config.min_revenue_growth_percent}% (완화)")
    print(f"   💹 최소 영업이익률: {config.min_operating_margin_percent}% (완화)")
    print()
    
    # 원본 main 함수의 로직을 사용하되 config만 교체
    return original_main()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)