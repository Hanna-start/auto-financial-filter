"""
Mock adapters for Korean financial data sources.
In a real implementation, these would interface with actual libraries:
- FinanceDataReader for market data
- OpenDartReader for financial statements  
- Pykrx for additional market data
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime, timedelta
import random
from ..models.base import StockSymbol, DataSourceAdapter
from ..config import FilterConfig


class MockFinanceDataReaderAdapter(DataSourceAdapter):
    """Mock adapter for FinanceDataReader library."""
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
        self.retry_count = 0
    
    def is_available(self) -> bool:
        """Check if the data source is available."""
        return True
    
    def get_retry_count(self) -> int:
        """Get the number of retry attempts for this adapter."""
        return self.retry_count
    
    def get_kospi_symbols(self) -> List[StockSymbol]:
        """Get all KOSPI stock symbols."""
        # Mock KOSPI symbols
        symbols = []
        for i in range(1, 101):  # Mock 100 KOSPI stocks
            code = f"{i:06d}"
            name = f"KOSPI주식{i}"
            symbols.append(StockSymbol(code=code, name=name, market="KOSPI"))
        return symbols
    
    def get_kosdaq_symbols(self) -> List[StockSymbol]:
        """Get all KOSDAQ stock symbols."""
        # Mock KOSDAQ symbols
        symbols = []
        for i in range(100001, 100051):  # Mock 50 KOSDAQ stocks
            code = f"{i}"
            name = f"KOSDAQ주식{i-100000}"
            symbols.append(StockSymbol(code=code, name=name, market="KOSDAQ"))
        return symbols
    
    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """Get trading data for a symbol over specified days."""
        # Generate mock trading data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        # Filter to business days only
        dates = dates[dates.weekday < 5]
        
        data = []
        base_price = random.uniform(10000, 100000)  # Base price in KRW
        base_volume = random.uniform(100000, 10000000)  # Base volume
        
        for date in dates:
            # Simulate price and volume fluctuations
            price = base_price * random.uniform(0.95, 1.05)
            volume = base_volume * random.uniform(0.5, 2.0)
            trading_value = price * volume
            
            data.append({
                'Date': date,
                'Close': price,
                'Volume': volume,
                'TradingValue': trading_value
            })
        
        return pd.DataFrame(data)


class MockOpenDartReaderAdapter(DataSourceAdapter):
    """Mock adapter for OpenDartReader library."""
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
        self.retry_count = 0
    
    def is_available(self) -> bool:
        """Check if the data source is available."""
        return True
    
    def get_retry_count(self) -> int:
        """Get the number of retry attempts for this adapter."""
        return self.retry_count
    
    def get_financial_statements(self, symbol: StockSymbol, quarters: int = 4) -> Dict[str, Any]:
        """Get quarterly financial statements for a symbol."""
        # Generate mock financial data
        quarterly_data = []
        
        for i in range(quarters):
            # Mock financial metrics with some realistic ranges
            revenue = random.uniform(50_000_000_000, 500_000_000_000)  # 50B-500B KRW
            operating_profit = revenue * random.uniform(0.05, 0.25)  # 5-25% margin
            total_assets = revenue * random.uniform(2, 8)  # Asset turnover
            total_debt = total_assets * random.uniform(0.2, 0.8)  # Debt ratio
            total_equity = total_assets - total_debt
            operating_cash_flow = operating_profit * random.uniform(0.8, 1.5)
            cogs = revenue * random.uniform(0.6, 0.9)  # COGS ratio
            
            quarterly_data.append({
                'quarter': f"2024Q{4-i}",
                'revenue': revenue,
                'operating_profit': operating_profit,
                'total_assets': total_assets,
                'total_debt': total_debt,
                'total_equity': total_equity,
                'operating_cash_flow': operating_cash_flow,
                'cogs': cogs,
                'debt_ratio': (total_debt / total_equity) * 100 if total_equity > 0 else 999
            })
        
        return {
            'symbol': symbol.code,
            'quarterly_data': quarterly_data
        }


class MockPykrxAdapter(DataSourceAdapter):
    """Mock adapter for Pykrx library."""
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
        self.retry_count = 0
    
    def is_available(self) -> bool:
        """Check if the data source is available."""
        return True
    
    def get_retry_count(self) -> int:
        """Get the number of retry attempts for this adapter."""
        return self.retry_count
    
    def get_market_data(self, symbol: StockSymbol) -> Dict[str, Any]:
        """Get additional market data for a symbol."""
        # Mock additional market metrics
        return {
            'symbol': symbol.code,
            'market_cap': random.uniform(100_000_000_000, 10_000_000_000_000),  # 100B-10T KRW
            'shares_outstanding': random.uniform(10_000_000, 1_000_000_000),
            'sector': random.choice(['Technology', 'Finance', 'Manufacturing', 'Healthcare', 'Energy']),
            'listing_date': datetime.now() - timedelta(days=random.randint(365, 3650))
        }


class MockDataAccessManager:
    """Mock manager class for coordinating multiple data source adapters."""
    
    def __init__(self, config: FilterConfig):
        self.config = config
        self.fdr_adapter = MockFinanceDataReaderAdapter(config)
        self.dart_adapter = MockOpenDartReaderAdapter(config)
        self.pykrx_adapter = MockPykrxAdapter(config)
    
    def get_all_symbols(self) -> List[StockSymbol]:
        """Get all stock symbols from both KOSPI and KOSDAQ markets."""
        symbols = []
        symbols.extend(self.fdr_adapter.get_kospi_symbols())
        symbols.extend(self.fdr_adapter.get_kosdaq_symbols())
        return symbols
    
    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """Get trading data for a symbol."""
        return self.fdr_adapter.get_trading_data(symbol, days)
    
    def get_financial_data(self, symbol: StockSymbol, quarters: int = 4) -> Dict[str, Any]:
        """Get financial data for a symbol."""
        return self.dart_adapter.get_financial_statements(symbol, quarters)
    
    def get_market_data(self, symbol: StockSymbol) -> Dict[str, Any]:
        """Get market data for a symbol."""
        return self.pykrx_adapter.get_market_data(symbol)
    
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