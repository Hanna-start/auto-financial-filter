#!/usr/bin/env python3
"""
Debug US Stage 3 Quality Growth Filter
미국 주식 Stage 3 품질성장 필터 디버그
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.filters.quality_growth_filter import QualityGrowthFilter
from auto_financial_filter.data_access.us_adapters import USDataAccessManager
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Debug Stage 3 filtering for US stocks."""
    
    print("🔍 US Stage 3 Quality Growth Filter Debug")
    print("=" * 50)
    
    # Very relaxed config for debugging
    config = FilterConfig(
        min_trading_volume_krw=1_000_000,        # $1M USD (very low)
        trading_volume_period_days=30,
        max_debt_ratio_percent=500.0,            # 500% (very high)
        min_revenue_growth_percent=-20.0,        # -20% (very low)
        cash_flow_quarters=4,
        min_operating_margin_percent=-10.0,      # -10% (allow losses)
        profit_trend_years=4,
        cogs_trend_quarters=6,
        data_cache_enabled=True,
        data_cache_ttl_hours=24,
        api_retry_attempts=3,
        api_timeout_seconds=30,
        verbose_output=True,
        log_level="DEBUG"
    )
    
    # Initialize data manager
    data_manager = USDataAccessManager(config)
    
    # Get a few test symbols
    all_symbols = data_manager.get_all_symbols()
    test_symbols = all_symbols[:5]  # Test first 5 symbols
    
    print(f"🧪 Testing Stage 3 with {len(test_symbols)} symbols:")
    for i, symbol in enumerate(test_symbols, 1):
        print(f"   {i}. {symbol.code} - {symbol.name}")
    print()
    
    # Create quality growth filter
    quality_filter = QualityGrowthFilter(config, data_manager)
    
    # Test each symbol individually
    for symbol in test_symbols:
        print(f"\n🔍 Analyzing {symbol.code} - {symbol.name}")
        print("-" * 40)
        
        try:
            # Get financial data
            financial_data = data_manager.get_financial_data(symbol)
            print(f"📊 Financial Data Structure:")
            if isinstance(financial_data, dict):
                print(f"   Type: Dictionary")
                print(f"   Keys: {list(financial_data.keys())}")
                if 'quarterly_data' in financial_data:
                    print(f"   Quarters: {len(financial_data['quarterly_data'])}")
                    # Show first quarter data
                    if financial_data['quarterly_data']:
                        q1 = financial_data['quarterly_data'][0]
                        print(f"   Q1 Data Keys: {list(q1.keys())}")
                        print(f"   Q1 Revenue: ${q1.get('revenue', 0):,.0f}")
                        print(f"   Q1 Operating Profit: ${q1.get('operating_profit', 0):,.0f}")
                        print(f"   Q1 COGS: ${q1.get('cogs', 0):,.0f}")
            
            # Get profitability metrics
            metrics = quality_filter._get_profitability_metrics(symbol)
            
            print(f"\n📈 Profitability Metrics:")
            print(f"   Operating Margin: {metrics.operating_margin:.2f}%")
            print(f"   Is Profit Peak: {metrics.is_profit_peak}")
            print(f"   Operating Profit Trend (16Q): {len(metrics.operating_profit_trend)} values")
            print(f"   COGS Ratio Trend (6Q): {len(metrics.cogs_ratio_trend)} values")
            
            # Show recent profit trend
            recent_4q = metrics.operating_profit_trend[-4:]
            print(f"   Recent 4Q Profits: {[f'${p:,.0f}' for p in recent_4q]}")
            
            # Show COGS trend
            print(f"   COGS Ratios: {[f'{r:.3f}' for r in metrics.cogs_ratio_trend]}")
            
            # Check individual criteria
            margin_ok = metrics.operating_margin >= config.min_operating_margin_percent
            peak_ok = metrics.is_profit_peak
            cogs_trend_ok = quality_filter._analyze_cogs_trend(metrics.cogs_ratio_trend)
            
            print(f"\n✅ Criteria Check:")
            print(f"   Operating Margin >= {config.min_operating_margin_percent}%: {margin_ok} ({metrics.operating_margin:.2f}%)")
            print(f"   Is Profit Peak: {peak_ok}")
            print(f"   COGS Decreasing Trend: {cogs_trend_ok}")
            
            # Show why COGS trend failed
            if not cogs_trend_ok:
                print(f"   COGS Trend Analysis:")
                for i in range(1, len(metrics.cogs_ratio_trend)):
                    prev_ratio = metrics.cogs_ratio_trend[i-1]
                    curr_ratio = metrics.cogs_ratio_trend[i]
                    decreasing = curr_ratio < prev_ratio
                    print(f"     Q{i}: {prev_ratio:.3f} -> {curr_ratio:.3f} {'✅' if decreasing else '❌'}")
            
            overall_pass = margin_ok and peak_ok and cogs_trend_ok
            print(f"\n🎯 Overall Result: {'✅ PASS' if overall_pass else '❌ FAIL'}")
            
        except Exception as e:
            print(f"❌ Error analyzing {symbol.code}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n🔍 Debug Analysis Complete!")
    print(f"💡 Key Insights:")
    print(f"   - Check if profit peak detection is too strict")
    print(f"   - COGS trend requires ALL quarters to decrease")
    print(f"   - Consider adjusting trend analysis logic")


if __name__ == "__main__":
    main()