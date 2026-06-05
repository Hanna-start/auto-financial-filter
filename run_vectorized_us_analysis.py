#!/usr/bin/env python3
"""
벡터화된 필터를 사용한 완전한 미국 주식 분석
- 3단계 필터링 파이프라인 (유동성 → 재무건전성 → 품질성장)
- 벡터화된 고성능 처리
- 상세한 탈락 사유 추적
- Excel 결과 출력
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')


import time
import pandas as pd
from datetime import datetime
from auto_financial_filter.config import FilterConfig
from auto_financial_filter.data_access.us_adapters import USDataAccessManager
from auto_financial_filter.filters.liquidity_filter import LiquidityFilter
from auto_financial_filter.filters.vectorized_financial_health_filter import VectorizedFinancialHealthFilter
from auto_financial_filter.models.base import StockSymbol
# from auto_financial_filter.utils.export import ExcelExporter
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_sp500_sample_symbols():
    """S&P 500 대표 종목 샘플 (다양한 섹터)"""
    return [
        # 기술 (Technology)
        StockSymbol("AAPL", "Apple Inc.", "NASDAQ"),
        StockSymbol("MSFT", "Microsoft Corporation", "NASDAQ"),
        StockSymbol("GOOGL", "Alphabet Inc.", "NASDAQ"),
        StockSymbol("AMZN", "Amazon.com Inc.", "NASDAQ"),
        StockSymbol("TSLA", "Tesla Inc.", "NASDAQ"),
        StockSymbol("NVDA", "NVIDIA Corporation", "NASDAQ"),
        StockSymbol("META", "Meta Platforms Inc.", "NASDAQ"),
        
        # 금융 (Financials)
        StockSymbol("JPM", "JPMorgan Chase & Co.", "NYSE"),
        StockSymbol("BAC", "Bank of America Corp", "NYSE"),
        StockSymbol("WFC", "Wells Fargo & Company", "NYSE"),
        StockSymbol("GS", "The Goldman Sachs Group Inc.", "NYSE"),
        StockSymbol("MS", "Morgan Stanley", "NYSE"),
        
        # 헬스케어 (Healthcare)
        StockSymbol("JNJ", "Johnson & Johnson", "NYSE"),
        StockSymbol("PFE", "Pfizer Inc.", "NYSE"),
        StockSymbol("UNH", "UnitedHealth Group Inc.", "NYSE"),
        StockSymbol("ABBV", "AbbVie Inc.", "NYSE"),
        StockSymbol("MRK", "Merck & Co. Inc.", "NYSE"),
        
        # 소비재 (Consumer Goods)
        StockSymbol("KO", "The Coca-Cola Company", "NYSE"),
        StockSymbol("PG", "Procter & Gamble Co", "NYSE"),
        StockSymbol("WMT", "Walmart Inc.", "NYSE"),
        StockSymbol("HD", "The Home Depot Inc.", "NYSE"),
        StockSymbol("MCD", "McDonald's Corporation", "NYSE"),
        
        # 에너지 (Energy)
        StockSymbol("XOM", "Exxon Mobil Corporation", "NYSE"),
        StockSymbol("CVX", "Chevron Corporation", "NYSE"),
        StockSymbol("COP", "ConocoPhillips", "NYSE"),
        
        # 산업재 (Industrials)
        StockSymbol("BA", "The Boeing Company", "NYSE"),
        StockSymbol("CAT", "Caterpillar Inc.", "NYSE"),
        StockSymbol("GE", "General Electric Company", "NYSE"),
        StockSymbol("MMM", "3M Company", "NYSE"),
        
        # 통신 (Communication)
        StockSymbol("VZ", "Verizon Communications Inc.", "NYSE"),
        StockSymbol("T", "AT&T Inc.", "NYSE"),
        
        # 유틸리티 (Utilities)
        StockSymbol("NEE", "NextEra Energy Inc.", "NYSE"),
        StockSymbol("DUK", "Duke Energy Corporation", "NYSE"),
        
        # 부동산 (Real Estate)
        StockSymbol("AMT", "American Tower Corporation", "NYSE"),
        StockSymbol("PLD", "Prologis Inc.", "NYSE"),
    ]


class VectorizedUSStockPipeline:
    """벡터화된 미국 주식 분석 파이프라인"""
    
    def __init__(self, config: FilterConfig):
        self.config = config
        self.data_manager = USDataAccessManager(config)
        self.results = {}
        
        # 필터 초기화
        self.liquidity_filter = LiquidityFilter(config, self.data_manager)
        self.financial_health_filter = VectorizedFinancialHealthFilter(config, self.data_manager)
        
        logger.info("VectorizedUSStockPipeline initialized")
        logger.info(f"Configuration: {config.__dict__}")
    
    def run_analysis(self, symbols):
        """완전한 3단계 분석 실행"""
        logger.info(f"Starting vectorized analysis for {len(symbols)} US stocks")
        
        # Stage 1: 유동성 필터
        logger.info("Stage 1: Liquidity Filter")
        stage1_result = self.liquidity_filter.filter(symbols)
        self.results['stage1'] = stage1_result
        
        logger.info(f"Stage 1 Results: {len(stage1_result.passed_symbols)} passed, "
                   f"{len(stage1_result.failed_symbols)} failed ({stage1_result.pass_rate:.1f}%)")
        
        if not stage1_result.passed_symbols:
            logger.warning("No symbols passed Stage 1 - stopping analysis")
            return self.results
        
        # Stage 2: 재무건전성 필터 (벡터화)
        logger.info("Stage 2: Financial Health Filter (Vectorized)")
        stage2_result = self.financial_health_filter.filter(stage1_result.passed_symbols)
        self.results['stage2'] = stage2_result
        
        logger.info(f"Stage 2 Results: {len(stage2_result.passed_symbols)} passed, "
                   f"{len(stage2_result.failed_symbols)} failed ({stage2_result.pass_rate:.1f}%)")
        
        # Stage 3는 아직 구현 중이므로 생략
        logger.info("Stage 3: Quality Growth Filter - 구현 중...")
        
        return self.results
    
    def export_results(self):
        """결과를 Excel로 출력"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Vectorized_US_Stock_Analysis_{timestamp}.xlsx"
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # 요약 시트
            self._create_summary_sheet(writer)
            
            # 각 단계별 상세 결과
            for stage_name, result in self.results.items():
                self._create_stage_sheet(writer, stage_name, result)
        
        logger.info(f"Results exported to: {filename}")
        return filename
    
    def _create_summary_sheet(self, writer):
        """요약 시트 생성"""
        summary_data = []
        
        for stage_name, result in self.results.items():
            summary_data.append({
                'Stage': stage_name.upper(),
                'Filter_Type': result.stage,
                'Total_Input': result.total_processed,
                'Passed': len(result.passed_symbols),
                'Failed': len(result.failed_symbols),
                'Pass_Rate_%': round(result.pass_rate, 1),
                'Criteria': str(result.criteria_applied)
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    def _create_stage_sheet(self, writer, stage_name, result):
        """단계별 상세 시트 생성"""
        stage_data = []
        
        # 통과한 종목들
        for symbol in result.passed_symbols:
            stage_data.append({
                'Symbol': symbol.code,
                'Name': symbol.name,
                'Market': symbol.market,
                'Result': 'PASS',
                'Failure_Reason': None
            })
        
        # 탈락한 종목들
        for symbol in result.failed_symbols:
            stage_data.append({
                'Symbol': symbol.code,
                'Name': symbol.name,
                'Market': symbol.market,
                'Result': 'FAIL',
                'Failure_Reason': 'See detailed analysis'
            })
        
        stage_df = pd.DataFrame(stage_data)
        sheet_name = f"Stage_{stage_name[-1]}_Details"
        stage_df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    def print_detailed_results(self):
        """상세 결과 콘솔 출력"""
        print("\n" + "="*80)
        print("🎯 벡터화된 미국 주식 분석 결과")
        print("="*80)
        
        for stage_name, result in self.results.items():
            print(f"\n📊 {stage_name.upper()}: {result.stage}")
            print(f"   입력: {result.total_processed}개 종목")
            print(f"   통과: {len(result.passed_symbols)}개 ({result.pass_rate:.1f}%)")
            print(f"   탈락: {len(result.failed_symbols)}개")
            
            if result.passed_symbols:
                print(f"   통과 종목: {', '.join([s.code for s in result.passed_symbols[:10]])}")
                if len(result.passed_symbols) > 10:
                    print(f"              ... 외 {len(result.passed_symbols)-10}개")


def main():
    """메인 실행 함수"""
    print("🚀 벡터화된 미국 주식 분석 시스템")
    print("="*60)
    
    # 설정
    config = FilterConfig(
        # 유동성 기준
        min_trading_volume_krw=1000000000,  # 일평균 거래대금 10억원 이상
        trading_volume_period_days=60,      # 60일 거래 데이터
        
        # 재무건전성 기준 (미국 시장에 맞게 조정)
        max_debt_ratio_percent=150.0,       # 부채비율 150% 이하 (미국은 한국보다 관대)
        min_revenue_growth_percent=3.0,     # 매출성장률 3% 이상 (보수적)
        cash_flow_quarters=3,               # 4분기 중 3분기 이상 양수 현금흐름
        
        # 기타 설정
        verbose_output=True
    )
    
    # 테스트 종목
    symbols = get_sp500_sample_symbols()
    
    print(f"📈 분석 대상: {len(symbols)}개 S&P 500 대표 종목")
    print(f"🎯 분석 기준:")
    print(f"   - 유동성: 일평균 거래대금 {config.min_trading_volume_krw:,}원 이상")
    print(f"   - 재무건전성: 부채비율 {config.max_debt_ratio_percent}% 이하, "
          f"매출성장률 {config.min_revenue_growth_percent}% 이상")
    
    # 분석 실행
    pipeline = VectorizedUSStockPipeline(config)
    
    start_time = time.time()
    results = pipeline.run_analysis(symbols)
    analysis_time = time.time() - start_time
    
    print(f"\n⏱️  총 분석 시간: {analysis_time:.2f}초")
    print(f"📊 처리 속도: {len(symbols)/analysis_time:.0f} 종목/초")
    
    # 결과 출력
    pipeline.print_detailed_results()
    
    # Excel 출력
    filename = pipeline.export_results()
    
    print(f"\n🎉 분석 완료!")
    print(f"📁 상세 결과: {filename}")
    print(f"💡 벡터화된 필터로 고속 처리 및 상세 분석 완료")


if __name__ == "__main__":
    main()