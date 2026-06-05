import os
import sys
from pathlib import Path

project_root = Path(os.getcwd())
sys.path.insert(0, str(project_root))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.data_access.alternative_adapters import AlternativeDataAccessManager
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter

config = FilterConfig(min_revenue_growth_percent=5.0)
manager = AlternativeDataAccessManager(config)
filter_stage2 = FinancialHealthFilter(config, manager)

symbol = StockSymbol("005930", "Samsung Electronics", "KOSPI")

print("Filtering Samsung...")
try:
    metrics = manager.get_financial_metrics(symbol)
    print(f"Revenue: {metrics.revenue}")
    print(f"Op Profit: {metrics.operating_profit}")
    print(f"OCF: {metrics.operating_cash_flow}")
    print(f"Debt Ratio: {metrics.debt_ratio}")
    
    # Simulate filter logic
    if not all(metrics.revenue):
        print("Missing revenue data")
    else:
        current_rev = metrics.revenue[-1]
        prev_rev = metrics.revenue[-2]
        growth = ((current_rev - prev_rev) / prev_rev) * 100 if prev_rev > 0 else 0
        print(f"Revenue Growth: {growth:.2f}%")
    
    passed, reason = filter_stage2.process(symbol)
    print(f"Result: {passed}, Reason: {reason}")
    
except Exception as e:
    print(f"Error: {e}")
