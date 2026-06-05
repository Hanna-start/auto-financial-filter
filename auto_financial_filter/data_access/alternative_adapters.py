"""
yfinance 기반 한국 주가 어댑터.

가격/거래량(1·4단계: 유동성·모멘텀) 데이터를 yfinance에서 가져온다.
재무(2·3단계)는 screener_db_adapter.py(실제 DART)를 쓴다.

과거 이 파일에 있던 WebScrapingFinancialAdapter / AlternativeDataAccessManager는
재무 수치를 random.uniform()으로 지어내는 가짜 생성기였으며 제거되었다.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime, timedelta
import time
import logging

from ..models.base import StockSymbol, DataSourceAdapter
from ..config import FilterConfig

logger = logging.getLogger(__name__)


class YFinanceKoreanAdapter(DataSourceAdapter):
    """Alternative adapter using yfinance for Korean stocks."""
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
        self.retry_count = 0
        self._yf = None
        self._initialize_yf()
    
    def _initialize_yf(self):
        """Initialize yfinance with error handling."""
        try:
            import yfinance as yf
            self._yf = yf
        except ImportError:
            logger.warning("yfinance not available. Using fallback implementation.")
            self._yf = None
    
    def is_available(self) -> bool:
        """Check if the data source is available."""
        return self._yf is not None
    
    def get_retry_count(self) -> int:
        """Get the number of retry attempts for this adapter."""
        return self.retry_count
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with retry logic and exponential backoff."""
        last_exception = None
        
        for attempt in range(self.config.api_retry_attempts + 1):
            try:
                self.retry_count = attempt
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.config.api_retry_attempts:
                    wait_time = 2 ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {self.config.api_retry_attempts + 1} attempts failed")
        
        raise last_exception
    
    def get_korean_symbols(self) -> List[StockSymbol]:
        """Get major Korean stock symbols using known tickers."""
        # Major Korean stocks available on international exchanges
        major_korean_stocks = [
            ("005930.KS", "Samsung Electronics", "KOSPI"),
            ("000660.KS", "SK Hynix", "KOSPI"),
            ("035420.KS", "NAVER", "KOSDAQ"),
            ("051910.KS", "LG Chem", "KOSPI"),
            ("006400.KS", "Samsung SDI", "KOSPI"),
            ("207940.KS", "Samsung Biologics", "KOSPI"),
            ("005380.KS", "Hyundai Motor", "KOSPI"),
            ("000270.KS", "Kia", "KOSPI"),
            ("068270.KS", "Celltrion", "KOSPI"),
            ("003670.KS", "POSCO Holdings", "KOSPI"),
            ("096770.KS", "SK Innovation", "KOSPI"),
            ("034730.KS", "SK", "KOSPI"),
            ("066570.KS", "LG Electronics", "KOSPI"),
            ("035720.KS", "Kakao", "KOSPI"),
            ("028260.KS", "Samsung C&T", "KOSPI"),
            ("012330.KS", "Hyundai Mobis", "KOSPI"),
            ("105560.KS", "KB Financial", "KOSPI"),
            ("055550.KS", "Shinhan Financial", "KOSPI"),
            ("086790.KS", "Hana Financial", "KOSPI"),
            ("017670.KS", "SK Telecom", "KOSPI"),
            ("030200.KS", "KT", "KOSPI"),
            ("036570.KS", "NCSoft", "KOSPI"),
            ("251270.KS", "Netmarble", "KOSPI"),
            ("323410.KS", "Kakao Bank", "KOSPI"),
            ("373220.KS", "LG Energy Solution", "KOSPI"),
        ]
        
        symbols = []
        for ticker, name, market in major_korean_stocks:
            # Extract Korean stock code (remove .KS suffix)
            code = ticker.replace('.KS', '')
            symbols.append(StockSymbol(code=code, name=name, market=market))
        
        return symbols
    
    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """Get trading data for a symbol using yfinance."""
        if not self.is_available():
            raise RuntimeError("yfinance not available")
        
        def _get_data():
            # Convert Korean stock code to yfinance format
            ticker = f"{symbol.code}.KS"
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 10)
            
            stock = self._yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                raise ValueError(f"No trading data available for symbol {symbol.code}")
            
            # Rename columns to match expected format
            df = df.rename(columns={'Close': 'Close', 'Volume': 'Volume'})
            
            # Drop NaN values that might occur on holidays or current day
            df = df.dropna(subset=['Close', 'Volume'])
            
            # Calculate trading value (price * volume)
            df['TradingValue'] = df['Close'] * df['Volume']
            
            # Keep only the most recent trading days
            df = df.tail(days)
            
            return df[['Close', 'Volume', 'TradingValue']].reset_index()
        
        return self._retry_with_backoff(_get_data)
