import os
import sys
from pathlib import Path

project_root = Path(os.getcwd())
sys.path.insert(0, str(project_root))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.data_access.alternative_adapters import AlternativeDataAccessManager

config = FilterConfig()
manager = AlternativeDataAccessManager(config)
symbol = StockSymbol("005930", "Samsung Electronics", "KOSPI")

print("Checking Alternative Adapter Data for Samsung...")
try:
    # Need to check the method it has. Let's look at dir(manager)
    print("Methods available:", [m for m in dir(manager) if not m.startswith('_')])
    
    # Check if there is get_financial_statements
    if hasattr(manager, 'get_financial_statements'):
        data = manager.get_financial_statements(symbol, quarters=4)
        print("Data:", data)
    elif hasattr(manager, '_yfinance_adapter') and hasattr(manager._yfinance_adapter, 'get_financial_statements'):
        data = manager._yfinance_adapter.get_financial_statements(symbol, quarters=4)
        print("Yfinance Data:", data)
except Exception as e:
    print(f"Error: {e}")
