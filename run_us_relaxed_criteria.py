#!/usr/bin/env python3
"""
완화된 기준으로 미국 기업 분석 - 더 많은 후보를 찾기 위해
US Stock Analysis with Relaxed Criteria - To find more candidates
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.filters.liquidity_filter import LiquidityFilter
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter
from auto_financial_filter.filters.quality_growth_filter import QualityGrowthFilter
from auto_financial_filter.utils.export import DataExporter
from auto_financial_filter.data_access.us_adapters import USDataAccessManager
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function with relaxed criteria for US stocks."""
    
    print("🇺🇸 미국 기업 재무 건전성 필터링 - 완화된 기준")
    print("🇺🇸 US Stock Financial Health Filter - Relaxed Criteria")
    print("=" * 70)
    
    # 더 현실적이고 완화된 기준 (미국 시장에 맞게 조정)
    config = FilterConfig(
        min_trading_volume_krw=10_000_000,       # $10M USD (매우 완화)
        trading_volume_period_days=30,           # 30일 평균
        max_debt_ratio_percent=400.0,            # 부채비율 400% 이하 (완화)
        min_revenue_growth_percent=-5.0,         # 매출성장률 -5% 이상 (완화 - 약간의 감소 허용)
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
    
    print(f"📊 Relaxed US Market Criteria (완화된 미국 시장 기준):")
    print(f"   💰 Min Trading Volume: ${config.min_trading_volume_krw:,} USD (매우 완화)")
    print(f"   💳 Max Debt Ratio: {config.max_debt_ratio_percent}% (완화)")
    print(f"   📊 Min Revenue Growth: {config.min_revenue_growth_percent}% (완화 - 약간의 감소 허용)")
    print(f"   💹 Min Operating Margin: {config.min_operating_margin_percent}% (완화)")
    print()
    
    # Initialize US data manager
    try:
        data_manager = USDataAccessManager(config)
        
        print(f"🔗 Data Sources: US Market (yfinance + SEC estimates)")
        
        # Check data source availability
        availability = data_manager.get_availability_status()
        print(f"📡 US Data Source Status:")
        for source, available in availability.items():
            status = "✅ Available" if available else "❌ Not Available"
            print(f"   - {source}: {status}")
        print()
        
    except Exception as e:
        logger.error(f"US data source initialization failed: {e}")
        return 1
    
    # Create and configure pipeline
    pipeline = StockFilterPipeline(config)
    
    # Add filters
    liquidity_filter = LiquidityFilter(config, data_manager)
    financial_filter = FinancialHealthFilter(config, data_manager)
    quality_filter = QualityGrowthFilter(config, data_manager)
    
    pipeline.add_filter(liquidity_filter)
    pipeline.add_filter(financial_filter)
    pipeline.add_filter(quality_filter)
    
    print(f"🔧 Pipeline Configuration (완화된 기준 파이프라인):")
    print(f"   1️⃣ Liquidity Filter - Very low volume requirement")
    print(f"   2️⃣ Financial Health Filter - Relaxed debt and growth criteria")
    print(f"   3️⃣ Quality Growth Filter - Minimal profitability requirement")
    print()
    
    # Get US stock symbols
    try:
        print("📈 Loading US stock data...")
        symbols = data_manager.get_all_symbols()
        print(f"✅ Loaded {len(symbols)} US stocks successfully")
        
        # Display sample symbols
        print(f"📋 Sample US Stocks (first 10):")
        for i, symbol in enumerate(symbols[:10], 1):
            print(f"   {i:2d}. {symbol.code} - {symbol.name} ({symbol.market})")
        if len(symbols) > 10:
            print(f"   ... and {len(symbols) - 10} more stocks")
        print()
        
    except Exception as e:
        logger.error(f"Failed to load US stock data: {e}")
        return 1
    
    # Execute pipeline
    try:
        print("🔄 Running Relaxed US Stock Filtering Pipeline...")
        print("   ⏳ This may take several minutes...")
        
        start_time = time.time()
        result = pipeline.execute(symbols)
        execution_time = time.time() - start_time
        
        print(f"✅ Relaxed US Stock Filtering Complete! (실행시간: {execution_time:.2f}초)")
        print()
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        return 1
    
    # Display results
    print("📊 Relaxed US Stock Filtering Results (완화된 기준 결과):")
    print(f"   📈 Total Processed: {result.total_processed} stocks")
    print(f"   🎯 Final Candidates: {len(result.final_candidates)} stocks")
    print(f"   📈 Overall Pass Rate: {len(result.final_candidates) / result.total_processed * 100:.1f}%")
    print()
    
    # Display stage-by-stage results
    print("📋 Stage-by-Stage Results:")
    for i, stage_result in enumerate(result.stage_results, 1):
        stage_name = stage_result.stage
        if "step1" in stage_name:
            stage_name = "Stage 1: Liquidity Filter (Relaxed)"
        elif "Financial Health" in stage_name:
            stage_name = "Stage 2: Financial Health Filter (Relaxed)"
        elif "final_candidate" in stage_name:
            stage_name = "Stage 3: Quality Growth Filter (Relaxed)"
        
        print(f"   {stage_name}")
        print(f"      📥 Input: {stage_result.total_processed} stocks")
        print(f"      ✅ Passed: {len(stage_result.passed_symbols)} stocks")
        print(f"      ❌ Failed: {len(stage_result.failed_symbols)} stocks")
        print(f"      📊 Pass Rate: {stage_result.pass_rate:.1f}%")
        print()
    
    # Display final candidates with details
    if result.final_candidates:
        print("🏆 Final US Stock Candidates (완화된 기준 통과 종목):")
        
        # Group by sector if possible
        sector_groups = {}
        for symbol in result.final_candidates:
            try:
                market_data = data_manager.get_market_data(symbol)
                sector = market_data.get('sector', 'Unknown')
                if sector not in sector_groups:
                    sector_groups[sector] = []
                sector_groups[sector].append(symbol)
            except:
                if 'Unknown' not in sector_groups:
                    sector_groups['Unknown'] = []
                sector_groups['Unknown'].append(symbol)
        
        # Display by sector
        for sector, symbols_in_sector in sector_groups.items():
            print(f"\n   📊 {sector} Sector:")
            for i, symbol in enumerate(symbols_in_sector, 1):
                print(f"      {i:2d}. {symbol.code} - {symbol.name} ({symbol.market})")
        
        print(f"\n📊 Sector Summary:")
        for sector, symbols_in_sector in sorted(sector_groups.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"   - {sector}: {len(symbols_in_sector)} stocks")
        print()
        
    else:
        print("❌ Even with relaxed criteria, no stocks passed all filters.")
        print("💡 This might indicate:")
        print("   - Very strict quality requirements")
        print("   - Market conditions affecting most stocks")
        print("   - Need for further criteria adjustment")
        print()
    
    # Export results to Excel
    excel_filename = f"US_Stock_Relaxed_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    try:
        print(f"📊 Exporting relaxed criteria results to Excel: {excel_filename}")
        DataExporter.export_pipeline_result_excel(result, excel_filename)
        print(f"✅ Excel file created successfully!")
        print()
        
        print("📁 Excel File Contents:")
        print("   📋 Summary: Analysis summary with relaxed criteria")
        print("   🏆 Final Candidates: Stocks passing relaxed filters")
        print("   📊 Stage Results: Detailed stage-by-stage results")
        print("   📈 Stage Details: Individual stage passing stocks")
        print()
        
    except Exception as e:
        logger.error(f"Excel file creation failed: {e}")
        print("💡 Trying CSV format instead...")
        
        try:
            csv_filename = excel_filename.replace('.xlsx', '.csv')
            DataExporter.export_pipeline_result_csv(result, csv_filename)
            print(f"✅ CSV file created: {csv_filename}")
        except Exception as csv_e:
            logger.error(f"CSV file creation also failed: {csv_e}")
    
    # Performance and comparison summary
    print("⚡ Performance Summary:")
    print(f"   ⏱️ Total Execution Time: {execution_time:.2f} seconds")
    print(f"   📊 Average Time per Stock: {execution_time / len(symbols):.3f} seconds")
    print()
    
    print("🎉 Relaxed US Stock Analysis Complete!")
    print(f"📁 Results File: {excel_filename}")
    print()
    print("💡 Comparison with Standard Criteria:")
    print("   - This analysis uses much more lenient criteria")
    print("   - Suitable for finding opportunities in challenging markets")
    print("   - Results should be further analyzed for investment decisions")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)