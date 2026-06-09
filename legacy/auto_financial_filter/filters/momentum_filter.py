"""
Momentum and Trend Filter
Filters out stocks that are fundamentally good but in a severe downtrend (e.g., below 120-day moving average).
"""

from typing import List, Dict, Any, Tuple
import logging
from ..models.base import StockSymbol, FilterResult, BaseFilter
from ..config import FilterConfig

class MomentumFilter(BaseFilter):
    """Stage 4: Momentum and Trend Filter"""
    
    def __init__(self, config: FilterConfig, data_manager):
        super().__init__(config)
        self.data_manager = data_manager
        self.ma_days = 120
        self.logger = logging.getLogger(__name__)
        
    def get_stage_name(self) -> str:
        return "4단계: 모멘텀 및 추세 필터"
    
    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        self.logger.info(f"Starting momentum filtering for {len(symbols)} symbols")
        passed_symbols = []
        failed_symbols = []
        
        criteria_applied = {
            "ma_days": self.ma_days,
            "min_price_to_ma_ratio": 0.95
        }
        
        for symbol in symbols:
            try:
                df = self.data_manager.get_trading_data(symbol, self.ma_days)
                if df.empty or len(df) < min(60, self.ma_days // 2):
                    self.logger.warning(f"Insufficient trading data for {symbol.code}")
                    failed_symbols.append(symbol)
                    continue
                
                ma_value = df['Close'].mean()
                current_price = df['Close'].iloc[-1]
                threshold = ma_value * 0.95
                
                if current_price < threshold:
                    self.logger.info(f"FAIL: {symbol.code} - Price {current_price:,.0f} < 120MA {ma_value:,.0f}")
                    failed_symbols.append(symbol)
                else:
                    self.logger.info(f"PASS: {symbol.code} - Price {current_price:,.0f} >= 120MA {ma_value:,.0f}")
                    passed_symbols.append(symbol)
                    
            except Exception as e:
                self.logger.error(f"Error in MomentumFilter for {symbol.code}: {e}")
                failed_symbols.append(symbol)
                
        result = FilterResult(
            passed_symbols=passed_symbols,
            failed_symbols=failed_symbols,
            stage=self.get_stage_name(),
            criteria_applied=criteria_applied
        )
        return result
