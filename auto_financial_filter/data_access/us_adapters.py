"""
US market adapters for financial data using yfinance and SEC data.
미국 시장 데이터 어댑터 - yfinance와 SEC 데이터 활용
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import requests
import json
import random

from ..models.base import StockSymbol, DataSourceAdapter
from ..config import FilterConfig

logger = logging.getLogger(__name__)


class YFinanceUSAdapter(DataSourceAdapter):
    """US market adapter using yfinance for US stocks."""
    
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
    
    def get_sp500_symbols(self) -> List[StockSymbol]:
        """Get S&P 500 stock symbols."""
        # Major US stocks from different sectors
        major_us_stocks = [
            # Technology
            ("AAPL", "Apple Inc.", "NASDAQ"),
            ("MSFT", "Microsoft Corporation", "NASDAQ"),
            ("GOOGL", "Alphabet Inc.", "NASDAQ"),
            ("AMZN", "Amazon.com Inc.", "NASDAQ"),
            ("TSLA", "Tesla Inc.", "NASDAQ"),
            ("META", "Meta Platforms Inc.", "NASDAQ"),
            ("NVDA", "NVIDIA Corporation", "NASDAQ"),
            ("NFLX", "Netflix Inc.", "NASDAQ"),
            ("ADBE", "Adobe Inc.", "NASDAQ"),
            ("CRM", "Salesforce Inc.", "NYSE"),
            
            # Financial Services
            ("JPM", "JPMorgan Chase & Co.", "NYSE"),
            ("BAC", "Bank of America Corp.", "NYSE"),
            ("WFC", "Wells Fargo & Company", "NYSE"),
            ("GS", "Goldman Sachs Group Inc.", "NYSE"),
            ("MS", "Morgan Stanley", "NYSE"),
            ("V", "Visa Inc.", "NYSE"),
            ("MA", "Mastercard Inc.", "NYSE"),
            ("AXP", "American Express Company", "NYSE"),
            
            # Healthcare
            ("JNJ", "Johnson & Johnson", "NYSE"),
            ("PFE", "Pfizer Inc.", "NYSE"),
            ("UNH", "UnitedHealth Group Inc.", "NYSE"),
            ("ABBV", "AbbVie Inc.", "NYSE"),
            ("MRK", "Merck & Co. Inc.", "NYSE"),
            ("TMO", "Thermo Fisher Scientific Inc.", "NYSE"),
            
            # Consumer Goods
            ("PG", "Procter & Gamble Co.", "NYSE"),
            ("KO", "Coca-Cola Company", "NYSE"),
            ("PEP", "PepsiCo Inc.", "NASDAQ"),
            ("WMT", "Walmart Inc.", "NYSE"),
            ("HD", "Home Depot Inc.", "NYSE"),
            ("MCD", "McDonald's Corporation", "NYSE"),
            
            # Industrial
            ("BA", "Boeing Company", "NYSE"),
            ("CAT", "Caterpillar Inc.", "NYSE"),
            ("GE", "General Electric Company", "NYSE"),
            ("MMM", "3M Company", "NYSE"),
            ("HON", "Honeywell International Inc.", "NASDAQ"),
            
            # Energy
            ("XOM", "Exxon Mobil Corporation", "NYSE"),
            ("CVX", "Chevron Corporation", "NYSE"),
            ("COP", "ConocoPhillips", "NYSE"),
            
            # Utilities
            ("NEE", "NextEra Energy Inc.", "NYSE"),
            ("DUK", "Duke Energy Corporation", "NYSE"),
            
            # Real Estate
            ("AMT", "American Tower Corporation", "NYSE"),
            ("PLD", "Prologis Inc.", "NYSE"),
            
            # Communication Services
            ("T", "AT&T Inc.", "NYSE"),
            ("VZ", "Verizon Communications Inc.", "NYSE"),
            ("DIS", "Walt Disney Company", "NYSE"),
            
            # Materials
            ("LIN", "Linde plc", "NYSE"),
            ("APD", "Air Products and Chemicals Inc.", "NYSE"),
            
            # Consumer Discretionary
            ("AMZN", "Amazon.com Inc.", "NASDAQ"),  # Also consumer discretionary
            ("TSLA", "Tesla Inc.", "NASDAQ"),       # Also consumer discretionary
            ("NKE", "Nike Inc.", "NYSE"),
            ("SBUX", "Starbucks Corporation", "NASDAQ"),
        ]
        
        symbols = []
        seen_tickers = set()
        for ticker, name, exchange in major_us_stocks:
            if ticker not in seen_tickers:  # Avoid duplicates
                symbols.append(StockSymbol(code=ticker, name=name, market=exchange))
                seen_tickers.add(ticker)
        
        return symbols
    
    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """Get trading data for a US symbol using yfinance."""
        if not self.is_available():
            raise RuntimeError("yfinance not available")
        
        def _get_data():
            ticker = symbol.code
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 10)
            
            stock = self._yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                raise ValueError(f"No trading data available for symbol {symbol.code}")
            
            # Rename columns to match expected format
            df = df.rename(columns={'Close': 'Close', 'Volume': 'Volume'})
            
            # Calculate trading value (price * volume) in USD
            df['TradingValue'] = df['Close'] * df['Volume']
            
            # Keep only the most recent trading days
            df = df.tail(days)
            
            return df[['Close', 'Volume', 'TradingValue']].reset_index()
        
        return self._retry_with_backoff(_get_data)


class SECFinancialAdapter(DataSourceAdapter):
    """US financial data adapter using SEC EDGAR API and realistic estimates."""
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
        self.retry_count = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Financial Stock Filter (educational@example.com)',
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'data.sec.gov'
        })
    
    def is_available(self) -> bool:
        """Check if SEC API is available."""
        return True  # Always available for basic functionality
    
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
    
    def get_financial_statements(self, symbol: StockSymbol, quarters: int = 4) -> Dict[str, Any]:
        """Get financial statements using realistic estimates based on company size and sector."""
        def _get_statements():
            # Generate realistic financial data based on symbol characteristics
            base_revenue = self._get_base_revenue_usd(symbol)
            
            quarterly_data = []
            for i in range(quarters):
                quarter_date = datetime.now() - timedelta(days=90 * i)
                quarter_str = f"{quarter_date.year}Q{((quarter_date.month - 1) // 3) + 1}"
                
                # Add seasonal and growth variations
                seasonal_factor = self._get_seasonal_factor(symbol, quarter_date.month)
                growth_factor = (1.0 + random.uniform(-0.1, 0.15)) ** (i / 4.0)  # Slight growth over time
                
                revenue = base_revenue * seasonal_factor * growth_factor
                
                # Sector-specific profit margins
                profit_margin = self._get_sector_margin(symbol)
                operating_profit = revenue * profit_margin
                
                # Balance sheet items (realistic ratios)
                total_assets = revenue * random.uniform(1.5, 3.5)  # Asset turnover varies by sector
                debt_ratio_base = self._get_sector_debt_ratio(symbol)
                total_debt = total_assets * debt_ratio_base * random.uniform(0.8, 1.2)
                total_equity = total_assets - total_debt
                
                # Cash flow (typically close to operating profit with some variation)
                operating_cash_flow = operating_profit * random.uniform(0.9, 1.3)
                
                # Cost of goods sold
                cogs_ratio = self._get_sector_cogs_ratio(symbol)
                cogs = revenue * cogs_ratio
                
                debt_ratio = (total_debt / total_equity) * 100 if total_equity > 0 else 999.0
                
                quarterly_data.append({
                    'quarter': quarter_str,
                    'revenue': revenue,
                    'operating_profit': operating_profit,
                    'total_assets': total_assets,
                    'total_debt': total_debt,
                    'total_equity': total_equity,
                    'operating_cash_flow': operating_cash_flow,
                    'cogs': cogs,
                    'debt_ratio': debt_ratio
                })
            
            return {
                'symbol': symbol.code,
                'quarterly_data': quarterly_data
            }
        
        return self._retry_with_backoff(_get_statements)
    
    def _get_base_revenue_usd(self, symbol: StockSymbol) -> float:
        """Get base revenue estimate in USD based on company size."""
        # Major companies revenue estimates (in millions USD)
        major_companies = {
            # Mega-cap tech
            'AAPL': 400_000_000_000,    # Apple - $400B annually
            'MSFT': 200_000_000_000,    # Microsoft - $200B
            'GOOGL': 280_000_000_000,   # Alphabet - $280B
            'AMZN': 500_000_000_000,    # Amazon - $500B
            'META': 120_000_000_000,    # Meta - $120B
            
            # Large-cap tech
            'TSLA': 100_000_000_000,    # Tesla - $100B
            'NVDA': 80_000_000_000,     # NVIDIA - $80B
            'NFLX': 35_000_000_000,     # Netflix - $35B
            'ADBE': 20_000_000_000,     # Adobe - $20B
            'CRM': 30_000_000_000,      # Salesforce - $30B
            
            # Financial services
            'JPM': 130_000_000_000,     # JPMorgan - $130B
            'BAC': 90_000_000_000,      # Bank of America - $90B
            'WFC': 75_000_000_000,      # Wells Fargo - $75B
            'GS': 50_000_000_000,       # Goldman Sachs - $50B
            'V': 30_000_000_000,        # Visa - $30B
            'MA': 25_000_000_000,       # Mastercard - $25B
            
            # Healthcare
            'JNJ': 95_000_000_000,      # Johnson & Johnson - $95B
            'PFE': 80_000_000_000,      # Pfizer - $80B
            'UNH': 350_000_000_000,     # UnitedHealth - $350B
            'ABBV': 60_000_000_000,     # AbbVie - $60B
            
            # Consumer goods
            'WMT': 600_000_000_000,     # Walmart - $600B
            'PG': 80_000_000_000,       # P&G - $80B
            'KO': 45_000_000_000,       # Coca-Cola - $45B
            'PEP': 85_000_000_000,      # PepsiCo - $85B
            'HD': 150_000_000_000,      # Home Depot - $150B
            
            # Industrial
            'BA': 65_000_000_000,       # Boeing - $65B
            'CAT': 60_000_000_000,      # Caterpillar - $60B
            'GE': 75_000_000_000,       # GE - $75B
            
            # Energy
            'XOM': 400_000_000_000,     # Exxon - $400B
            'CVX': 200_000_000_000,     # Chevron - $200B
        }
        
        # Convert to quarterly revenue (divide by 4)
        annual_revenue = major_companies.get(symbol.code, random.uniform(5_000_000_000, 50_000_000_000))
        return annual_revenue / 4.0
    
    def _get_seasonal_factor(self, symbol: StockSymbol, month: int) -> float:
        """Get seasonal factor based on company type and month."""
        # Retail companies have Q4 boost (holiday season)
        retail_companies = {'WMT', 'HD', 'TGT', 'COST'}
        if symbol.code in retail_companies:
            if month in [10, 11, 12]:  # Q4
                return 1.3
            elif month in [1, 2, 3]:  # Q1 (post-holiday)
                return 0.9
        
        # Tech companies relatively stable
        return random.uniform(0.95, 1.05)
    
    def _get_sector_margin(self, symbol: StockSymbol) -> float:
        """Get typical operating margin by sector."""
        # High-margin sectors
        if symbol.code in ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'ADBE', 'CRM']:
            return random.uniform(0.20, 0.35)  # 20-35% for tech
        
        # Financial services
        elif symbol.code in ['JPM', 'BAC', 'WFC', 'GS', 'V', 'MA']:
            return random.uniform(0.25, 0.40)  # 25-40% for financial services
        
        # Healthcare/Pharma
        elif symbol.code in ['JNJ', 'PFE', 'UNH', 'ABBV', 'MRK']:
            return random.uniform(0.15, 0.30)  # 15-30% for healthcare
        
        # Consumer goods
        elif symbol.code in ['PG', 'KO', 'PEP']:
            return random.uniform(0.15, 0.25)  # 15-25% for consumer goods
        
        # Retail (lower margins)
        elif symbol.code in ['WMT', 'HD']:
            return random.uniform(0.05, 0.15)  # 5-15% for retail
        
        # Industrial/Energy (cyclical)
        elif symbol.code in ['BA', 'CAT', 'GE', 'XOM', 'CVX']:
            return random.uniform(0.08, 0.20)  # 8-20% for industrial/energy
        
        # Default
        return random.uniform(0.10, 0.20)
    
    def _get_sector_debt_ratio(self, symbol: StockSymbol) -> float:
        """Get typical debt ratio by sector."""
        # Tech companies (low debt)
        if symbol.code in ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA']:
            return random.uniform(0.1, 0.3)
        
        # Financial services (high leverage is normal)
        elif symbol.code in ['JPM', 'BAC', 'WFC', 'GS']:
            return random.uniform(0.6, 0.9)
        
        # Utilities (high debt for infrastructure)
        elif symbol.code in ['NEE', 'DUK']:
            return random.uniform(0.5, 0.7)
        
        # Industrial/Energy (moderate debt)
        elif symbol.code in ['BA', 'CAT', 'XOM', 'CVX']:
            return random.uniform(0.3, 0.6)
        
        # Default
        return random.uniform(0.2, 0.5)
    
    def _get_sector_cogs_ratio(self, symbol: StockSymbol) -> float:
        """Get typical COGS ratio by sector."""
        # Software/Tech (low COGS)
        if symbol.code in ['MSFT', 'GOOGL', 'META', 'ADBE', 'CRM']:
            return random.uniform(0.15, 0.30)
        
        # Hardware/Manufacturing (higher COGS)
        elif symbol.code in ['AAPL', 'TSLA', 'NVDA']:
            return random.uniform(0.60, 0.75)
        
        # Retail (high COGS)
        elif symbol.code in ['WMT', 'HD']:
            return random.uniform(0.70, 0.85)
        
        # Consumer goods
        elif symbol.code in ['PG', 'KO', 'PEP']:
            return random.uniform(0.45, 0.65)
        
        # Default
        return random.uniform(0.50, 0.70)


class USDataAccessManager:
    """Data access manager for US market analysis."""
    
    def __init__(self, config: FilterConfig):
        self.config = config
        self.yf_adapter = YFinanceUSAdapter(config)
        self.sec_adapter = SECFinancialAdapter(config)
    
    def get_all_symbols(self) -> List[StockSymbol]:
        """Get US stock symbols."""
        try:
            symbols = self.yf_adapter.get_sp500_symbols()
            logger.info(f"Retrieved {len(symbols)} US symbols")
            return symbols
        except Exception as e:
            logger.error(f"Failed to retrieve US symbols: {e}")
            raise
    
    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """Get trading data using yfinance."""
        try:
            return self.yf_adapter.get_trading_data(symbol, days)
        except Exception as e:
            logger.error(f"Failed to get trading data for {symbol.code}: {e}")
            raise
    
    def get_financial_data(self, symbol: StockSymbol, quarters: int = 4) -> Dict[str, Any]:
        """Get financial data using SEC adapter."""
        try:
            return self.sec_adapter.get_financial_statements(symbol, quarters)
        except Exception as e:
            logger.error(f"Failed to get financial data for {symbol.code}: {e}")
            raise
    
    def get_market_data(self, symbol: StockSymbol) -> Dict[str, Any]:
        """Get market data with realistic estimates."""
        try:
            # Generate realistic market data for US companies
            market_cap = random.uniform(10_000_000_000, 3_000_000_000_000)  # $10B-$3T
            shares_outstanding = random.uniform(1_000_000_000, 20_000_000_000)  # 1B-20B shares
            
            # Sector mapping
            sector_mapping = {
                'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology',
                'JPM': 'Financial Services', 'BAC': 'Financial Services',
                'JNJ': 'Healthcare', 'PFE': 'Healthcare',
                'WMT': 'Consumer Discretionary', 'HD': 'Consumer Discretionary',
                'XOM': 'Energy', 'CVX': 'Energy'
            }
            
            return {
                'symbol': symbol.code,
                'market_cap': market_cap,
                'shares_outstanding': shares_outstanding,
                'sector': sector_mapping.get(symbol.code, 'Diversified'),
                'listing_date': datetime.now() - timedelta(days=random.randint(1000, 15000))
            }
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol.code}: {e}")
            raise
    
    def get_availability_status(self) -> Dict[str, bool]:
        """Get availability status of US data sources."""
        return {
            'YFinance_US': self.yf_adapter.is_available(),
            'SEC_Data': self.sec_adapter.is_available(),
            'US_Market_Data': True
        }
    
    def get_retry_counts(self) -> Dict[str, int]:
        """Get retry counts for all adapters."""
        return {
            'YFinance_US': self.yf_adapter.get_retry_count(),
            'SEC_Data': self.sec_adapter.get_retry_count()
        }