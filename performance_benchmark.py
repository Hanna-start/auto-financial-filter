#!/usr/bin/env python3
"""
성능 벤치마크 스크립트
- 기존 for 루프 방식 vs 벡터화 방식 성능 비교
- 대량 데이터에서의 속도 차이 측정
- 메모리 사용량 비교
"""

import sys
import time
import psutil
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter
from auto_financial_filter.filters.vectorized_financial_health_filter import VectorizedFinancialHealthFilter
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """성능 벤치마크 클래스"""
    
    def __init__(self):
        self.config = FilterConfig(
            max_debt_ratio_percent=200.0,
            min_revenue_growth_percent=5.0,
            cash_flow_quarters=4,
            verbose_output=False  # 벤치마크 시 로그 최소화
        )
        
    def create_large_dataset(self, symbol_count: int):
        """대량 테스트 데이터셋 생성"""
        from auto_financial_filter.models.base import StockSymbol
        
        symbols = []
        for i in range(symbol_count):
            symbols.append(StockSymbol(
                code=f"TEST{i:06d}",
                name=f"Test Company {i}",
                market="KOSPI" if i % 2 == 0 else "KOSDAQ"
            ))
        
        return symbols
    
    def measure_performance(self, filter_class, symbols, description):
        """필터 성능 측정"""
        data_manager = MockDataAccessManager(self.config)
        filter_instance = filter_class(self.config, data_manager)
        
        # 메모리 사용량 측정 시작
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # 실행 시간 측정
        start_time = time.time()
        
        try:
            result = filter_instance.filter(symbols)
            execution_time = time.time() - start_time
            
            # 메모리 사용량 측정 종료
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = memory_after - memory_before
            
            return {
                'description': description,
                'symbol_count': len(symbols),
                'execution_time': execution_time,
                'memory_used_mb': memory_used,
                'passed_count': len(result.passed_symbols),
                'failed_count': len(result.failed_symbols),
                'symbols_per_second': len(symbols) / execution_time if execution_time > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error in {description}: {e}")
            return None
    
    def run_benchmark(self):
        """벤치마크 실행"""
        print("🚀 재무 건전성 필터 성능 벤치마크")
        print("=" * 60)
        
        # 다양한 데이터 크기로 테스트
        test_sizes = [100, 500, 1000, 2000, 5000]
        results = []
        
        for size in test_sizes:
            print(f"\n📊 테스트 데이터 크기: {size:,}개 종목")
            print("-" * 40)
            
            symbols = self.create_large_dataset(size)
            
            # 1. 기존 for 루프 방식
            result1 = self.measure_performance(
                FinancialHealthFilter, 
                symbols, 
                f"기존 For Loop 방식 ({size:,}개)"
            )
            
            if result1:
                results.append(result1)
                print(f"⏱️  기존 방식: {result1['execution_time']:.2f}초 "
                      f"({result1['symbols_per_second']:.0f} 종목/초)")
                print(f"💾 메모리 사용: {result1['memory_used_mb']:.1f}MB")
            
            # 2. 벡터화 방식
            result2 = self.measure_performance(
                VectorizedFinancialHealthFilter, 
                symbols, 
                f"벡터화 방식 ({size:,}개)"
            )
            
            if result2:
                results.append(result2)
                print(f"⚡ 벡터화: {result2['execution_time']:.2f}초 "
                      f"({result2['symbols_per_second']:.0f} 종목/초)")
                print(f"💾 메모리 사용: {result2['memory_used_mb']:.1f}MB")
                
                # 성능 개선 비율 계산
                if result1 and result1['execution_time'] > 0:
                    speedup = result1['execution_time'] / result2['execution_time']
                    print(f"🎯 성능 개선: {speedup:.1f}배 빠름")
        
        # 결과 요약
        self.print_summary(results)
        
        # 결과를 CSV로 저장
        self.save_results(results)
    
    def print_summary(self, results):
        """결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📈 성능 벤치마크 요약")
        print("=" * 60)
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            # 방식별 그룹화
            for method in df['description'].str.extract(r'(기존 For Loop|벡터화)')[0].unique():
                if pd.notna(method):
                    method_data = df[df['description'].str.contains(method)]
                    
                    print(f"\n🔍 {method} 방식:")
                    print(f"   평균 처리 속도: {method_data['symbols_per_second'].mean():.0f} 종목/초")
                    print(f"   평균 메모리 사용: {method_data['memory_used_mb'].mean():.1f}MB")
                    print(f"   최대 처리량: {method_data['symbol_count'].max():,}개 종목")
        
        # 권장사항
        print(f"\n💡 권장사항:")
        print(f"   - 1,000개 이상 종목 분석 시 벡터화 방식 사용 권장")
        print(f"   - 실시간 분석에는 벡터화 방식 필수")
        print(f"   - 메모리 제약이 있는 환경에서는 배치 처리 고려")
    
    def save_results(self, results):
        """결과를 CSV 파일로 저장"""
        if results:
            df = pd.DataFrame(results)
            filename = f"performance_benchmark_{int(time.time())}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n📁 결과 저장: {filename}")


def main():
    """메인 함수"""
    benchmark = PerformanceBenchmark()
    benchmark.run_benchmark()


if __name__ == "__main__":
    main()