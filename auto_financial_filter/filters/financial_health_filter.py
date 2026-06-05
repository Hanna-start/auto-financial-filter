"""
Financial health filtering module for debt ratio and cash flow analysis.

This module implements the second stage of the stock filtering pipeline,
focusing on financial health metrics including debt ratio, cash flow health,
and revenue growth analysis.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..models.base import StockSymbol, FilterResult, BaseFilter, FinancialMetrics
from ..config import FilterConfig
from ..data_access.adapters import DataAccessManager


class FinancialHealthFilter(BaseFilter):
    """
    Financial health filter for analyzing debt ratio, cash flow, and revenue growth.
    
    This filter implements the second stage of the filtering pipeline, applying
    financial health criteria to stocks that passed the liquidity filter.
    """
    
    def __init__(self, config: FilterConfig, data_manager: DataAccessManager):
        super().__init__(config)
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)
        
        # Configuration parameters
        self.max_debt_ratio = config.max_debt_ratio_percent
        self.min_revenue_growth = config.min_revenue_growth_percent
        self.cash_flow_quarters = config.cash_flow_quarters
        
        self.logger.info(f"FinancialHealthFilter initialized with:")
        self.logger.info(f"  Max debt ratio: {self.max_debt_ratio}%")
        self.logger.info(f"  Min revenue growth: {self.min_revenue_growth}%")
        self.logger.info(f"  Cash flow quarters: {self.cash_flow_quarters}")
    
    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        """
        Apply financial health filtering to the provided stock symbols.
        
        Args:
            symbols: List of stock symbols to filter
            
        Returns:
            FilterResult containing passed and failed symbols with criteria applied
        """
        self.logger.info(f"Starting financial health filtering for {len(symbols)} symbols")
        
        passed_symbols = []
        failed_symbols = []
        
        for i, symbol in enumerate(symbols):
            if i % 50 == 0:
                self.logger.info(f"Processing symbol {i+1}/{len(symbols)}: {symbol.code}")
            
            try:
                # Get financial metrics for the symbol
                financial_metrics = self._get_financial_metrics(symbol)
                
                if financial_metrics is None:
                    self.logger.warning(f"No financial data available for {symbol.code}")
                    failed_symbols.append(symbol)
                    continue
                
                # Apply financial health criteria
                if self._passes_financial_health_criteria(financial_metrics):
                    passed_symbols.append(symbol)
                    self.logger.debug(f"Symbol {symbol.code} passed financial health criteria")
                else:
                    failed_symbols.append(symbol)
                    self.logger.debug(f"Symbol {symbol.code} failed financial health criteria")
                    
            except Exception as e:
                self.logger.error(f"Error processing {symbol.code}: {str(e)}")
                failed_symbols.append(symbol)
        
        criteria_applied = {
            "max_debt_ratio_percent": self.max_debt_ratio,
            "min_revenue_growth_percent": self.min_revenue_growth,
            "cash_flow_quarters_required": self.cash_flow_quarters
        }
        
        self.logger.info(f"Financial health filtering complete: {len(passed_symbols)} passed, {len(failed_symbols)} failed")
        
        return FilterResult(
            passed_symbols=passed_symbols,
            failed_symbols=failed_symbols,
            stage="Financial Health Filter",
            criteria_applied=criteria_applied
        )
    
    def _get_financial_metrics(self, symbol: StockSymbol) -> Optional[FinancialMetrics]:
        """
        Retrieve financial metrics for a stock symbol.
        
        Args:
            symbol: Stock symbol to get metrics for
            
        Returns:
            FinancialMetrics object or None if data unavailable
        """
        try:
            # Get quarterly financial data
            financial_data = self.data_manager.get_financial_data(symbol, quarters=8)
            quarterly_data = financial_data.get('quarterly_data', [])
            
            if not quarterly_data or len(quarterly_data) < 8:  # Need at least 8 quarters for YoY comparison
                return None
            
            # Calculate debt ratio (most recent quarter)
            latest_quarter = quarterly_data[0]
            debt_ratio = self._calculate_debt_ratio(latest_quarter)
            
            # Get operating cash flow for recent 4 quarters
            operating_cash_flow = [q.get('operating_cash_flow', 0) for q in quarterly_data[:4]]
            
            # Calculate revenue growth YoY
            revenue_growth_yoy = self._calculate_revenue_growth_yoy(quarterly_data)
            
            # Get quarterly revenue for recent 4 quarters
            quarterly_revenue = [q.get('revenue', 0) for q in quarterly_data[:4]]
            
            return FinancialMetrics(
                symbol=symbol,
                debt_ratio=debt_ratio,
                operating_cash_flow=operating_cash_flow,
                revenue_growth_yoy=revenue_growth_yoy,
                quarterly_revenue=quarterly_revenue
            )
            
        except Exception as e:
            self.logger.error(f"Error retrieving financial metrics for {symbol.code}: {str(e)}")
            return None
    
    def _calculate_debt_ratio(self, quarter_data: Dict[str, Any]) -> float:
        """
        Calculate debt ratio from quarterly financial data.
        
        Args:
            quarter_data: Dictionary containing quarterly financial data
            
        Returns:
            Debt ratio as percentage
        """
        total_debt = quarter_data.get('total_debt', 0)
        total_equity = quarter_data.get('total_equity', 0)
        
        if total_equity <= 0:
            return float('inf')  # Infinite debt ratio if no equity
        
        return (total_debt / total_equity) * 100
    
    def _calculate_revenue_growth_yoy(self, quarterly_data: List[Dict[str, Any]]) -> float:
        """
        Calculate year-over-year revenue growth based on 4 quarters cumulative.
        
        Args:
            quarterly_data: List of quarterly financial data (most recent first)
            
        Returns:
            Revenue growth percentage (YoY)
        """
        if len(quarterly_data) < 8:
            return 0.0
        
        # Recent 4 quarters cumulative revenue
        recent_4q_revenue = sum(q.get('revenue', 0) for q in quarterly_data[:4])
        
        # Previous year same 4 quarters cumulative revenue
        previous_4q_revenue = sum(q.get('revenue', 0) for q in quarterly_data[4:8])
        
        if previous_4q_revenue <= 0:
            return 0.0
        
        return ((recent_4q_revenue - previous_4q_revenue) / previous_4q_revenue) * 100
    
    def _passes_financial_health_criteria(self, metrics: FinancialMetrics) -> bool:
        """
        Check if financial metrics meet all health criteria.
        
        Args:
            metrics: FinancialMetrics object to evaluate
            
        Returns:
            True if all criteria are met, False otherwise
        """
        # Criterion 1: Debt ratio must be less than maximum threshold
        if metrics.debt_ratio >= self.max_debt_ratio:
            self.logger.debug(f"Failed debt ratio check: {metrics.debt_ratio:.1f}% >= {self.max_debt_ratio}%")
            return False
        
        # Criterion 2: Cash flow health validation
        if not self._validate_cash_flow_health(metrics.operating_cash_flow):
            self.logger.debug("Failed cash flow health check")
            return False
        
        # Criterion 3: Revenue growth must meet minimum threshold
        if metrics.revenue_growth_yoy < self.min_revenue_growth:
            self.logger.debug(f"Failed revenue growth check: {metrics.revenue_growth_yoy:.1f}% < {self.min_revenue_growth}%")
            return False
        
        return True
    
    def _validate_cash_flow_health(self, operating_cash_flow: List[float]) -> bool:
        """
        Validate cash flow health based on quarterly operating cash flow data.
        
        Cash flow is considered healthy if either:
        1. All recent 4 quarters show positive OCF, OR
        2. Cumulative OCF over 4 quarters meets sufficient levels (positive)
        
        Args:
            operating_cash_flow: List of 4 quarterly operating cash flow values
            
        Returns:
            True if cash flow health criteria are met, False otherwise
        """
        if len(operating_cash_flow) != 4:
            return False
        
        # Check if all 4 quarters are positive
        all_positive = all(ocf > 0 for ocf in operating_cash_flow)
        
        # Check if cumulative cash flow is sufficient (positive)
        cumulative_ocf = sum(operating_cash_flow)
        cumulative_sufficient = cumulative_ocf > 0
        
        # Pass if either condition is met
        return all_positive or cumulative_sufficient
    
    def get_stage_name(self) -> str:
        """Get the name of this filtering stage."""
        return "Financial Health Filter"
    
    def get_filter_name(self) -> str:
        """Get the name of this filter."""
        return "Financial Health Filter"
    
    def get_criteria_description(self) -> Dict[str, str]:
        """Get human-readable description of filter criteria."""
        return {
            "max_debt_ratio": f"Debt ratio < {self.max_debt_ratio}%",
            "cash_flow_health": f"Positive cash flow over {self.cash_flow_quarters} quarters",
            "min_revenue_growth": f"Revenue growth ≥ {self.min_revenue_growth}% YoY"
        }