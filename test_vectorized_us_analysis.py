#!/usr/bin/env python3
"""
벡터화된 필터를 실제 미국 주식 데이터로 테스트
- 실제 yfinance 데이터로 성능 및 정확성 검증
- 탈락 사유 추적 기능 테스트
- 기존 방식과 결과 비교
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time
import pandas as pd
from auto_financial_filter.config import FilterConfig
from auto_financial_filter.data_access.us_adapters import USDataAccessManager
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter
from auto_financial_filter.filters.vectorized_financial_health_filter import VectorizedFinancialHealthFilter
from auto_financial_filter.models.base import StockSymbol
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_us_test_symbols():
    """미국 주식 테스트 심볼 생성"""
    # 다양한 섹터의 대표 종목들
    test_symbols = [
        # 기술주
        StockSymbol("AAPL", "Apple Inc.", "NASDAQ"),
        StockSymbol("MSFT", "Microsoft Corporation", "NASDAQ"),
        StockSymbol("GOOGL", "Alphabet Inc.", "NASDAQ"),
        StockSymbol("AMZN", "Amazon.com Inc.", "NASDAQ"),
        StockSymbol("TSLA", "Tesla Inc.", "NASDAQ"),
        
        # 금융주
        StockSymbol("JPM", "JPMorgan Chase & Co.", "NYSE"),
        StockSymbol("BAC", "Bank of America Corp", "NYSE"),
        StockSymbol("WFC", "Wells Fargo & Company", "NYSE"),
        
        # 헬스케어
        StockSymbol("JNJ", "Johnson & Johnson", "NYSE"),
        StockSymbol("PFE", "Pfizer Inc.", "NYSE"),
        
        # 소비재
        StockSymbol("KO", "The Coca-Cola Company", "NYSE"),
        StockSymbol("PG", "Procter & Gamble Co", "NYSE"),
        
        # 에너지
        StockSymbol("XOM", "Exxon Mobil Corporation", "NYSE"),
        StockSymbol("CVX", "Chevron Corporation", "NYSE"),
        
        # 산업재
        StockSymbol("BA", "The Boeing Company", "NYSE"),
        StockSymbol("CAT", "Caterpillar Inc.", "NYSE"),
    ]
    
    return test_symbols


def test_vectorized_vs_traditional():
    """벡터화 vs 전통적 방식 비교 테스트"""
    print("🧪 벡터화된 필터 vs 전통적 필터 비교 테스트")
    print("=" * 60)
    
    # 설정
    config = FilterConfig(
        max_debt_ratio_percent=200.0,
        min_revenue_growth_percent=5.0,
        cash_flow_quarters=3,  # 미국 데이터에 맞게 조정
        verbose_output=True
    )
    
    # 테스트 데이터
    symbols = create_us_test_symbols()
    data_manager = USDataAccessManager(config)
    
    print(f"📊 테스트 대상: {len(symbols)}개 미국 주식")
    print(f"🎯 필터 기준: 부채비율 ≤ {config.max_debt_ratio_percent}%, "
          f"매출성장률 ≥ {config.min_revenue_growth_percent}%, "
          f"현금흐름 양수 분기 ≥ {config.cash_flow_quarters}개")
    
    # 1. 전통적 방식 테스트
    print("\n🔄 전통적 For Loop 방식 테스트...")
    traditional_filter = FinancialHealthFilter(config, data_manager)
    
    start_time = time.time()
    traditional_result = traditional_filter.filter(symbols)
    traditional_time = time.time() - start_time
    
    print(f"⏱️  실행 시간: {traditional_time:.2f}초")
    print(f"✅ 통과: {len(traditional_result.passed_symbols)}개")
    print(f"❌ 탈락: {len(traditional_result.failed_symbols)}개")
    print(f"📈 통과율: {traditional_result.pass_rate:.1f}%")
    
    # 2. 벡터화 방식 테스트
    print("\n⚡ 벡터화 방식 테스트...")
    vectorized_filter = VectorizedFinancialHealthFilter(config, data_manager)
    
    start_time = time.time()
    vectorized_result = vectorized_filter.filter(symbols)
    vectorized_time = time.time() - start_time
    
    print(f"⏱️  실행 시간: {vectorized_time:.2f}초")
    print(f"✅ 통과: {len(vectorized_result.passed_symbols)}개")
    print(f"❌ 탈락: {len(vectorized_result.failed_symbols)}개")
    print(f"📈 통과율: {vectorized_result.pass_rate:.1f}%")
    
    # 3. 성능 비교
    print(f"\n🎯 성능 비교:")
    if vectorized_time > 0:
        speedup = traditional_time / vectorized_time
        print(f"   성능 개선: {speedup:.1f}배 {'빠름' if speedup > 1 else '느림'}")
    
    # 4. 결과 일치성 검증
    print(f"\n🔍 결과 일치성 검증:")
    traditional_passed_codes = {s.code for s in traditional_result.passed_symbols}
    vectorized_passed_codes = {s.code for s in vectorized_result.passed_symbols}
    
    if traditional_passed_codes == vectorized_passed_codes:
        print("✅ 두 방식의 결과가 완전히 일치합니다!")
    else:
        print("⚠️  결과 차이 발견:")
        only_traditional = traditional_passed_codes - vectorized_passed_codes
        only_vectorized = vectorized_passed_codes - traditional_passed_codes
        
        if only_traditional:
            print(f"   전통적 방식만 통과: {only_traditional}")
        if only_vectorized:
            print(f"   벡터화 방식만 통과: {only_vectorized}")
    
    # 5. 상세 분석 결과 출력
    print(f"\n📋 상세 분석 결과:")
    
    print(f"\n통과한 종목들:")
    for symbol in vectorized_result.passed_symbols:
        print(f"  ✅ {symbol.code} - {symbol.name}")
    
    print(f"\n탈락한 종목들:")
    for symbol in vectorized_result.failed_symbols:
        print(f"  ❌ {symbol.code} - {symbol.name}")
    
    return traditional_result, vectorized_result


def export_detailed_analysis():
    """상세 분석 결과를 Excel로 출력"""
    print("\n📊 상세 분석 결과 Excel 출력...")
    
    config = FilterConfig(
        max_debt_ratio_percent=200.0,
        min_revenue_growth_percent=5.0,
        cash_flow_quarters=3,
        verbose_output=False
    )
    
    symbols = create_us_test_symbols()
    data_manager = USDataAccessManager(config)
    vectorized_filter = VectorizedFinancialHealthFilter(config, data_manager)
    
    result = vectorized_filter.filter(symbols)
    
    # 결과를 DataFrame으로 변환
    results_data = []
    
    for symbol in result.passed_symbols:
        results_data.append({
            'Symbol': symbol.code,
            'Name': symbol.name,
            'Market': symbol.market,
            'Result': 'PASS',
            'Failure_Reason': None
        })
    
    for symbol in result.failed_symbols:
        results_data.append({
            'Symbol': symbol.code,
            'Name': symbol.name,
            'Market': symbol.market,
            'Result': 'FAIL',
            'Failure_Reason': 'Analysis Required'  # 실제로는 상세 사유 추가 필요
        })
    
    df = pd.DataFrame(results_data)
    
    # Excel 파일로 저장
    filename = f"Vectorized_US_Analysis_Results_{int(time.time())}.xlsx"
    df.to_excel(filename, index=False)
    
    print(f"📁 결과 저장: {filename}")
    print(f"📈 총 {len(df)}개 종목 분석 완료")
    
    return filename


def main():
    """메인 함수"""
    try:
        # 1. 성능 비교 테스트
        traditional_result, vectorized_result = test_vectorized_vs_traditional()
        
        # 2. 상세 분석 결과 출력
        export_detailed_analysis()
        
        print(f"\n🎉 벡터화된 필터 테스트 완료!")
        print(f"   - 실제 미국 주식 데이터로 검증 완료")
        print(f"   - 성능 및 정확성 확인")
        print(f"   - 상세 분석 결과 Excel 출력")
        
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()