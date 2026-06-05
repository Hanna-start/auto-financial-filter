"""
벡터화된 품질성장 필터 - 고성능 트렌드 분석
- pandas rolling(), shift(), apply() 활용한 고속 트렌드 분석
- 복잡한 수익 피크 및 COGS 트렌드를 벡터화로 처리
- 대량 데이터에서도 빠른 성능 보장
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging

from ..models.base import StockSymbol, FilterResult, BaseFilter
from ..models.standardized_data import FilterResultWithReasons, FailureReason, StandardizedFinancialData
from ..config import FilterConfig


class VectorizedQualityGrowthFilter(BaseFilter):
    """벡터화된 품질성장 필터 - 고성능 트렌드 분석"""
    
    def __init__(self, config: FilterConfig, data_manager):
        super().__init__(config)
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)
    
    def get_stage_name(self) -> str:
        """필터 단계 이름 반환"""
        return "Quality Growth Filter (Vectorized)"
    
    def filter(self, symbols: List[StockSymbol]) -> FilterResultWithReasons:
        """벡터화된 품질성장 필터링 실행"""
        self.logger.info(f"Starting vectorized quality growth filtering for {len(symbols)} symbols")
        
        # 1단계: 모든 종목의 재무 데이터를 수집하여 통합 DataFrame 생성
        financial_df = self._collect_and_standardize_data(symbols)
        
        if financial_df.empty:
            return self._create_empty_result(symbols)
        
        # 2단계: 벡터화된 트렌드 분석
        analysis_df = self._perform_vectorized_analysis(financial_df)
        
        # 3단계: 결과 변환 및 반환
        return self._convert_to_result(analysis_df, symbols)
    
    def _collect_and_standardize_data(self, symbols: List[StockSymbol]) -> pd.DataFrame:
        """모든 종목의 데이터를 수집하고 분석용 DataFrame으로 변환"""
        records = []
        
        for symbol in symbols:
            try:
                financial_data = self.data_manager.get_financial_data(symbol)
                
                # 표준화된 데이터로 변환
                std_data = self._convert_to_standardized_data(symbol, financial_data)
                
                if std_data and std_data.validate():
                    # 분석용 레코드 생성
                    record = self._create_analysis_record(std_data)
                    records.append(record)
                else:
                    # 데이터 문제가 있는 경우
                    records.append(self._create_error_record(symbol, "Invalid Data"))
                    
            except Exception as e:
                self.logger.warning(f"Error collecting data for {symbol.code}: {e}")
                records.append(self._create_error_record(symbol, "Collection Error"))
        
        return pd.DataFrame(records)
    
    def _convert_to_standardized_data(self, symbol: StockSymbol, financial_data) -> Optional[StandardizedFinancialData]:
        """기존 데이터를 표준화된 형식으로 변환"""
        try:
            # Mock 데이터의 경우 간단한 변환
            if hasattr(financial_data, 'empty') and financial_data.empty:
                return None
            
            # 실제 구현에서는 각 어댑터별로 구현 필요
            # 여기서는 기본적인 구조만 제공
            return None
        except Exception:
            return None
    
    def _create_analysis_record(self, std_data: StandardizedFinancialData) -> Dict[str, Any]:
        """표준화된 데이터에서 분석용 레코드 생성"""
        latest = std_data.get_latest_quarter()
        
        # 영업이익 트렌드 (16분기)
        profit_trend = std_data.get_operating_profit_trend(years=4)
        
        # COGS 비율 트렌드 (6분기)
        cogs_trend = std_data.get_cogs_ratio_trend(quarters=6)
        
        return {
            'symbol_code': std_data.symbol_code,
            'symbol_name': std_data.symbol_name,
            'market': std_data.market,
            'data_available': True,
            'operating_margin': latest.operating_margin,
            'profit_trend_16q': profit_trend,
            'cogs_trend_6q': cogs_trend,
            'currency': std_data.currency
        }
    
    def _create_error_record(self, symbol: StockSymbol, error_type: str) -> Dict[str, Any]:
        """오류 레코드 생성"""
        return {
            'symbol_code': symbol.code,
            'symbol_name': symbol.name,
            'market': symbol.market,
            'data_available': False,
            'error_type': error_type,
            'operating_margin': np.nan,
            'profit_trend_16q': [],
            'cogs_trend_6q': []
        }
    
    def _perform_vectorized_analysis(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """벡터화된 트렌드 분석 수행"""
        # 데이터가 있는 종목만 분석
        valid_data = financial_df[financial_df['data_available'] == True].copy()
        
        if valid_data.empty:
            return financial_df
        
        # 1. 영업이익률 기준 (벡터화)
        valid_data['pass_operating_margin'] = (
            valid_data['operating_margin'] >= self.config.min_operating_margin_percent
        )
        
        # 2. 수익 피크 분석 (벡터화된 apply 사용)
        valid_data['pass_profit_peak'] = valid_data['profit_trend_16q'].apply(
            self._vectorized_profit_peak_analysis
        )
        
        # 3. COGS 트렌드 분석 (벡터화된 apply 사용)
        valid_data['pass_cogs_trend'] = valid_data['cogs_trend_6q'].apply(
            self._vectorized_cogs_trend_analysis
        )
        
        # 4. 전체 기준 통과 여부
        valid_data['pass_all_criteria'] = (
            valid_data['pass_operating_margin'] & 
            valid_data['pass_profit_peak'] & 
            valid_data['pass_cogs_trend']
        )
        
        # 5. 탈락 사유 분석 (벡터화된 조건부 로직)
        valid_data['failure_reason'] = np.where(
            ~valid_data['pass_operating_margin'], FailureReason.LOW_OPERATING_MARGIN.value,
            np.where(
                ~valid_data['pass_profit_peak'], FailureReason.NOT_PROFIT_PEAK.value,
                np.where(
                    ~valid_data['pass_cogs_trend'], FailureReason.COGS_TREND_POOR.value,
                    'Passed All Criteria'
                )
            )
        )
        
        # 원본 DataFrame에 결과 병합
        result_df = financial_df.copy()
        
        # 데이터가 없는 종목들 처리
        result_df['pass_all_criteria'] = False
        result_df['failure_reason'] = FailureReason.MISSING_DATA.value
        
        # 유효한 데이터 결과 업데이트
        for idx, row in valid_data.iterrows():
            mask = result_df['symbol_code'] == row['symbol_code']
            result_df.loc[mask, 'pass_all_criteria'] = row['pass_all_criteria']
            result_df.loc[mask, 'failure_reason'] = row['failure_reason']
            result_df.loc[mask, 'pass_operating_margin'] = row['pass_operating_margin']
            result_df.loc[mask, 'pass_profit_peak'] = row['pass_profit_peak']
            result_df.loc[mask, 'pass_cogs_trend'] = row['pass_cogs_trend']
        
        # 통계 로깅
        self._log_vectorized_statistics(result_df)
        
        return result_df
    
    def _vectorized_profit_peak_analysis(self, profit_trend: List[float]) -> bool:
        """벡터화된 수익 피크 분석"""
        if not profit_trend or len(profit_trend) < 16:
            return False
        
        # pandas Series로 변환하여 벡터화 연산 활용
        profit_series = pd.Series(profit_trend)
        
        # 4분기 rolling sum 계산 (벡터화)
        rolling_4q_sum = profit_series.rolling(window=4, min_periods=4).sum()
        
        # 최근 4분기 합계
        recent_4q_sum = rolling_4q_sum.iloc[-1]
        
        # 전체 기간 중 최대값
        max_4q_sum = rolling_4q_sum.max()
        
        # 최근 4분기가 최대값 이상이면 피크
        return recent_4q_sum >= max_4q_sum
    
    def _vectorized_cogs_trend_analysis(self, cogs_trend: List[float]) -> bool:
        """벡터화된 COGS 트렌드 분석"""
        if not cogs_trend or len(cogs_trend) < 6:
            return False
        
        # pandas Series로 변환
        cogs_series = pd.Series(cogs_trend)
        
        # 전반부 vs 후반부 평균 비교 (벡터화)
        first_half_avg = cogs_series.iloc[:3].mean()
        second_half_avg = cogs_series.iloc[3:].mean()
        
        # 최신 vs 가장 오래된 비교
        recent_vs_oldest = cogs_series.iloc[-1] < cogs_series.iloc[0]
        
        # 전체적 개선 또는 장기적 개선
        overall_improvement = second_half_avg < first_half_avg
        
        return overall_improvement or recent_vs_oldest
    
    def _log_vectorized_statistics(self, result_df: pd.DataFrame) -> None:
        """벡터화된 통계 로깅"""
        total_count = len(result_df)
        data_available_count = result_df['data_available'].sum()
        passed_count = result_df['pass_all_criteria'].sum()
        
        self.logger.info(f"Vectorized quality growth analysis results:")
        self.logger.info(f"  Total symbols: {total_count}")
        self.logger.info(f"  Data available: {data_available_count}")
        self.logger.info(f"  Passed all criteria: {passed_count}")
        
        if data_available_count > 0:
            # 각 기준별 통과율 (데이터가 있는 종목 기준)
            valid_data = result_df[result_df['data_available'] == True]
            
            if 'pass_operating_margin' in valid_data.columns:
                margin_pass = valid_data['pass_operating_margin'].sum()
                peak_pass = valid_data['pass_profit_peak'].sum()
                cogs_pass = valid_data['pass_cogs_trend'].sum()
                
                self.logger.info(f"  Operating margin pass: {margin_pass}/{data_available_count} ({margin_pass/data_available_count*100:.1f}%)")
                self.logger.info(f"  Profit peak pass: {peak_pass}/{data_available_count} ({peak_pass/data_available_count*100:.1f}%)")
                self.logger.info(f"  COGS trend pass: {cogs_pass}/{data_available_count} ({cogs_pass/data_available_count*100:.1f}%)")
    
    def _convert_to_result(self, analysis_df: pd.DataFrame, original_symbols: List[StockSymbol]) -> FilterResultWithReasons:
        """분석 결과를 FilterResultWithReasons로 변환"""
        symbol_dict = {symbol.code: symbol for symbol in original_symbols}
        
        passed_symbols = []
        failed_symbols = []
        failure_reasons = {}
        
        for _, row in analysis_df.iterrows():
            symbol_code = row['symbol_code']
            symbol = symbol_dict.get(symbol_code)
            
            if symbol:
                if row.get('pass_all_criteria', False):
                    passed_symbols.append(symbol)
                else:
                    failed_symbols.append(symbol)
                    # 탈락 사유 매핑
                    reason_str = row.get('failure_reason', FailureReason.MISSING_DATA.value)
                    failure_reasons[symbol_code] = FailureReason(reason_str)
        
        # 처리되지 않은 종목들 (데이터 수집 실패)
        processed_codes = set(analysis_df['symbol_code'])
        for symbol in original_symbols:
            if symbol.code not in processed_codes:
                failed_symbols.append(symbol)
                failure_reasons[symbol.code] = FailureReason.DATA_COLLECTION_ERROR
        
        return FilterResultWithReasons(
            passed_symbols=passed_symbols,
            failed_symbols=failed_symbols,
            failure_reasons=failure_reasons,
            stage="Quality Growth Filter (Vectorized)",
            criteria_applied=self._get_criteria_applied(),
            detailed_metrics=analysis_df  # 상세 분석 결과 포함
        )
    
    def _create_empty_result(self, symbols: List[StockSymbol]) -> FilterResultWithReasons:
        """빈 결과 생성 (모든 종목 탈락)"""
        failure_reasons = {
            symbol.code: FailureReason.MISSING_DATA 
            for symbol in symbols
        }
        
        return FilterResultWithReasons(
            passed_symbols=[],
            failed_symbols=symbols,
            failure_reasons=failure_reasons,
            stage="Quality Growth Filter (Vectorized)",
            criteria_applied=self._get_criteria_applied()
        )
    
    def _get_criteria_applied(self) -> Dict[str, Any]:
        """적용된 기준 정보"""
        return {
            "min_operating_margin_percent": self.config.min_operating_margin_percent,
            "profit_trend_years": self.config.profit_trend_years,
            "cogs_trend_quarters": self.config.cogs_trend_quarters,
            "vectorized": True,
            "trend_analysis_method": "pandas_rolling_operations",
            "failure_reasons_tracked": True
        }