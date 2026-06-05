"""
벡터화된 재무건전성 필터 - 성능 최적화 버전
- pandas 벡터화 연산으로 대량 데이터 고속 처리
- for 루프 제거하여 수천 개 종목도 빠르게 분석
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
import logging
from datetime import datetime

from ..models.base import StockSymbol, FilterResult, BaseFilter
from ..config import FilterConfig


class VectorizedFinancialHealthFilter(BaseFilter):
    """벡터화된 재무건전성 필터 - 고성능 버전"""
    
    def __init__(self, config: FilterConfig, data_manager):
        super().__init__(config)
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("VectorizedFinancialHealthFilter initialized with:")
        self.logger.info(f"  Max debt ratio: {config.max_debt_ratio_percent}%")
        self.logger.info(f"  Min revenue growth: {config.min_revenue_growth_percent}%")
        self.logger.info(f"  Cash flow quarters: {config.cash_flow_quarters}")
    
    def get_stage_name(self) -> str:
        """필터 단계 이름 반환"""
        return "Financial Health Filter (Vectorized)"
    
    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        """벡터화된 재무건전성 필터링 실행"""
        self.logger.info(f"Starting vectorized financial health filtering for {len(symbols)} symbols")
        
        # 1단계: 모든 종목의 재무 데이터를 한 번에 수집
        financial_df = self._collect_all_financial_data(symbols)
        
        if financial_df.empty:
            self.logger.warning("No financial data available for any symbols")
            return FilterResult(
                passed_symbols=[],
                failed_symbols=symbols,
                stage="Financial Health Filter (Vectorized)",
                criteria_applied=self._get_criteria_applied()
            )
        
        # 2단계: 벡터화된 계산으로 모든 기준을 한 번에 검사
        results_df = self._apply_vectorized_criteria(financial_df)
        
        # 3단계: 결과를 StockSymbol 객체로 변환
        passed_symbols, failed_symbols = self._convert_results_to_symbols(results_df, symbols)
        
        result = FilterResult(
            passed_symbols=passed_symbols,
            failed_symbols=failed_symbols,
            stage="Financial Health Filter (Vectorized)",
            criteria_applied=self._get_criteria_applied()
        )
        
        self.logger.info(f"Vectorized financial health filtering complete: {len(passed_symbols)} passed, "
                        f"{len(failed_symbols)} failed ({result.pass_rate:.1f}% pass rate)")
        
        return result
    
    def _collect_all_financial_data(self, symbols: List[StockSymbol]) -> pd.DataFrame:
        """모든 종목의 재무 데이터를 한 번에 수집하여 DataFrame으로 구성"""
        financial_records = []
        
        for symbol in symbols:
            try:
                # 개별 종목 재무 데이터 수집
                financial_data = self.data_manager.get_financial_data(symbol)
                
                # 데이터 형식 통일 (DataFrame 또는 Dictionary → 표준 레코드)
                record = self._standardize_financial_data(symbol, financial_data)
                if record:
                    financial_records.append(record)
                    
            except Exception as e:
                self.logger.warning(f"Failed to collect data for {symbol.code}: {e}")
                # 데이터 수집 실패한 종목도 기록 (나중에 탈락 처리)
                financial_records.append({
                    'symbol_code': symbol.code,
                    'symbol_name': symbol.name,
                    'symbol_market': symbol.market,
                    'data_available': False,
                    'debt_ratio': np.nan,
                    'revenue_growth_yoy': np.nan,
                    'cash_flow_positive_quarters': 0
                })
        
        return pd.DataFrame(financial_records)
    
    def _standardize_financial_data(self, symbol: StockSymbol, financial_data) -> Dict[str, Any]:
        """재무 데이터를 표준 형식으로 변환"""
        try:
            # 데이터 형식에 따른 처리 (한국: DataFrame, 미국: Dictionary)
            if hasattr(financial_data, 'empty'):
                # DataFrame 형식 (한국 시장)
                if financial_data.empty:
                    return None
                
                # 최신 분기 데이터에서 부채비율 계산
                latest_data = financial_data.iloc[-1]
                total_debt = latest_data.get('TotalDebt', 0)
                total_equity = latest_data.get('TotalEquity', 1)
                debt_ratio = (total_debt / total_equity) * 100 if total_equity > 0 else 999.0
                
                # 분기별 매출 및 현금흐름 추출
                quarterly_revenue = financial_data['Revenue'].tolist()[-4:]
                operating_cash_flow = financial_data['OperatingCashFlow'].tolist()[-4:]
                
            else:
                # Dictionary 형식 (미국 시장)
                quarterly_data = financial_data.get('quarterly_data', [])
                if not quarterly_data:
                    return None
                
                # 최신 분기 부채비율
                latest_quarter = quarterly_data[0]
                debt_ratio = latest_quarter.get('debt_ratio', 0)
                
                # 분기별 데이터 추출
                quarterly_revenue = [q.get('revenue', 0) for q in quarterly_data]
                operating_cash_flow = [q.get('operating_cash_flow', 0) for q in quarterly_data]
            
            # 매출성장률 계산 (전년동기 대비)
            if len(quarterly_revenue) >= 4:
                current_revenue = quarterly_revenue[-1]  # 최근 분기
                previous_year_revenue = quarterly_revenue[0]  # 1년 전 분기
                
                if previous_year_revenue > 0:
                    revenue_growth_yoy = ((current_revenue - previous_year_revenue) / previous_year_revenue) * 100
                else:
                    revenue_growth_yoy = 0.0
            else:
                revenue_growth_yoy = 0.0
            
            # 현금흐름 양수 분기 수 계산
            cash_flow_positive_quarters = sum(1 for cf in operating_cash_flow if cf > 0)
            
            return {
                'symbol_code': symbol.code,
                'symbol_name': symbol.name,
                'symbol_market': symbol.market,
                'data_available': True,
                'debt_ratio': debt_ratio,
                'revenue_growth_yoy': revenue_growth_yoy,
                'cash_flow_positive_quarters': cash_flow_positive_quarters,
                'quarterly_revenue': quarterly_revenue,
                'operating_cash_flow': operating_cash_flow
            }
            
        except Exception as e:
            self.logger.warning(f"Error standardizing data for {symbol.code}: {e}")
            return None
    
    def _apply_vectorized_criteria(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """벡터화된 연산으로 모든 기준을 한 번에 적용"""
        # 벡터화된 기준 검사 (한 줄씩 모든 종목 동시 처리)
        financial_df['pass_data_available'] = financial_df['data_available'] == True
        financial_df['pass_debt_ratio'] = financial_df['debt_ratio'] <= self.config.max_debt_ratio_percent
        financial_df['pass_revenue_growth'] = financial_df['revenue_growth_yoy'] >= self.config.min_revenue_growth_percent
        financial_df['pass_cash_flow'] = financial_df['cash_flow_positive_quarters'] >= self.config.cash_flow_quarters
        
        # 전체 기준 통과 여부 (모든 조건을 AND 연산)
        financial_df['pass_all_criteria'] = (
            financial_df['pass_data_available'] & 
            financial_df['pass_debt_ratio'] & 
            financial_df['pass_revenue_growth'] & 
            financial_df['pass_cash_flow']
        )
        
        # 탈락 사유 분석 (벡터화된 조건부 로직)
        financial_df['failure_reason'] = np.where(
            ~financial_df['pass_data_available'], 'Missing Data',
            np.where(
                ~financial_df['pass_debt_ratio'], 'Debt Ratio Exceeded',
                np.where(
                    ~financial_df['pass_revenue_growth'], 'Revenue Growth Below Threshold',
                    np.where(
                        ~financial_df['pass_cash_flow'], 'Insufficient Positive Cash Flow',
                        'Passed All Criteria'
                    )
                )
            )
        )
        
        # 통계 정보 로깅 (벡터화된 집계)
        total_count = len(financial_df)
        passed_count = financial_df['pass_all_criteria'].sum()
        
        self.logger.info(f"Vectorized analysis results:")
        self.logger.info(f"  Data Available: {financial_df['pass_data_available'].sum()}/{total_count}")
        self.logger.info(f"  Debt Ratio OK: {financial_df['pass_debt_ratio'].sum()}/{total_count}")
        self.logger.info(f"  Revenue Growth OK: {financial_df['pass_revenue_growth'].sum()}/{total_count}")
        self.logger.info(f"  Cash Flow OK: {financial_df['pass_cash_flow'].sum()}/{total_count}")
        self.logger.info(f"  Overall Passed: {passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)")
        
        return financial_df
    
    def _convert_results_to_symbols(self, results_df: pd.DataFrame, original_symbols: List[StockSymbol]) -> tuple:
        """결과 DataFrame을 StockSymbol 객체 리스트로 변환"""
        # 원본 심볼 딕셔너리 생성 (빠른 조회를 위해)
        symbol_dict = {symbol.code: symbol for symbol in original_symbols}
        
        passed_symbols = []
        failed_symbols = []
        
        for _, row in results_df.iterrows():
            symbol_code = row['symbol_code']
            symbol = symbol_dict.get(symbol_code)
            
            if symbol:
                if row['pass_all_criteria']:
                    passed_symbols.append(symbol)
                else:
                    failed_symbols.append(symbol)
                    # 탈락 사유 로깅
                    self.logger.debug(f"FAIL: {symbol_code} - {row['failure_reason']}")
        
        # 데이터가 없는 종목들도 탈락 처리
        processed_codes = set(results_df['symbol_code'])
        for symbol in original_symbols:
            if symbol.code not in processed_codes:
                failed_symbols.append(symbol)
                self.logger.debug(f"FAIL: {symbol.code} - No Data Collected")
        
        return passed_symbols, failed_symbols
    
    def _get_criteria_applied(self) -> Dict[str, Any]:
        """적용된 기준 정보 반환"""
        return {
            "max_debt_ratio_percent": self.config.max_debt_ratio_percent,
            "min_revenue_growth_percent": self.config.min_revenue_growth_percent,
            "cash_flow_quarters_required": self.config.cash_flow_quarters,
            "vectorized": True,  # 벡터화 버전임을 표시
            "failure_reasons_tracked": True  # 탈락 사유 추적 기능
        }