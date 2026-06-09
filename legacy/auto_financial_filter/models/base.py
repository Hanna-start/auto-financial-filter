"""Base data models for the financial stock filter system."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


@dataclass
class StockSymbol:
    """Represents a stock symbol with market information."""
    code: str
    name: str
    market: str  # 'KOSPI', 'KOSDAQ', 'NYSE', 'NASDAQ', etc.
    
    def __post_init__(self):
        self.validate()
    
    def validate(self) -> None:
        """Validate the stock symbol data."""
        if not self.code or not self.code.strip():
            raise ValueError("Stock code cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("Stock name cannot be empty")
        
        # Support both Korean and US markets
        valid_markets = ['KOSPI', 'KOSDAQ', 'NYSE', 'NASDAQ', 'AMEX', 'OTC', '비상장']
        if self.market not in valid_markets:
            raise ValueError(f"Market must be one of {valid_markets}, got: {self.market}")
        
    def is_valid(self) -> bool:
        """Check if the stock symbol is valid without raising exceptions."""
        try:
            self.validate()
            return True
        except ValueError:
            return False
    
    def is_korean_market(self) -> bool:
        """Check if this is a Korean market stock."""
        return self.market in ['KOSPI', 'KOSDAQ']
    
    def is_us_market(self) -> bool:
        """Check if this is a US market stock."""
        return self.market in ['NYSE', 'NASDAQ', 'AMEX', 'OTC']


@dataclass
class LiquidityMetrics:
    """Liquidity metrics for a stock symbol."""
    symbol: StockSymbol
    avg_daily_volume: float
    avg_daily_value: float  # KRW
    period_days: int
    
    def __post_init__(self):
        self.validate()
    
    def validate(self) -> None:
        """Validate the liquidity metrics data."""
        if not isinstance(self.symbol, StockSymbol):
            raise ValueError("Symbol must be a StockSymbol instance")
        self.symbol.validate()
        
        if self.avg_daily_volume < 0:
            raise ValueError("Average daily volume cannot be negative")
        if self.avg_daily_value < 0:
            raise ValueError("Average daily value cannot be negative")
        if self.period_days <= 0:
            raise ValueError("Period days must be positive")
        
    def is_valid(self) -> bool:
        """Check if the liquidity metrics are valid without raising exceptions."""
        try:
            self.validate()
            return True
        except ValueError:
            return False


@dataclass
class FinancialMetrics:
    """Financial health metrics for a stock symbol."""
    symbol: StockSymbol
    debt_ratio: float
    operating_cash_flow: List[float]  # 4 quarters
    revenue_growth_yoy: float
    quarterly_revenue: List[float]
    
    def __post_init__(self):
        self.validate()
    
    def validate(self) -> None:
        """Validate the financial metrics data."""
        if not isinstance(self.symbol, StockSymbol):
            raise ValueError("Symbol must be a StockSymbol instance")
        self.symbol.validate()
        
        if self.debt_ratio < 0:
            raise ValueError("Debt ratio cannot be negative")
        
        if len(self.operating_cash_flow) != 4:
            raise ValueError("Operating cash flow must contain exactly 4 quarters of data")
        
        if len(self.quarterly_revenue) != 4:
            raise ValueError("Quarterly revenue must contain exactly 4 quarters of data")
        
        if any(revenue < 0 for revenue in self.quarterly_revenue):
            raise ValueError("Quarterly revenue values cannot be negative")
        
    def is_valid(self) -> bool:
        """Check if the financial metrics are valid without raising exceptions."""
        try:
            self.validate()
            return True
        except ValueError:
            return False


@dataclass
class ProfitabilityMetrics:
    """Profitability and trend metrics for a stock symbol."""
    symbol: StockSymbol
    operating_margin: float
    operating_profit_trend: List[float]  # 4 years
    cogs_ratio_trend: List[float]  # 6 quarters
    is_profit_peak: bool
    
    def __post_init__(self):
        self.validate()
    
    def validate(self) -> None:
        """Validate the profitability metrics data."""
        if not isinstance(self.symbol, StockSymbol):
            raise ValueError("Symbol must be a StockSymbol instance")
        self.symbol.validate()
        
        if len(self.operating_profit_trend) != 16:
            raise ValueError("Operating profit trend must contain exactly 16 quarters (4 years) of data")
        
        if len(self.cogs_ratio_trend) != 6:
            raise ValueError("COGS ratio trend must contain exactly 6 quarters of data")
        
        if any(ratio < 0 for ratio in self.cogs_ratio_trend):
            raise ValueError("COGS ratio values cannot be negative")
        
        if not isinstance(self.is_profit_peak, bool):
            raise ValueError("is_profit_peak must be a boolean value")
        
    def is_valid(self) -> bool:
        """Check if the profitability metrics are valid without raising exceptions."""
        try:
            self.validate()
            return True
        except ValueError:
            return False


@dataclass
class FilterResult:
    """Result of a filtering stage."""
    passed_symbols: List[StockSymbol]
    failed_symbols: List[StockSymbol]
    stage: str
    criteria_applied: Dict[str, Any]
    
    def __post_init__(self):
        self.validate()
    
    def validate(self) -> None:
        """Validate the filter result data."""
        if not isinstance(self.passed_symbols, list):
            raise ValueError("passed_symbols must be a list")
        if not isinstance(self.failed_symbols, list):
            raise ValueError("failed_symbols must be a list")
        
        # Validate all symbols in both lists
        for symbol in self.passed_symbols:
            if not isinstance(symbol, StockSymbol):
                raise ValueError("All passed symbols must be StockSymbol instances")
            symbol.validate()
            
        for symbol in self.failed_symbols:
            if not isinstance(symbol, StockSymbol):
                raise ValueError("All failed symbols must be StockSymbol instances")
            symbol.validate()
        
        if not self.stage or not self.stage.strip():
            raise ValueError("Stage name cannot be empty")
        
        if not isinstance(self.criteria_applied, dict):
            raise ValueError("criteria_applied must be a dictionary")
        
        # Check for duplicate symbols between passed and failed
        passed_codes = {symbol.code for symbol in self.passed_symbols}
        failed_codes = {symbol.code for symbol in self.failed_symbols}
        overlap = passed_codes.intersection(failed_codes)
        if overlap:
            raise ValueError(f"Symbols cannot appear in both passed and failed lists: {overlap}")
    
    def is_valid(self) -> bool:
        """Check if the filter result is valid without raising exceptions."""
        try:
            self.validate()
            return True
        except ValueError:
            return False
    
    @property
    def total_processed(self) -> int:
        """Total number of symbols processed."""
        return len(self.passed_symbols) + len(self.failed_symbols)
    
    @property
    def pass_rate(self) -> float:
        """Percentage of symbols that passed the filter."""
        if self.total_processed == 0:
            return 0.0
        return len(self.passed_symbols) / self.total_processed * 100


class BaseFilter(ABC):
    """Abstract base class for all filter implementations."""
    
    def __init__(self, config: 'FilterConfig'):
        self.config = config
    
    @abstractmethod
    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        """
        Apply the filter to a list of stock symbols.
        
        Args:
            symbols: List of stock symbols to filter
            
        Returns:
            FilterResult containing passed and failed symbols
        """
        pass
    
    @abstractmethod
    def get_stage_name(self) -> str:
        """Get the name of this filtering stage."""
        pass


class DataSourceAdapter(ABC):
    """Abstract base class for data source adapters."""
    
    def __init__(self, config: 'FilterConfig'):
        self.config = config
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the data source is available."""
        pass
    
    @abstractmethod
    def get_retry_count(self) -> int:
        """Get the number of retry attempts for this adapter."""
        pass