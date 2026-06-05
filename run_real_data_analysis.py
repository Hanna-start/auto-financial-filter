#!/usr/bin/env python3
"""
실제 데이터를 사용한 재무 건전성 기반 종목 필터링 시스템 실행 스크립트
Real data analysis script for Financial Stock Filter System
"""

import sys
import os
import io
from pathlib import Path

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.filters.liquidity_filter import LiquidityFilter
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter
from auto_financial_filter.filters.quality_growth_filter import QualityGrowthFilter
from auto_financial_filter.filters.momentum_filter import MomentumFilter
from auto_financial_filter.utils.export import DataExporter
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def try_import_data_sources():
    """Try to import various data source adapters in order of preference."""
    
    # Try alternative data sources (yfinance + web scraping) first
    try:
        from auto_financial_filter.data_access.alternative_adapters import AlternativeDataAccessManager
        logger.info("✅ Using alternative data sources (yfinance + web scraping)")
        return AlternativeDataAccessManager, "alternative"
    except ImportError as e:
        logger.warning(f"❌ Alternative data sources not available: {e}")
    
    # Try original Korean data sources
    try:
        from auto_financial_filter.data_access.adapters import DataAccessManager
        data_manager = DataAccessManager(FilterConfig())
        availability = data_manager.get_availability_status()
        if any(availability.values()):
            logger.info("✅ Using original Korean data sources (FinanceDataReader, OpenDartReader, Pykrx)")
            return DataAccessManager, "original"
        else:
            logger.warning("❌ Original Korean data sources libraries not installed")
    except ImportError as e:
        logger.warning(f"❌ Original Korean data sources not available: {e}")
    
    # Fallback to mock data
    try:
        from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
        logger.info("✅ Using mock data sources (for testing)")
        return MockDataAccessManager, "mock"
    except ImportError as e:
        logger.error(f"❌ Even mock data sources not available: {e}")
        raise RuntimeError("No data sources available")


def main():
    """Main function to run real data analysis."""
    
    print("🚀 재무 건전성 기반 종목 필터링 시스템 - 실제 데이터 분석")
    print("=" * 70)
    
    # Create configuration with realistic parameters
    config = FilterConfig(
        min_trading_volume_krw=5_000_000_000,    # 50억 KRW (더 현실적인 기준)
        trading_volume_period_days=30,           # 30일 평균
        max_debt_ratio_percent=200.0,            # 부채비율 200% 이하
        min_revenue_growth_percent=0.0,          # 매출성장률 0% 이상 (역성장 배제)
        cash_flow_quarters=4,                    # 4분기 현금흐름 분석
        min_operating_margin_percent=5.0,        # 영업이익률 5% 이상 (더 현실적)
        profit_trend_years=4,                    # 4년 수익성 트렌드
        cogs_trend_quarters=6,                   # 6분기 매출원가 트렌드
        data_cache_enabled=True,                 # 캐싱 활성화
        data_cache_ttl_hours=24,                 # 24시간 캐시
        api_retry_attempts=3,                    # 3회 재시도
        api_timeout_seconds=30,                  # 30초 타임아웃
        verbose_output=True,                     # 상세 출력
        log_level="INFO"
    )
    
    print(f"📊 필터링 기준:")
    print(f"   💰 최소 거래량: {config.min_trading_volume_krw:,} KRW")
    print(f"   📈 거래량 기간: {config.trading_volume_period_days}일")
    print(f"   💳 최대 부채비율: {config.max_debt_ratio_percent}%")
    print(f"   📊 최소 매출성장률: {config.min_revenue_growth_percent}%")
    print(f"   💹 최소 영업이익률: {config.min_operating_margin_percent}%")
    print()
    
    # Try to get the best available data source
    try:
        DataManagerClass, source_type = try_import_data_sources()
        data_manager = DataManagerClass(config)
        
        print(f"🔗 데이터 소스: {source_type}")
        
        # Check data source availability
        availability = data_manager.get_availability_status()
        print(f"📡 데이터 소스 상태:")
        for source, available in availability.items():
            status = "✅ 사용 가능" if available else "❌ 사용 불가"
            print(f"   - {source}: {status}")
        print()
        
    except Exception as e:
        logger.error(f"데이터 소스 초기화 실패: {e}")
        return 1
    
    # Create and configure pipeline
    pipeline = StockFilterPipeline(config)
    
    # Add filters
    liquidity_filter = LiquidityFilter(config, data_manager)
    financial_filter = FinancialHealthFilter(config, data_manager)
    quality_filter = QualityGrowthFilter(config, data_manager)
    momentum_filter = MomentumFilter(config, data_manager)
    
    pipeline.add_filter(liquidity_filter)
    pipeline.add_filter(financial_filter)
    pipeline.add_filter(quality_filter)
    pipeline.add_filter(momentum_filter)
    
    print(f"🔧 파이프라인 구성:")
    print(f"   1️⃣ 유동성 필터 (거래량 기준)")
    print(f"   2️⃣ 재무건전성 필터 (부채비율, 매출성장률, 현금흐름)")
    print(f"   3️⃣ 품질성장 필터 (영업이익률, 수익성 트렌드)")
    print(f"   4️⃣ 모멘텀 필터 (120일 이동평균선 상회 여부)")
    print()
    
    # Get stock symbols
    try:
        print("📈 종목 데이터 로딩 중...")
        symbols = data_manager.get_all_symbols()
        print(f"✅ 총 {len(symbols)}개 종목 로드 완료")
        
        # Display sample symbols
        print(f"📋 종목 샘플 (처음 10개):")
        for i, symbol in enumerate(symbols[:10], 1):
            print(f"   {i:2d}. {symbol.code} - {symbol.name} ({symbol.market})")
        if len(symbols) > 10:
            print(f"   ... 외 {len(symbols) - 10}개 종목")
        print()
        
    except Exception as e:
        logger.error(f"종목 데이터 로딩 실패: {e}")
        return 1
    
    # Execute pipeline
    try:
        print("🔄 필터링 파이프라인 실행 중...")
        print("   ⏳ 이 작업은 몇 분 정도 소요될 수 있습니다...")
        
        start_time = time.time()
        result = pipeline.execute(symbols)
        execution_time = time.time() - start_time
        
        print(f"✅ 필터링 완료! (실행시간: {execution_time:.2f}초)")
        print()
        
    except Exception as e:
        logger.error(f"파이프라인 실행 실패: {e}")
        return 1
    
    # Display results
    print("📊 필터링 결과 요약:")
    print(f"   📈 총 처리된 종목: {result.total_processed}개")
    print(f"   🎯 최종 후보 종목: {len(result.final_candidates)}개")
    print(f"   📈 전체 통과율: {len(result.final_candidates) / result.total_processed * 100:.1f}%")
    print()
    
    # Display stage-by-stage results
    print("📋 단계별 필터링 결과:")
    for i, stage_result in enumerate(result.stage_results, 1):
        stage_name = stage_result.stage
        if "step1" in stage_name:
            stage_name = "1단계: 유동성 필터"
        elif "Financial Health" in stage_name:
            stage_name = "2단계: 재무건전성 필터"
        elif "final_candidate" in stage_name:
            stage_name = "3단계: 품질성장 필터"
        
        print(f"   {stage_name}")
        print(f"      📥 입력: {stage_result.total_processed}개")
        print(f"      ✅ 통과: {len(stage_result.passed_symbols)}개")
        print(f"      ❌ 실패: {len(stage_result.failed_symbols)}개")
        print(f"      📊 통과율: {stage_result.pass_rate:.1f}%")
        
        # Show criteria applied
        if stage_result.criteria_applied:
            print(f"      🔍 적용된 기준:")
            for key, value in stage_result.criteria_applied.items():
                print(f"         - {key}: {value}")
        print()
    
    # Display final candidates
    if result.final_candidates:
        print("🏆 최종 후보 종목:")
        for i, symbol in enumerate(result.final_candidates, 1):
            print(f"   {i:2d}. {symbol.code} - {symbol.name} ({symbol.market})")
        print()
    else:
        print("❌ 모든 필터링 기준을 통과한 종목이 없습니다.")
        print("💡 필터링 기준을 완화해보세요:")
        print("   - 최소 거래량 낮추기")
        print("   - 부채비율 기준 완화")
        print("   - 매출성장률 기준 낮추기")
        print("   - 영업이익률 기준 낮추기")
        print()
    
    # Export results to Excel
    excel_filename = f"재무건전성_필터링_결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    try:
        print(f"📊 결과를 엑셀 파일로 내보내는 중: {excel_filename}")
        DataExporter.export_pipeline_result_excel(result, excel_filename)
        print(f"✅ 엑셀 파일 생성 완료!")
        print()
        
        print("📁 엑셀 파일 구성:")
        print("   📋 Summary: 전체 요약 정보")
        print("   🏆 Final Candidates: 최종 후보 종목 리스트")
        print("   📊 Stage Results: 단계별 필터링 결과 요약")
        if result.stage_results:
            for i, stage_result in enumerate(result.stage_results, 1):
                if stage_result.passed_symbols:
                    print(f"   📈 Stage {i} Passed: {i}단계 통과 종목 상세")
        print()
        
    except Exception as e:
        logger.error(f"엑셀 파일 생성 실패: {e}")
        print("💡 CSV 형식으로 대신 저장해보겠습니다...")
        
        try:
            csv_filename = excel_filename.replace('.xlsx', '.csv')
            DataExporter.export_pipeline_result_csv(result, csv_filename)
            print(f"✅ CSV 파일 생성 완료: {csv_filename}")
        except Exception as csv_e:
            logger.error(f"CSV 파일 생성도 실패: {csv_e}")
    
    # Performance summary
    print("⚡ 성능 요약:")
    print(f"   ⏱️ 총 실행시간: {execution_time:.2f}초")
    print(f"   📊 종목당 평균 처리시간: {execution_time / len(symbols):.3f}초")
    
    # Retry counts (if available)
    try:
        retry_counts = data_manager.get_retry_counts()
        if any(count > 0 for count in retry_counts.values()):
            print(f"   🔄 API 재시도 횟수:")
            for source, count in retry_counts.items():
                if count > 0:
                    print(f"      - {source}: {count}회")
    except:
        pass  # Retry counts not available for all adapters
    
    print()
    print("🎉 분석 완료!")
    print(f"📁 결과 파일: {excel_filename}")
    
    return 0


if __name__ == "__main__":
    from datetime import datetime
    exit_code = main()
    sys.exit(exit_code)