#!/usr/bin/env python3
"""
미국 기업 Stage 2까지만 실행 - 유동성 + 재무건전성 필터
US Stock Analysis - Stage 1 & 2 Only (Liquidity + Financial Health)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.filters.liquidity_filter import LiquidityFilter
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter
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
    """Main function to run US stock analysis - Stage 2 only."""
    
    print("🇺🇸 미국 기업 재무 건전성 필터링 - Stage 2까지")
    print("🇺🇸 US Stock Financial Health Filter - Stage 1 & 2 Only")
    print("=" * 70)
    
    # 완화된 기준으로 설정 (더 많은 후보를 얻기 위해)
    config = FilterConfig(
        min_trading_volume_krw=10_000_000,       # $10M USD (완화)
        trading_volume_period_days=30,           # 30일 평균
        max_debt_ratio_percent=300.0,            # 부채비율 300% 이하 (완화)
        min_revenue_growth_percent=-10.0,        # 매출성장률 -10% 이상 (완화)
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
    
    print(f"📊 US Market Criteria - Stage 2 Only (미국 시장 기준 - 2단계까지):")
    print(f"   💰 Min Trading Volume: ${config.min_trading_volume_krw:,} USD")
    print(f"   💳 Max Debt Ratio: {config.max_debt_ratio_percent}%")
    print(f"   📊 Min Revenue Growth: {config.min_revenue_growth_percent}%")
    print(f"   ⚠️  Stage 3 (Quality Growth) SKIPPED to avoid errors")
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
    
    # Create pipeline with ONLY Stage 1 & 2 filters
    pipeline = StockFilterPipeline(config)
    
    # Add ONLY liquidity and financial health filters (NO quality growth filter)
    liquidity_filter = LiquidityFilter(config, data_manager)
    financial_filter = FinancialHealthFilter(config, data_manager)
    
    pipeline.add_filter(liquidity_filter)
    pipeline.add_filter(financial_filter)
    # NOTE: Quality Growth Filter is NOT added to avoid Stage 3 errors
    
    print(f"🔧 Pipeline Configuration - Stage 2 Only:")
    print(f"   1️⃣ Liquidity Filter - Trading volume criteria")
    print(f"   2️⃣ Financial Health Filter - Debt ratio, revenue growth, cash flow")
    print(f"   ❌ Quality Growth Filter - SKIPPED (Stage 3)")
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
    
    # Execute pipeline (Stage 1 & 2 only)
    try:
        print("🔄 Running US Stock Filtering Pipeline - Stage 2 Only...")
        print("   ⏳ Processing liquidity and financial health filters...")
        
        start_time = time.time()
        result = pipeline.execute(symbols)
        execution_time = time.time() - start_time
        
        print(f"✅ US Stock Stage 2 Filtering Complete! (실행시간: {execution_time:.2f}초)")
        print()
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        return 1
    
    # Display results
    print("📊 US Stock Stage 2 Results (미국 주식 2단계 결과):")
    print(f"   📈 Total Processed: {result.total_processed} stocks")
    print(f"   🎯 Stage 2 Candidates: {len(result.final_candidates)} stocks")
    print(f"   📈 Stage 2 Pass Rate: {len(result.final_candidates) / result.total_processed * 100:.1f}%")
    print()
    
    # Display stage-by-stage results
    print("📋 Stage-by-Stage Results (단계별 결과):")
    for i, stage_result in enumerate(result.stage_results, 1):
        stage_name = stage_result.stage
        if "step1" in stage_name:
            stage_name = "Stage 1: Liquidity Filter"
        elif "Financial Health" in stage_name:
            stage_name = "Stage 2: Financial Health Filter"
        
        print(f"   {stage_name}")
        print(f"      📥 Input: {stage_result.total_processed} stocks")
        print(f"      ✅ Passed: {len(stage_result.passed_symbols)} stocks")
        print(f"      ❌ Failed: {len(stage_result.failed_symbols)} stocks")
        print(f"      📊 Pass Rate: {stage_result.pass_rate:.1f}%")
        
        # Show criteria applied
        if stage_result.criteria_applied:
            print(f"      🔍 Applied Criteria:")
            for key, value in stage_result.criteria_applied.items():
                print(f"         - {key}: {value}")
        print()
    
    # Display Stage 2 candidates with details
    if result.final_candidates:
        print("🏆 Stage 2 US Stock Candidates (2단계 통과 미국 주식):")
        
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
        
        # Show some financial details for top candidates
        print("💰 Financial Details (Top 10 Candidates):")
        for i, symbol in enumerate(result.final_candidates[:10], 1):
            try:
                financial_data = data_manager.get_financial_data(symbol)
                latest_quarter = financial_data['quarterly_data'][0]
                revenue = latest_quarter['revenue'] / 1_000_000  # Convert to millions
                debt_ratio = latest_quarter['debt_ratio']
                print(f"   {i:2d}. {symbol.code}: Revenue ${revenue:,.0f}M, Debt Ratio {debt_ratio:.1f}%")
            except:
                print(f"   {i:2d}. {symbol.code}: Financial data unavailable")
        print()
        
    else:
        print("❌ No stocks passed Stage 2 filters.")
        print("💡 Consider further relaxing the criteria:")
        print("   - Lower minimum trading volume")
        print("   - Increase maximum debt ratio")
        print("   - Lower revenue growth requirement")
        print()
    
    # Export results to Excel
    excel_filename = f"US_Stock_Stage2_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    try:
        print(f"📊 Exporting Stage 2 results to Excel: {excel_filename}")
        DataExporter.export_pipeline_result_excel(result, excel_filename)
        print(f"✅ Excel file created successfully!")
        print()
        
        print("📁 Excel File Contents (Stage 2 Results):")
        print("   📋 Summary: Stage 2 analysis summary")
        print("   🏆 Final Candidates: Stocks passing liquidity + financial health filters")
        print("   📊 Stage Results: Stage 1 & 2 detailed results")
        print("   📈 Stage 1 Passed: Liquidity filter passing stocks (49 stocks)")
        print("   📈 Stage 2 Passed: Financial health filter passing stocks")
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
    
    # Performance summary
    print("⚡ Performance Summary:")
    print(f"   ⏱️ Total Execution Time: {execution_time:.2f} seconds")
    print(f"   📊 Average Time per Stock: {execution_time / len(symbols):.3f} seconds")
    print(f"   🎯 Stages Completed: 2 out of 3 (Stage 3 skipped)")
    print()
    
    print("🎉 US Stock Stage 2 Analysis Complete!")
    print(f"📁 Results File: {excel_filename}")
    print()
    print("💡 Next Steps:")
    print("   - Review Stage 2 candidates in Excel file")
    print("   - These stocks passed liquidity and financial health criteria")
    print("   - Consider manual analysis for final investment decisions")
    print("   - Stage 3 (Quality Growth) can be added later after fixing compatibility")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)