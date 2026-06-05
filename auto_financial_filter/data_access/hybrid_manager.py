"""
HybridDataAccessManager — 가격은 yfinance, 재무는 실제 screener.db.

재무선배 기준을 진짜 데이터로 돌리기 위한 데이터 매니저.
- 1·4단계(유동성·모멘텀): 주가/거래량이 필요 → yfinance (DART에는 주가가 없음)
- 2·3단계(재무건전성·품질성장): 실제 재무 → screener.db (연 단위)

종목 코드는 6자리 한국 종목코드(StockSymbol.code)를 사용한다.
"""

from typing import List, Dict, Any, Optional
import logging

import pandas as pd

from ..config import FilterConfig
from ..models.base import StockSymbol
from .alternative_adapters import YFinanceKoreanAdapter
from .screener_db_adapter import ScreenerDBAdapter, DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


class HybridDataAccessManager:
    """가격=yfinance, 재무=screener.db 하이브리드 매니저."""

    def __init__(
        self,
        config: FilterConfig,
        db_path: str = DEFAULT_DB_PATH,
        require_financials: bool = True,
    ):
        self.config = config
        self.require_financials = require_financials
        self.price_adapter = YFinanceKoreanAdapter(config)       # 가격(거래량/이동평균)
        self.db_adapter = ScreenerDBAdapter(config, db_path)      # 실제 재무

    def get_all_symbols(self) -> List[StockSymbol]:
        """screener.db 기준 상장사 목록(기본: 실제 재무 보유 회사만)."""
        symbols = self.db_adapter.get_listed_symbols(
            require_financials=self.require_financials
        )
        logger.info(f"Hybrid: loaded {len(symbols)} symbols from screener.db")
        return symbols

    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """가격/거래량 — yfinance에서 실시간 조회 (1·4단계용)."""
        return self.price_adapter.get_trading_data(symbol, days)

    def get_financial_data(self, symbol: StockSymbol, quarters: int = 4) -> Dict[str, Any]:
        """
        실제 재무 — screener.db에서 연 단위 조회 (2·3단계용).
        반환: {'symbol', 'annual_data': [...]}  (연 단위 필터가 소비)
        호환을 위해 quarters 인자는 '연 수'로 해석한다.
        """
        years = max(quarters, 1)
        return self.db_adapter.get_financial_statements(symbol, years=max(years, 5))

    def get_market_data(self, symbol: StockSymbol) -> Dict[str, Any]:
        """시가총액 등은 현재 미사용. 최소 정보만 반환."""
        return {
            "symbol": symbol.code,
            "market_cap": None,
            "shares_outstanding": None,
            "sector": "Unknown",
        }

    def get_availability_status(self) -> Dict[str, bool]:
        return {
            "YFinance_Price": self.price_adapter.is_available(),
            "ScreenerDB_Financials": self.db_adapter.is_available(),
        }

    def get_retry_counts(self) -> Dict[str, int]:
        return {
            "YFinance_Price": self.price_adapter.get_retry_count(),
            "ScreenerDB_Financials": self.db_adapter.get_retry_count(),
        }
