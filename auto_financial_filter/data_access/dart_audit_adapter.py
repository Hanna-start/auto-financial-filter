"""
Adapter for executing the local dart-audit-extractor and parsing its timeseries excel.
This enables analysis of unlisted companies based on 1-year interval data.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from ..models.base import StockSymbol, DataSourceAdapter
from ..config import FilterConfig


logger = logging.getLogger(__name__)

class DartAuditExtractorAdapter(DataSourceAdapter):
    """
    Adapter that executes the local DART Audit Extractor (dart-audit-extractor)
    to parse financial data directly from DART PDFs for unlisted companies.
    """
    
    def __init__(self, config: FilterConfig, extractor_path: str = "D:/Agent_Project/dart-audit-extractor", api_key: Optional[str] = None):
        super().__init__(config)
        self.extractor_path = Path(extractor_path)
        self.api_key = api_key or os.environ.get("DART_API_KEY")
        self.retry_count = 0
        
    def is_available(self) -> bool:
        """Check if dart-audit-extractor is available at the specified path."""
        return (self.extractor_path / "extractor.py").exists()

    def get_retry_count(self) -> int:
        """Get the number of retry attempts for this adapter."""
        return self.retry_count

    def get_financial_statements(self, symbol: StockSymbol, quarters: int = 4) -> Dict[str, Any]:
        """
        Executes dart-audit-extractor for the given symbol (company name),
        reads the resulting timeseries excel, and maps it to the expected structure.
        Note: The data is yearly, not quarterly, but we return it in the expected list format.
        (1 year data corresponds to 1 'quarter' data block in the filter system)
        """
        if not self.is_available():
            raise RuntimeError(f"dart-audit-extractor not found at {self.extractor_path}")
            
        # 1. Run the extractor subprocess
        env = os.environ.copy()
        if self.api_key:
            env["DART_API_KEY"] = self.api_key
            
        company_name = symbol.name # For unlisted, code might be empty, name is important
        
        logger.info(f"Running dart-audit-extractor for {company_name} (this might take a minute)...")
        
        try:
            # We use sys.executable to ensure the same Python environment
            result = subprocess.run(
                [sys.executable, "extractor.py", company_name],
                cwd=str(self.extractor_path),
                env=env,
                capture_output=True,
                text=True,
                encoding='utf-8' # Handle Windows encoding
            )
            
            if result.returncode != 0:
                logger.error(f"Extractor failed for {company_name}:\n{result.stderr}")
                raise RuntimeError(f"Failed to extract DART data for {company_name}")
                
            logger.debug(f"Extractor output: {result.stdout}")
        except Exception as e:
            raise RuntimeError(f"Error executing dart-audit-extractor: {e}")
            
        # 2. Find and read the output excel file
        data_dir = self.extractor_path / "data" / company_name
        excel_path = data_dir / f"{company_name}_시계열.xlsx"
        
        if not excel_path.exists():
            raise FileNotFoundError(f"Extracted excel not found at {excel_path}. Maybe no data available for this company?")
            
        try:
            df = pd.read_excel(excel_path, sheet_name="long_data")
        except Exception as e:
            raise RuntimeError(f"Failed to read extracted excel file: {e}")
            
        # 3. Transform the data
        # long_data columns: 회사명, 사업연도, 구분, 재무제표, 계정, 값
        divs = df['구분'].unique()
        preferred_div = "연결" if "연결" in divs else "별도"
        
        df_filtered = df[df['구분'] == preferred_div]
        if df_filtered.empty and len(divs) > 0:
            preferred_div = divs[0]
            df_filtered = df[df['구분'] == preferred_div]
            
        # Pivot table: Index(사업연도) -> Columns(계정) -> Values(값)
        pivot_df = df_filtered.pivot_table(index='사업연도', columns='계정', values='값', aggfunc='last').reset_index()
        pivot_df = pivot_df.sort_values('사업연도')
        
        # 4. Map to expected dictionary format
        mapped_data = []
        for _, row in pivot_df.iterrows():
            def safe_get(col_name, default=0.0):
                if col_name in pivot_df.columns and pd.notna(row[col_name]):
                    return float(row[col_name])
                return default
                
            revenue = safe_get('매출액')
            if revenue == 0.0:  # Fallback to 영업수익 if 매출액 is missing
                revenue = safe_get('영업수익')
                
            op_profit = safe_get('영업이익')
            assets = safe_get('자산총계')
            debt = safe_get('부채총계')
            equity = safe_get('자본총계')
            cash_flow = safe_get('영업활동현금흐름')
            cogs = safe_get('매출원가')
            
            if equity > 0:
                debt_ratio = (debt / equity) * 100
            else:
                debt_ratio = 999.0
                
            year_str = str(int(row['사업연도']))
            
            mapped_data.append({
                'quarter': year_str,  # Represents Year
                'revenue': revenue,
                'operating_profit': op_profit,
                'total_assets': assets,
                'total_debt': debt,
                'total_equity': equity,
                'operating_cash_flow': cash_flow,
                'cogs': cogs,
                'debt_ratio': debt_ratio
            })
            
        # The filter system assumes 'quarters' periods.
        # But for QualityGrowthFilter, it looks at 6 periods for COGS trend.
        # FinancialHealthFilter looks at `cash_flow_quarters` (default 4).
        # We will return the most recent `quarters` years (or all if we want).
        # To satisfy both filters, `quarters` should ideally be 6 when calling this.
        
        mapped_data = sorted(mapped_data, key=lambda x: x['quarter'], reverse=True)
        recent_data = mapped_data[:quarters]
        recent_data = list(reversed(recent_data)) # chronological order
        
        return {
            'symbol': symbol.code,
            'quarterly_data': recent_data
        }
        
    def get_trading_data(self, symbol: StockSymbol, days: int) -> pd.DataFrame:
        """
        Unlisted companies do not have trading data. 
        We return an empty dataframe to safely fail the liquidity filter 
        if it's not explicitly bypassed.
        """
        return pd.DataFrame(columns=['Close', 'Volume', 'TradingValue'])
