#!/usr/bin/env python3
"""
Demo script to generate Excel output with mock data for Financial Stock Filter.
Mock 데이터를 사용해서 엑셀 출력 예제를 생성하는 스크립트
"""

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.pipeline import StockFilterPipeline, PipelineResult
from auto_financial_filter.models.base import StockSymbol, FilterResult
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
from auto_financial_filter.filters.liquidity_filter import LiquidityFilter
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter
from auto_financial_filter.filters.quality_growth_filter import QualityGrowthFilter
from auto_financial_filter.utils.export import DataExporter
import time

def create_demo_symbols():
    """Create demo stock symbols for testing."""
    return [
        StockSymbol("005930", "삼성전자", "KOSPI"),
        StockSymbol("000660", "SK하이닉스", "KOSPI"),
        StockSymbol("035420", "NAVER", "KOSDAQ"),
        StockSymbol("051910", "LG화학", "KOSPI"),
        StockSymbol("006400", "삼성SDI", "KOSPI"),
        StockSymbol("207940", "삼성바이오로직스", "KOSPI"),
        StockSymbol("373220", "LG에너지솔루션", "KOSPI"),
        StockSymbol("005380", "현대차", "KOSPI"),
        StockSymbol("000270", "기아", "KOSPI"),
        StockSymbol("068270", "셀트리온", "KOSPI"),
        StockSymbol("003670", "포스코홀딩스", "KOSPI"),
        StockSymbol("096770", "SK이노베이션", "KOSPI"),
        StockSymbol("034730", "SK", "KOSPI"),
        StockSymbol("018260", "삼성에스디에스", "KOSPI"),
        StockSymbol("066570", "LG전자", "KOSPI"),
        StockSymbol("323410", "카카오뱅크", "KOSPI"),
        StockSymbol("035720", "카카오", "KOSPI"),
        StockSymbol("028260", "삼성물산", "KOSPI"),
        StockSymbol("012330", "현대모비스", "KOSPI"),
        StockSymbol("105560", "KB금융", "KOSPI"),
        StockSymbol("055550", "신한지주", "KOSPI"),
        StockSymbol("086790", "하나금융지주", "KOSPI"),
        StockSymbol("032830", "삼성생명", "KOSPI"),
        StockSymbol("017670", "SK텔레콤", "KOSPI"),
        StockSymbol("030200", "KT", "KOSPI"),
        StockSymbol("036570", "엔씨소프트", "KOSPI"),
        StockSymbol("251270", "넷마블", "KOSPI"),
        StockSymbol("352820", "하이브", "KOSPI"),
        StockSymbol("042700", "한미반도체", "KOSDAQ"),
        StockSymbol("240810", "원익IPS", "KOSDAQ")
    ]

def main():
    """Main function to demonstrate Excel export functionality."""
    print("🚀 재무 건전성 기반 종목 필터링 시스템 - 엑셀 출력 데모")
    print("=" * 60)
    
    # Create configuration
    config = FilterConfig(
        min_trading_volume_krw=3_000_000_000,  # 30억 KRW
        max_debt_ratio_percent=180.0,          # 180%
        min_revenue_growth_percent=8.0,        # 8%
        min_operating_margin_percent=8.0,      # 8%
        verbose_output=True
    )
    
    print(f"📊 설정 매개변수:")
    print(f"   - 최소 거래량: {config.min_trading_volume_krw:,} KRW")
    print(f"   - 최대 부채비율: {config.max_debt_ratio_percent}%")
    print(f"   - 최소 매출성장률: {config.min_revenue_growth_percent}%")
    print(f"   - 최소 영업이익률: {config.min_operating_margin_percent}%")
    print()
    
    # Create mock data manager
    data_manager = MockDataAccessManager(config)
    
    # Create pipeline
    pipeline = StockFilterPipeline(config)
    
    # Add filters
    liquidity_filter = LiquidityFilter(config, data_manager)
    financial_filter = FinancialHealthFilter(config, data_manager)
    quality_filter = QualityGrowthFilter(config, data_manager)
    
    pipeline.add_filter(liquidity_filter)
    pipeline.add_filter(financial_filter)
    pipeline.add_filter(quality_filter)
    
    # Create demo symbols
    symbols = create_demo_symbols()
    print(f"📈 분석 대상 종목: {len(symbols)}개")
    
    # Execute pipeline
    print("\n🔄 필터링 파이프라인 실행 중...")
    start_time = time.time()
    result = pipeline.execute(symbols)
    execution_time = time.time() - start_time
    
    # Display results
    print(f"\n✅ 필터링 완료! (실행시간: {execution_time:.2f}초)")
    print(f"📊 총 처리된 종목: {result.total_processed}개")
    print(f"🎯 최종 후보 종목: {len(result.final_candidates)}개")
    print()
    
    # Display stage results
    print("📋 단계별 필터링 결과:")
    for i, stage_result in enumerate(result.stage_results, 1):
        print(f"   {i}단계 - {stage_result.stage}")
        print(f"      입력: {stage_result.total_processed}개")
        print(f"      통과: {len(stage_result.passed_symbols)}개")
        print(f"      실패: {len(stage_result.failed_symbols)}개")
        print(f"      통과율: {stage_result.pass_rate:.1f}%")
        print()
    
    # Display final candidates
    if result.final_candidates:
        print("🏆 최종 후보 종목:")
        for symbol in result.final_candidates:
            print(f"   {symbol.code} - {symbol.name} ({symbol.market})")
        print()
    
    # Export to Excel
    excel_filename = "재무건전성_종목필터링_결과.xlsx"
    print(f"📊 엑셀 파일로 내보내는 중: {excel_filename}")
    
    try:
        DataExporter.export_pipeline_result_excel(result, excel_filename)
        print(f"✅ 엑셀 파일 생성 완료: {excel_filename}")
        print()
        print("📁 엑셀 파일 구성:")
        print("   - Summary: 전체 요약 정보")
        print("   - Final Candidates: 최종 후보 종목 리스트")
        print("   - Stage Results: 단계별 필터링 결과 요약")
        print("   - Stage 1 Passed: 1단계(유동성) 통과 종목")
        print("   - Stage 2 Passed: 2단계(재무건전성) 통과 종목")
        print("   - Stage 3 Passed: 3단계(품질성장) 통과 종목")
        
    except Exception as e:
        print(f"❌ 엑셀 파일 생성 실패: {e}")
        print("💡 pandas와 openpyxl 패키지가 설치되어 있는지 확인해주세요.")
        print("   설치 명령어: pip install pandas openpyxl")
    
    print(f"\n🎉 데모 완료!")

if __name__ == "__main__":
    main()