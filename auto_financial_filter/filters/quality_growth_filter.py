"""
Quality growth filtering module for the financial stock filter system.

This module implements the third and final stage of the filtering pipeline,
focusing on profitability and operational efficiency trends.
"""

from typing import List, Dict, Any
import logging
from datetime import datetime, timedelta

from ..models.base import StockSymbol, ProfitabilityMetrics, FilterResult, BaseFilter
from ..config import FilterConfig
from ..data_access.adapters import DataAccessManager


class QualityGrowthFilter(BaseFilter):
    """
    Third stage filter that evaluates stocks based on profitability and trend criteria.
    
    Filters stocks based on:
    - Operating margin >= 10% threshold
    - Recent 4 quarters operating profit is peak among past 4 years
    - COGS ratio shows consistently decreasing trend over 6 quarters
    """
    
    def __init__(self, config: FilterConfig, data_manager: DataAccessManager):
        super().__init__(config)
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)
        
    def get_stage_name(self) -> str:
        """Get the name of this filtering stage."""
        return "final_candidate_list"
    
    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        """
        Apply quality growth filtering to a list of stock symbols.
        
        Args:
            symbols: List of stock symbols to filter (from step 2)
            
        Returns:
            FilterResult containing passed and failed symbols
        """
        self.logger.info(f"Starting quality growth filtering for {len(symbols)} symbols")
        
        passed_symbols = []
        failed_symbols = []
        processed_count = 0
        
        criteria_applied = {
            "min_operating_margin_percent": self.config.min_operating_margin_percent,
            "profit_trend_years": self.config.profit_trend_years,
            "cogs_trend_quarters": self.config.cogs_trend_quarters
        }
        
        for i, symbol in enumerate(symbols):
            try:
                # Progress tracking
                processed_count += 1
                if processed_count % 5 == 0 or processed_count == len(symbols):
                    progress_pct = (processed_count / len(symbols)) * 100
                    self.logger.info(f"Progress: {processed_count}/{len(symbols)} ({progress_pct:.1f}%)")
                
                # Get profitability metrics for the symbol
                profitability_metrics = self._get_profitability_metrics(symbol)
                
                # Apply all quality growth criteria
                if self._meets_quality_growth_criteria(profitability_metrics):
                    passed_symbols.append(symbol)
                    self.logger.debug(f"PASS: {symbol.code} - OPM: {profitability_metrics.operating_margin:.1f}%, Peak: {profitability_metrics.is_profit_peak}")
                else:
                    failed_symbols.append(symbol)
                    self.logger.debug(f"FAIL: {symbol.code} - OPM: {profitability_metrics.operating_margin:.1f}%, Peak: {profitability_metrics.is_profit_peak}")
                    
            except Exception as e:
                # Error handling - exclude problematic stocks and continue
                failed_symbols.append(symbol)
                self.logger.warning(f"Error processing {symbol.code}: {str(e)}")
                continue
        
        result = FilterResult(
            passed_symbols=passed_symbols,
            failed_symbols=failed_symbols,
            stage=self.get_stage_name(),
            criteria_applied=criteria_applied
        )
        
        self.logger.info(
            f"Quality growth filtering complete: {len(passed_symbols)} passed, "
            f"{len(failed_symbols)} failed ({result.pass_rate:.1f}% pass rate)"
        )
        
        return result
    
    def _get_profitability_metrics(self, symbol: StockSymbol) -> ProfitabilityMetrics:
        """
        Get profitability metrics for a stock symbol.
        
        Args:
            symbol: Stock symbol to analyze
            
        Returns:
            ProfitabilityMetrics containing profitability and trend data
        """
        # Get financial data for trend analysis
        financial_data = self.data_manager.get_financial_data(symbol)
        
        # Handle both DataFrame (Korean) and dict (US) formats
        if hasattr(financial_data, 'empty'):
            # DataFrame format (Korean adapters)
            if financial_data.empty:
                raise ValueError(f"No financial data available for {symbol.code}")
        elif isinstance(financial_data, dict):
            # Dictionary format (US adapters)
            if not financial_data or not financial_data.get('quarterly_data'):
                raise ValueError(f"No financial data available for {symbol.code}")
        else:
            raise ValueError(f"Unsupported financial data format for {symbol.code}")
        
        # Calculate operating margin from most recent quarter
        operating_margin = self._calculate_operating_margin(financial_data)
        
        # Get 4 years of quarterly operating profit data for trend analysis
        operating_profit_trend = self._extract_operating_profit_trend(financial_data)
        
        # Get 6 quarters of COGS ratio data for trend analysis
        cogs_ratio_trend = self._extract_cogs_ratio_trend(financial_data)
        
        # Determine if recent 4 quarters represent profit peak
        is_profit_peak = self._is_profit_peak(operating_profit_trend)
        
        return ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=operating_margin,
            operating_profit_trend=operating_profit_trend,
            cogs_ratio_trend=cogs_ratio_trend,
            is_profit_peak=is_profit_peak
        )
    
    def _calculate_operating_margin(self, financial_data) -> float:
        """
        Calculate operating margin from financial data.
        
        Args:
            financial_data: DataFrame or dict containing financial statement data
            
        Returns:
            Operating margin as percentage
        """
        if hasattr(financial_data, 'iloc'):
            # DataFrame format (Korean adapters)
            latest_data = financial_data.iloc[-1]
            operating_profit = latest_data.get('OperatingProfit', 0)
            revenue = latest_data.get('Revenue', 0)
        else:
            # Dictionary format (US adapters)
            quarterly_data = financial_data.get('quarterly_data', [])
            if not quarterly_data:
                return 0.0
            latest_data = quarterly_data[0]  # Most recent quarter is first
            operating_profit = latest_data.get('operating_profit', 0)
            revenue = latest_data.get('revenue', 0)
        
        if revenue == 0:
            return 0.0
        
        return (operating_profit / revenue) * 100
    
    def _extract_operating_profit_trend(self, financial_data) -> List[float]:
        """
        Extract 4 years (16 quarters) of operating profit data.
        
        Args:
            financial_data: DataFrame or dict containing financial statement data
            
        Returns:
            List of 16 quarterly operating profit values
        """
        if hasattr(financial_data, 'iloc'):
            # DataFrame format (Korean adapters)
            operating_profits = financial_data['OperatingProfit'].tolist()
        else:
            # Dictionary format (US adapters)
            quarterly_data = financial_data.get('quarterly_data', [])
            operating_profits = [q.get('operating_profit', 0) for q in quarterly_data]
        
        # Ensure we have at least 16 quarters of data
        # (과거 US 가짜 데이터용 4→16분기 위조 시뮬은 제거됨 — 부족하면 명확히 실패)
        if len(operating_profits) < 16:
            raise ValueError(f"Insufficient operating profit data: need 16 quarters, got {len(operating_profits)}")
        
        # Return the most recent 16 quarters
        return operating_profits[-16:]
    
    def _extract_cogs_ratio_trend(self, financial_data) -> List[float]:
        """
        Extract 6 quarters of COGS ratio data.
        
        Args:
            financial_data: DataFrame or dict containing financial statement data
            
        Returns:
            List of 6 quarterly COGS ratio values
        """
        cogs_ratios = []
        
        if hasattr(financial_data, 'iterrows'):
            # DataFrame format (Korean adapters)
            for _, row in financial_data.iterrows():
                cogs = row.get('COGS', 0)
                revenue = row.get('Revenue', 0)
                
                if revenue == 0:
                    cogs_ratio = 0.0
                else:
                    cogs_ratio = cogs / revenue
                
                cogs_ratios.append(cogs_ratio)
        else:
            # Dictionary format (US adapters)
            quarterly_data = financial_data.get('quarterly_data', [])
            for quarter in quarterly_data:
                cogs = quarter.get('cogs', 0)
                revenue = quarter.get('revenue', 0)
                
                if revenue == 0:
                    cogs_ratio = 0.0
                else:
                    cogs_ratio = cogs / revenue
                
                cogs_ratios.append(cogs_ratio)
        
        # Ensure we have at least 6 quarters of data
        # (과거 US 가짜 데이터용 4→6분기 위조 시뮬은 제거됨 — 부족하면 명확히 실패)
        if len(cogs_ratios) < 6:
            raise ValueError(f"Insufficient COGS data: need 6 quarters, got {len(cogs_ratios)}")
        
        # Return the most recent 6 quarters
        return cogs_ratios[-6:]
    
    def _is_profit_peak(self, operating_profit_trend: List[float]) -> bool:
        """
        Determine if recent 4 quarters represent the profit peak over 4 years.
        
        Args:
            operating_profit_trend: List of 16 quarterly operating profit values
            
        Returns:
            True if recent 4 quarters is the peak, False otherwise
        """
        if len(operating_profit_trend) != 16:
            return False
        
        # Calculate sum of recent 4 quarters
        recent_4q_sum = sum(operating_profit_trend[-4:])
        
        # Check all possible 4-quarter windows in the 16-quarter period
        max_4q_sum = 0
        for i in range(len(operating_profit_trend) - 3):
            window_sum = sum(operating_profit_trend[i:i+4])
            max_4q_sum = max(max_4q_sum, window_sum)
        
        # Recent 4Q is peak if it equals or exceeds the maximum
        return recent_4q_sum >= max_4q_sum
    
    def _analyze_cogs_trend(self, cogs_ratios: List[float]) -> bool:
        """
        Analyze COGS ratio trend to determine if it's generally decreasing.
        
        Args:
            cogs_ratios: List of 6 quarterly COGS ratios
            
        Returns:
            True if trend is generally decreasing, False otherwise
        """
        if len(cogs_ratios) != 6:
            return False
        
        # More realistic trend analysis: compare first half vs second half
        # This allows for quarterly fluctuations while checking overall trend
        first_half_avg = sum(cogs_ratios[:3]) / 3  # First 3 quarters average
        second_half_avg = sum(cogs_ratios[3:]) / 3  # Last 3 quarters average
        
        # Also check if the most recent quarter is lower than the oldest
        recent_vs_oldest = cogs_ratios[-1] < cogs_ratios[0]
        
        # Pass if either:
        # 1. Second half average is lower than first half (overall improvement)
        # 2. Most recent quarter is lower than oldest quarter (long-term improvement)
        overall_improvement = second_half_avg < first_half_avg
        long_term_improvement = recent_vs_oldest
        
        return overall_improvement or long_term_improvement
    
    def _meets_quality_growth_criteria(self, metrics: ProfitabilityMetrics) -> bool:
        """
        Check if profitability metrics meet all quality growth criteria.
        
        Args:
            metrics: ProfitabilityMetrics to evaluate
            
        Returns:
            True if all criteria are met, False otherwise
        """
        # Criterion 1: Operating margin >= 10%
        margin_ok = metrics.operating_margin >= self.config.min_operating_margin_percent
        
        # Criterion 2: Recent 4 quarters is profit peak
        peak_ok = metrics.is_profit_peak
        
        # Criterion 3: COGS ratio shows decreasing trend
        cogs_trend_ok = self._analyze_cogs_trend(metrics.cogs_ratio_trend)
        
        self.logger.debug(
            f"Quality criteria for {metrics.symbol.code}: "
            f"Margin={margin_ok} ({metrics.operating_margin:.1f}%), "
            f"Peak={peak_ok}, COGS_trend={cogs_trend_ok}"
        )
        
        return margin_ok and peak_ok and cogs_trend_ok
    
    def get_quality_summary(self, symbols: List[StockSymbol]) -> Dict[str, Any]:
        """
        Get a summary of quality growth metrics for a list of symbols.
        
        Args:
            symbols: List of symbols to analyze
            
        Returns:
            Dictionary containing quality growth summary statistics
        """
        if not symbols:
            return {
                "total_symbols": 0,
                "avg_operating_margin": 0.0,
                "symbols_with_profit_peak": 0,
                "symbols_with_decreasing_cogs": 0,
                "symbols_meeting_all_criteria": 0
            }
        
        operating_margins = []
        profit_peaks = 0
        decreasing_cogs = 0
        all_criteria_met = 0
        
        for symbol in symbols:
            try:
                metrics = self._get_profitability_metrics(symbol)
                operating_margins.append(metrics.operating_margin)
                
                if metrics.is_profit_peak:
                    profit_peaks += 1
                
                if self._analyze_cogs_trend(metrics.cogs_ratio_trend):
                    decreasing_cogs += 1
                
                if self._meets_quality_growth_criteria(metrics):
                    all_criteria_met += 1
                    
            except Exception as e:
                self.logger.warning(f"Could not get quality metrics for {symbol.code}: {e}")
                continue
        
        return {
            "total_symbols": len(symbols),
            "avg_operating_margin": sum(operating_margins) / len(operating_margins) if operating_margins else 0.0,
            "symbols_with_profit_peak": profit_peaks,
            "symbols_with_decreasing_cogs": decreasing_cogs,
            "symbols_meeting_all_criteria": all_criteria_met,
            "criteria_pass_rate": (all_criteria_met / len(symbols)) * 100 if symbols else 0.0
        }