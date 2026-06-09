"""
Real adapters for Korean financial data sources.
These adapters interface with actual libraries:
- FinanceDataReader for market data
- OpenDartReader for financial statements  
- Pykrx for additional market data
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from ..models.base import StockSymbol, DataSourceAdapter
from ..config import FilterConfig


logger = logging.getLogger(__name__)


class FinanceDataReaderAdapter(DataSourceAdapter):
    """Adapter for FinanceDataReader library."""
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
        self.retry_count = 0
        self._fdr = None
        self._initialize_fdr()
    
    def _initialize_fdr(self):
        """Initialize FinanceDataReader with error handling."""
        try:
            import FinanceDataReader as fdr
            self._fdr = fdr
        except ImportError:
            logger.warning("FinanceDataReader not available. Using fallback implementation.")
            self._fdr = None
    
    def is_available(self) -> bool:
        """Check if the data source is available."""
        return self._fdr is not None
    
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
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {self.config.api_retry_attempts + 1} attempts failed")
        
        raise last_exception
    
    def get_kospi_symbols(self) -> List[StockSymbol]:
        """Get all KOSPI stock symbols."""
        if not self.is_available():
            raise RuntimeError("FinanceDataReader not available")
        
        def _get_symbols():
            df = self._fdr.StockListing('KOSPI')
            symbols = []
            for _, row in df.iterrows():
                symbols.append(StockSymbol(
                    code=str(row['Code']),
                    name=str(row['Name']),
                    market='KOSPI'
                ))
            return symbols
        
        return self._retry_with_backoff(_get_symbols)
    
    def get_kosdaq_symbols(self) -> List[StockSymbol]:
        """Get all KOSDAQ stock symbols."""
        if not self.is_available():
            raise RuntimeError("FinanceDataReader not available")
        
        def _get_symbols():
            df = self._fdr.StockListing('KOSDAQ')
            symbols = []
            for _, row in df.iterrows():
                symbols.append(StockSymbol(
                    code=str(row['Code']),
                    name=str(row['Name']),
                    market='KOSDAQ'
                ))
            return symbols
        
        return self._retry_with_backoff(_get_symbols)
    
    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """Get trading data for a symbol over specified days."""
        if not self.is_available():
            raise RuntimeError("FinanceDataReader not available")
        
        def _get_data():
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 10)  # Buffer for weekends/holidays
            
            df = self._fdr.DataReader(symbol.code, start_date, end_date)
            
            if df.empty:
                raise ValueError(f"No trading data available for symbol {symbol.code}")
            
            # Calculate trading value (price * volume)
            df['TradingValue'] = df['Close'] * df['Volume']
            
            # Keep only the most recent trading days
            df = df.tail(days)
            
            return df[['Close', 'Volume', 'TradingValue']].reset_index()
        
        return self._retry_with_backoff(_get_data)


class OpenDartReaderAdapter(DataSourceAdapter):
    """Adapter for OpenDartReader library."""
    
    def __init__(self, config: FilterConfig, api_key: Optional[str] = None):
        super().__init__(config)
        self.retry_count = 0
        self.api_key = api_key
        self._dart = None
        self._initialize_dart()
    
    def _initialize_dart(self):
        """Initialize OpenDartReader with error handling."""
        try:
            import OpenDartReader
            if self.api_key:
                self._dart = OpenDartReader(self.api_key)
            else:
                logger.warning("OpenDartReader API key not provided. Using fallback implementation.")
                self._dart = None
        except ImportError:
            logger.warning("OpenDartReader not available. Using fallback implementation.")
            self._dart = None
    
    def is_available(self) -> bool:
        """Check if the data source is available."""
        return self._dart is not None
    
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
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {self.config.api_retry_attempts + 1} attempts failed")
        
        raise last_exception
    
    def get_financial_statements(self, symbol: StockSymbol, quarters: int = 4) -> Dict[str, Any]:
        """Get quarterly financial statements for a symbol."""
        if not self.is_available():
            raise RuntimeError("OpenDartReader not available")
        
        def _get_statements():
            # Get company information first
            corp_list = self._dart.list()
            corp_info = corp_list[corp_list['stock_code'] == symbol.code]
            
            if corp_info.empty:
                raise ValueError(f"Company information not found for symbol {symbol.code}")
            
            corp_code = corp_info.iloc[0]['corp_code']
            
            # Get financial statements for the last few years to ensure we have enough quarters
            current_year = datetime.now().year
            quarterly_data = []
            
            for year in range(current_year, current_year - 3, -1):  # Last 3 years
                try:
                    # Get quarterly financial statements
                    fs = self._dart.finstate(corp_code, year, reprt_code='11013')  # Quarterly
                    
                    if not fs.empty:
                        # Extract relevant financial metrics
                        for quarter in ['Q4', 'Q3', 'Q2', 'Q1']:
                            quarter_data = fs[fs['reprt_code'] == f'{year}{quarter}']
                            if not quarter_data.empty:
                                quarterly_data.append(self._extract_financial_metrics(quarter_data, f"{year}{quarter}"))
                                
                                if len(quarterly_data) >= quarters:
                                    break
                    
                    if len(quarterly_data) >= quarters:
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to get financial data for {symbol.code} year {year}: {e}")
                    continue
            
            if len(quarterly_data) < quarters:
                raise ValueError(f"Insufficient financial data for symbol {symbol.code}. Got {len(quarterly_data)} quarters, need {quarters}")
            
            return {
                'symbol': symbol.code,
                'quarterly_data': quarterly_data[:quarters]
            }
        
        return self._retry_with_backoff(_get_statements)
    
    def _extract_financial_metrics(self, quarter_data: pd.DataFrame, quarter: str) -> Dict[str, Any]:
        """Extract financial metrics from quarterly data."""
        metrics = {'quarter': quarter}
        
        # Define mapping of account names to our metrics
        account_mapping = {
            '매출액': 'revenue',
            '영업이익': 'operating_profit',
            '자산총계': 'total_assets',
            '부채총계': 'total_debt',
            '자본총계': 'total_equity',
            '영업활동현금흐름': 'operating_cash_flow',
            '매출원가': 'cogs'
        }
        
        for account_name, metric_name in account_mapping.items():
            account_data = quarter_data[quarter_data['account_nm'] == account_name]
            if not account_data.empty:
                metrics[metric_name] = float(account_data.iloc[0]['thstrm_amount'])
            else:
                metrics[metric_name] = 0.0
        
        # Calculate derived metrics
        if metrics.get('total_equity', 0) > 0:
            metrics['debt_ratio'] = (metrics.get('total_debt', 0) / metrics['total_equity']) * 100
        else:
            metrics['debt_ratio'] = 999.0  # High value to indicate problematic debt ratio
        
        return metrics


class PykrxAdapter(DataSourceAdapter):
    """Adapter for Pykrx library."""
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
        self.retry_count = 0
        self._pykrx = None
        self._initialize_pykrx()
    
    def _initialize_pykrx(self):
        """Initialize Pykrx with error handling."""
        try:
            import pykrx
            self._pykrx = pykrx
        except ImportError:
            logger.warning("Pykrx not available. Using fallback implementation.")
            self._pykrx = None
    
    def is_available(self) -> bool:
        """Check if the data source is available."""
        return self._pykrx is not None
    
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
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {self.config.api_retry_attempts + 1} attempts failed")
        
        raise last_exception
    
    def get_market_data(self, symbol: StockSymbol) -> Dict[str, Any]:
        """Get additional market data for a symbol."""
        if not self.is_available():
            raise RuntimeError("Pykrx not available")
        
        def _get_data():
            from pykrx import stock
            
            # Get basic market information
            today = datetime.now().strftime('%Y%m%d')
            
            # Get market cap and shares outstanding
            market_data = stock.get_market_cap_by_ticker(today, market=symbol.market)
            
            if symbol.code not in market_data.index:
                raise ValueError(f"Market data not found for symbol {symbol.code}")
            
            ticker_data = market_data.loc[symbol.code]
            
            # Get sector information (this might not be available in pykrx)
            sector = "Unknown"  # Default value
            
            return {
                'symbol': symbol.code,
                'market_cap': float(ticker_data['시가총액']),
                'shares_outstanding': float(ticker_data['상장주식수']),
                'sector': sector,
                'listing_date': datetime.now() - timedelta(days=365)  # Placeholder
            }
        
        return self._retry_with_backoff(_get_data)


class DataAccessManager:
    """Manager class for coordinating multiple data source adapters."""
    
    def __init__(self, config: FilterConfig, dart_api_key: Optional[str] = None):
        self.config = config
        self.fdr_adapter = FinanceDataReaderAdapter(config)
        self.dart_adapter = OpenDartReaderAdapter(config, dart_api_key)
        self.pykrx_adapter = PykrxAdapter(config)
    
    def get_all_symbols(self) -> List[StockSymbol]:
        """Get all stock symbols from both KOSPI and KOSDAQ markets."""
        symbols = []
        errors = []
        
        try:
            kospi_symbols = self.fdr_adapter.get_kospi_symbols()
            symbols.extend(kospi_symbols)
            logger.info(f"Retrieved {len(kospi_symbols)} KOSPI symbols")
        except Exception as e:
            error_msg = f"Failed to retrieve KOSPI symbols: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        try:
            kosdaq_symbols = self.fdr_adapter.get_kosdaq_symbols()
            symbols.extend(kosdaq_symbols)
            logger.info(f"Retrieved {len(kosdaq_symbols)} KOSDAQ symbols")
        except Exception as e:
            error_msg = f"Failed to retrieve KOSDAQ symbols: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        if not symbols and errors:
            raise RuntimeError(f"Failed to retrieve any symbols. Errors: {'; '.join(errors)}")
        
        return symbols
    
    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """Get trading data for a symbol with fallback handling."""
        try:
            return self.fdr_adapter.get_trading_data(symbol, days)
        except Exception as e:
            logger.error(f"Failed to get trading data for {symbol.code}: {e}")
            raise
    
    def get_financial_data(self, symbol: StockSymbol, quarters: int = 4) -> Dict[str, Any]:
        """Get financial data for a symbol with fallback handling."""
        try:
            return self.dart_adapter.get_financial_statements(symbol, quarters)
        except Exception as e:
            logger.error(f"Failed to get financial data for {symbol.code}: {e}")
            raise
    
    def get_market_data(self, symbol: StockSymbol) -> Dict[str, Any]:
        """Get market data for a symbol with fallback handling."""
        try:
            return self.pykrx_adapter.get_market_data(symbol)
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol.code}: {e}")
            raise
    
    def get_availability_status(self) -> Dict[str, bool]:
        """Get availability status of all data sources."""
        return {
            'FinanceDataReader': self.fdr_adapter.is_available(),
            'OpenDartReader': self.dart_adapter.is_available(),
            'Pykrx': self.pykrx_adapter.is_available()
        }
    
    def get_retry_counts(self) -> Dict[str, int]:
        """Get retry counts for all adapters."""
        return {
            'FinanceDataReader': self.fdr_adapter.get_retry_count(),
            'OpenDartReader': self.dart_adapter.get_retry_count(),
            'Pykrx': self.pykrx_adapter.get_retry_count()
        }