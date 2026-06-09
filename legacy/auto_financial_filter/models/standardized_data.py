"""
표준화된 데이터 모델 - 데이터 계약 (Data Contract)
- 모든 데이터 어댑터가 동일한 형식으로 데이터 반환
- 타입 힌팅으로 데이터 구조 명확화
- 한국/미국 시장 구분 없이 통일된 처리
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import pandas as pd
from enum import Enum


class FailureReason(Enum):
    """탈락 사유 열거형"""
    MISSING_DATA = "Missing Data"
    DEBT_RATIO_EXCEEDED = "Debt Ratio Exceeded"
    REVENUE_GROWTH_BELOW = "Revenue Growth Below Threshold"
    NEGATIVE_CASH_FLOW = "Negative Cash Flow"
    LOW_OPERATING_MARGIN = "Operating Margin Below Threshold"
    NOT_PROFIT_PEAK = "Not Profit Peak"
    COGS_TREND_POOR = "COGS Trend Not Improving"
    LOW_TRADING_VOLUME = "Trading Volume Below Threshold"
    DATA_COLLECTION_ERROR = "Data Collection Error"


@dataclass
class StandardizedQuarterlyData:
    """표준화된 분기별 재무 데이터"""
    quarter: str                    # "2024Q1" 형식
    revenue: float                  # 매출 (원화 또는 달러)
    operating_profit: float         # 영업이익
    operating_margin: float         # 영업이익률 (%)
    total_assets: float            # 총자산
    total_debt: float              # 총부채
    total_equity: float            # 총자본
    debt_ratio: float              # 부채비율 (%)
    operating_cash_flow: float     # 영업현금흐름
    cogs: float                    # 매출원가
    cogs_ratio: float              # 매출원가율 (COGS/Revenue)
    
    def validate(self) -> bool:
        """데이터 유효성 검증"""
        return (
            self.revenue >= 0 and
            self.total_assets >= 0 and
            self.total_debt >= 0 and
            self.total_equity > 0 and  # 자본은 양수여야 함
            0 <= self.operating_margin <= 100 and
            0 <= self.cogs_ratio <= 1.0
        )


@dataclass
class StandardizedTradingData:
    """표준화된 거래 데이터"""
    symbol_code: str
    period_days: int
    daily_data: pd.DataFrame       # Date, Close, Volume, TradingValue 컬럼
    avg_daily_volume: float        # 일평균 거래량
    avg_daily_value: float         # 일평균 거래대금 (원화 기준)
    
    def validate(self) -> bool:
        """데이터 유효성 검증"""
        required_columns = ['Date', 'Close', 'Volume', 'TradingValue']
        return (
            all(col in self.daily_data.columns for col in required_columns) and
            len(self.daily_data) > 0 and
            self.avg_daily_volume >= 0 and
            self.avg_daily_value >= 0
        )


@dataclass
class StandardizedFinancialData:
    """표준화된 재무 데이터 - 모든 어댑터가 이 형식으로 반환"""
    symbol_code: str
    symbol_name: str
    market: str
    currency: str                           # "KRW" 또는 "USD"
    quarterly_data: List[StandardizedQuarterlyData]  # 최신순 정렬 (최신이 [0])
    data_collection_date: datetime
    data_source: str                        # "KRX", "yfinance", "SEC" 등
    
    def validate(self) -> bool:
        """데이터 유효성 검증"""
        return (
            len(self.quarterly_data) >= 4 and  # 최소 4분기 데이터 필요
            all(quarter.validate() for quarter in self.quarterly_data) and
            self.currency in ["KRW", "USD"] and
            len(self.symbol_code) > 0
        )
    
    def get_latest_quarter(self) -> StandardizedQuarterlyData:
        """최신 분기 데이터 반환"""
        return self.quarterly_data[0]
    
    def get_revenue_growth_yoy(self) -> float:
        """전년동기 대비 매출성장률 계산"""
        if len(self.quarterly_data) < 4:
            return 0.0
        
        current_revenue = self.quarterly_data[0].revenue  # 최신 분기
        previous_year_revenue = self.quarterly_data[3].revenue  # 1년 전 분기
        
        if previous_year_revenue <= 0:
            return 0.0
        
        return ((current_revenue - previous_year_revenue) / previous_year_revenue) * 100
    
    def get_cash_flow_positive_quarters(self) -> int:
        """현금흐름 양수 분기 수 계산"""
        return sum(1 for quarter in self.quarterly_data[:4] if quarter.operating_cash_flow > 0)
    
    def get_operating_profit_trend(self, years: int = 4) -> List[float]:
        """영업이익 트렌드 데이터 반환 (분기별)"""
        quarters_needed = years * 4
        if len(self.quarterly_data) < quarters_needed:
            # 데이터가 부족하면 사용 가능한 만큼만 반환
            return [q.operating_profit for q in self.quarterly_data]
        
        return [q.operating_profit for q in self.quarterly_data[:quarters_needed]]
    
    def get_cogs_ratio_trend(self, quarters: int = 6) -> List[float]:
        """매출원가율 트렌드 데이터 반환"""
        if len(self.quarterly_data) < quarters:
            return [q.cogs_ratio for q in self.quarterly_data]
        
        return [q.cogs_ratio for q in self.quarterly_data[:quarters]]


@dataclass
class FilterResultWithReasons:
    """탈락 사유가 포함된 필터링 결과"""
    passed_symbols: List[StockSymbol]
    failed_symbols: List[StockSymbol]
    failure_reasons: Dict[str, FailureReason]  # symbol_code -> FailureReason
    stage: str
    criteria_applied: Dict[str, Any]
    detailed_metrics: Optional[pd.DataFrame] = None  # 상세 지표 (선택사항)
    
    @property
    def total_processed(self) -> int:
        """총 처리된 종목 수"""
        return len(self.passed_symbols) + len(self.failed_symbols)
    
    @property
    def pass_rate(self) -> float:
        """통과율 (백분율)"""
        if self.total_processed == 0:
            return 0.0
        return len(self.passed_symbols) / self.total_processed * 100
    
    def get_failure_summary(self) -> Dict[FailureReason, int]:
        """탈락 사유별 통계"""
        summary = {}
        for reason in self.failure_reasons.values():
            summary[reason] = summary.get(reason, 0) + 1
        return summary
    
    def export_detailed_results(self) -> pd.DataFrame:
        """상세 결과를 DataFrame으로 내보내기"""
        results = []
        
        # 통과한 종목들
        for symbol in self.passed_symbols:
            results.append({
                'symbol_code': symbol.code,
                'symbol_name': symbol.name,
                'market': symbol.market,
                'result': 'PASS',
                'failure_reason': None
            })
        
        # 탈락한 종목들
        for symbol in self.failed_symbols:
            reason = self.failure_reasons.get(symbol.code, FailureReason.DATA_COLLECTION_ERROR)
            results.append({
                'symbol_code': symbol.code,
                'symbol_name': symbol.name,
                'market': symbol.market,
                'result': 'FAIL',
                'failure_reason': reason.value
            })
        
        df = pd.DataFrame(results)
        
        # 상세 지표가 있으면 병합
        if self.detailed_metrics is not None:
            df = df.merge(self.detailed_metrics, on='symbol_code', how='left')
        
        return df


class DataStandardizer:
    """데이터 표준화 유틸리티 클래스"""
    
    @staticmethod
    def convert_to_krw(amount: float, currency: str, exchange_rate: float = 1300.0) -> float:
        """외화를 원화로 변환"""
        if currency == "KRW":
            return amount
        elif currency == "USD":
            return amount * exchange_rate
        else:
            raise ValueError(f"Unsupported currency: {currency}")
    
    @staticmethod
    def normalize_trading_value(trading_data: StandardizedTradingData, target_currency: str = "KRW") -> StandardizedTradingData:
        """거래대금을 목표 통화로 정규화"""
        if trading_data.daily_data.empty:
            return trading_data
        
        # 거래대금이 이미 목표 통화라면 그대로 반환
        # 실제 구현에서는 통화 정보를 trading_data에 포함해야 함
        return trading_data
    
    @staticmethod
    def validate_financial_data(data: StandardizedFinancialData) -> List[str]:
        """재무 데이터 유효성 검증 및 오류 목록 반환"""
        errors = []
        
        if not data.validate():
            errors.append("Basic validation failed")
        
        # 추가 비즈니스 로직 검증
        latest = data.get_latest_quarter()
        
        if latest.debt_ratio > 1000:  # 부채비율 1000% 초과는 비정상
            errors.append("Abnormally high debt ratio")
        
        if latest.operating_margin < -100:  # 영업이익률 -100% 미만은 비정상
            errors.append("Abnormally low operating margin")
        
        if len(data.quarterly_data) < 4:
            errors.append("Insufficient quarterly data (need at least 4 quarters)")
        
        return errors