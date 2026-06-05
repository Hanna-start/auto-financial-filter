#!/usr/bin/env python3
"""
미국 기업 재무 건전성 기반 종목 필터링 시스템
US Stock Financial Health Filter System
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

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
    """Main function to run US stock analysis."""
    
    print("🇺🇸 미국 기업 재무 건전성 기반 종목 필터링 시스템")
    print("🇺🇸 US Stock Financial Health Filter System")
    print("=" * 70)
    
    # Create configuration adapted for US market (USD-based)
    config = FilterConfig(
        min_trading_volume_krw=50_000_000,       # $50M USD equivalent (converted from KRW logic)
        trading_volume_period_days=30,           # 30일 평균
        max_debt_ratio_percent=200.0,            # 부채비율 200% 이하
        min_revenue_growth_percent=5.0,          # 매출성장률 5% 이상
        cash_flow_quarters=4,                    # 4분기 현금흐름 분석
        min_operating_margin_percent=5.0,        # 영업이익률 5% 이상
        profit_trend_years=4,                    # 4년 수익성 트렌드
        cogs_trend_quarters=6,                   # 6분기 매출원가 트렌드
        data_cache_enabled=True,                 # 캐싱 활성화
        data_cache_ttl_hours=24,                 # 24시간 캐시
        api_retry_attempts=3,                    # 3회 재시도
        api_timeout_seconds=30,                  # 30초 타임아웃
        verbose_output=True,                     # 상세 출력
        log_level="INFO"
    )
    
    print(f"📊 US Market Filtering Criteria (미국 시장 필터링 기준):")
    print(f"   💰 Min Trading Volume: ${config.min_trading_volume_krw:,} USD")
    print(f"   📈 Volume Period: {config.trading_volume_period_days} days")
    print(f"   💳 Max Debt Ratio: {config.max_debt_ratio_percent}%")
    print(f"   📊 Min Revenue Growth: {config.min_revenue_growth_percent}%")
    print(f"   💹 Min Operating Margin: {config.min_operating_margin_percent}%")
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
    
    # Create and configure pipeline (same as Korean system)
    pipeline = StockFilterPipeline(config)
    
    # Add filters (reusing existing filter logic)
    liquidity_filter = LiquidityFilter(config, data_manager)
    financial_filter = FinancialHealthFilter(config, data_manager)
    quality_filter = QualityGrowthFilter(config, data_manager)
    
    pipeline.add_filter(liquidity_filter)
    pipeline.add_filter(financial_filter)
    pipeline.add_filter(quality_filter)
    
    print(f"🔧 Pipeline Configuration (파이프라인 구성):")
    print(f"   1️⃣ Liquidity Filter (유동성 필터) - Trading volume criteria")
    print(f"   2️⃣ Financial Health Filter (재무건전성 필터) - Debt ratio, revenue growth, cash flow")
    print(f"   3️⃣ Quality Growth Filter (품질성장 필터) - Operating margin, profitability trends")
    print()
    
    # Get US stock symbols
    try:
        print("📈 Loading US stock data (미국 주식 데이터 로딩 중)...")
        symbols = data_manager.get_all_symbols()
        print(f"✅ Loaded {len(symbols)} US stocks successfully")
        
        # Display sample symbols
        print(f"📋 Sample US Stocks (미국 주식 샘플 - first 15):")
        for i, symbol in enumerate(symbols[:15], 1):
            print(f"   {i:2d}. {symbol.code} - {symbol.name} ({symbol.market})")
        if len(symbols) > 15:
            print(f"   ... and {len(symbols) - 15} more stocks")
        print()
        
    except Exception as e:
        logger.error(f"Failed to load US stock data: {e}")
        return 1
    
    # Execute pipeline
    try:
        print("🔄 Running US Stock Filtering Pipeline...")
        print("   ⏳ This may take several minutes for US market analysis...")
        
        start_time = time.time()
        result = pipeline.execute(symbols)
        execution_time = time.time() - start_time
        
        print(f"✅ US Stock Filtering Complete! (실행시간: {execution_time:.2f}초)")
        print()
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        return 1
    
    # Display results
    print("📊 US Stock Filtering Results Summary (미국 주식 필터링 결과 요약):")
    print(f"   📈 Total Processed: {result.total_processed} stocks")
    print(f"   🎯 Final Candidates: {len(result.final_candidates)} stocks")
    print(f"   📈 Overall Pass Rate: {len(result.final_candidates) / result.total_processed * 100:.1f}%")
    print()
    
    # Display stage-by-stage results
    print("📋 Stage-by-Stage Results (단계별 필터링 결과):")
    for i, stage_result in enumerate(result.stage_results, 1):
        stage_name = stage_result.stage
        if "step1" in stage_name:
            stage_name = "Stage 1: Liquidity Filter"
        elif "Financial Health" in stage_name:
            stage_name = "Stage 2: Financial Health Filter"
        elif "final_candidate" in stage_name:
            stage_name = "Stage 3: Quality Growth Filter"
        
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
    
    # Display final candidates
    if result.final_candidates:
        print("🏆 Final US Stock Candidates (최종 미국 주식 후보):")
        for i, symbol in enumerate(result.final_candidates, 1):
            print(f"   {i:2d}. {symbol.code} - {symbol.name} ({symbol.market})")
        print()
        
        # Show sector distribution if available
        sectors = {}
        for symbol in result.final_candidates:
            try:
                market_data = data_manager.get_market_data(symbol)
                sector = market_data.get('sector', 'Unknown')
                sectors[sector] = sectors.get(sector, 0) + 1
            except:
                pass
        
        if sectors:
            print("📊 Sector Distribution (섹터 분포):")
            for sector, count in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
                print(f"   - {sector}: {count} stocks")
            print()
    else:
        print("❌ No stocks passed all filtering criteria.")
        print("💡 Consider relaxing the filtering criteria:")
        print("   - Lower minimum trading volume")
        print("   - Increase maximum debt ratio")
        print("   - Lower revenue growth requirement")
        print("   - Lower operating margin requirement")
        print()
    
    # Export results to Excel
    excel_filename = f"US_Stock_Filter_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    try:
        print(f"📊 Exporting results to Excel: {excel_filename}")
        DataExporter.export_pipeline_result_excel(result, excel_filename)
        print(f"✅ Excel file created successfully!")
        print()
        
        print("📁 Excel File Structure:")
        print("   📋 Summary: Overall analysis summary")
        print("   🏆 Final Candidates: Final qualifying US stocks")
        print("   📊 Stage Results: Stage-by-stage filtering summary")
        if result.stage_results:
            for i, stage_result in enumerate(result.stage_results, 1):
                if stage_result.passed_symbols:
                    print(f"   📈 Stage {i} Passed: Stage {i} qualifying stocks details")
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
    print("⚡ Performance Summary (성능 요약):")
    print(f"   ⏱️ Total Execution Time: {execution_time:.2f} seconds")
    print(f"   📊 Average Time per Stock: {execution_time / len(symbols):.3f} seconds")
    
    # Retry counts (if available)
    try:
        retry_counts = data_manager.get_retry_counts()
        if any(count > 0 for count in retry_counts.values()):
            print(f"   🔄 API Retry Counts:")
            for source, count in retry_counts.items():
                if count > 0:
                    print(f"      - {source}: {count} retries")
    except:
        pass  # Retry counts not available for all adapters
    
    print()
    print("🎉 US Stock Analysis Complete! (미국 주식 분석 완료!)")
    print(f"📁 Results File: {excel_filename}")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)