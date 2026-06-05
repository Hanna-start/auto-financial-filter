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
    data = manager.get_financial_data(symbol)
    print(data)
except Exception as e:
    print(f"Error: {e}")
