"""
Liquidity filtering module for the financial stock filter system.

This module implements the first stage of the filtering pipeline,
focusing on trading volume and liquidity criteria.
"""

from typing import List, Dict, Any
import logging
from datetime import datetime, timedelta

from ..models.base import StockSymbol, LiquidityMetrics, FilterResult, BaseFilter
from ..config import FilterConfig
from ..data_access.adapters import DataAccessManager


class LiquidityFilter(BaseFilter):
    """
    First stage filter that evaluates stocks based on liquidity criteria.
    
    Filters stocks based on:
    - 30-day average trading volume
    - Minimum trading value threshold (default: 10 billion KRW)
    """
    
    def __init__(self, config: FilterConfig, data_manager: DataAccessManager):
        super().__init__(config)
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)
        
    def get_stage_name(self) -> str:
        """Get the name of this filtering stage."""
        return "filtered_symbols_step1"
    
    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        """
        Apply liquidity filtering to a list of stock symbols.
        
        Args:
            symbols: List of stock symbols to filter
            
        Returns:
            FilterResult containing passed and failed symbols
        """
        self.logger.info(f"Starting liquidity filtering for {len(symbols)} symbols")
        
        passed_symbols = []
        failed_symbols = []
        processed_count = 0
        
        criteria_applied = {
            "min_trading_volume_krw": self.config.min_trading_volume_krw,
            "trading_volume_period_days": self.config.trading_volume_period_days
        }
        
        for i, symbol in enumerate(symbols):
            try:
                # Progress tracking
                processed_count += 1
                if processed_count % 10 == 0 or processed_count == len(symbols):
                    progress_pct = (processed_count / len(symbols)) * 100
                    self.logger.info(f"Progress: {processed_count}/{len(symbols)} ({progress_pct:.1f}%)")
                
                # Get liquidity metrics for the symbol
                liquidity_metrics = self._get_liquidity_metrics(symbol)
                
                # Apply threshold filtering
                if self._meets_liquidity_criteria(liquidity_metrics):
                    passed_symbols.append(symbol)
                    self.logger.debug(f"PASS: {symbol.code} - Trading value: {liquidity_metrics.avg_daily_value:,.0f} KRW")
                else:
                    failed_symbols.append(symbol)
                    self.logger.debug(f"FAIL: {symbol.code} - Trading value: {liquidity_metrics.avg_daily_value:,.0f} KRW (below {self.config.min_trading_volume_krw:,.0f})")
                    
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
            f"Liquidity filtering complete: {len(passed_symbols)} passed, "
            f"{len(failed_symbols)} failed ({result.pass_rate:.1f}% pass rate)"
        )
        
        return result
    
    def _get_liquidity_metrics(self, symbol: StockSymbol) -> LiquidityMetrics:
        """
        Get liquidity metrics for a stock symbol.
        
        Args:
            symbol: Stock symbol to analyze
            
        Returns:
            LiquidityMetrics containing volume and value data
        """
        # Get trading data for the specified period
        trading_data = self.data_manager.get_trading_data(
            symbol, 
            self.config.trading_volume_period_days
        )
        
        if trading_data.empty:
            raise ValueError(f"No trading data available for {symbol.code}")
        
        # Calculate average daily volume and trading value
        avg_daily_volume = self._calculate_average_volume(trading_data['Volume'].tolist())
        avg_daily_value = self._calculate_average_trading_value(trading_data['TradingValue'].tolist())
        
        return LiquidityMetrics(
            symbol=symbol,
            avg_daily_volume=avg_daily_volume,
            avg_daily_value=avg_daily_value,
            period_days=len(trading_data)
        )
    
    def _calculate_average_volume(self, daily_volumes: List[float]) -> float:
        """
        Calculate average daily volume over the specified period.
        
        Args:
            daily_volumes: List of daily trading volumes
            
        Returns:
            Average daily volume
        """
        if not daily_volumes:
            return 0.0
        return sum(daily_volumes) / len(daily_volumes)
    
    def _calculate_average_trading_value(self, daily_trading_values: List[float]) -> float:
        """
        Calculate average daily trading value over the specified period.
        
        Args:
            daily_trading_values: List of daily trading values (price * volume)
            
        Returns:
            Average daily trading value in KRW
        """
        if not daily_trading_values:
            return 0.0
        return sum(daily_trading_values) / len(daily_trading_values)
    
    def _meets_liquidity_criteria(self, metrics: LiquidityMetrics) -> bool:
        """
        Check if liquidity metrics meet the filtering criteria.
        
        Args:
            metrics: LiquidityMetrics to evaluate
            
        Returns:
            True if metrics meet criteria, False otherwise
        """
        return metrics.avg_daily_value >= self.config.min_trading_volume_krw
    
    def get_liquidity_summary(self, symbols: List[StockSymbol]) -> Dict[str, Any]:
        """
        Get a summary of liquidity metrics for a list of symbols.
        
        Args:
            symbols: List of symbols to analyze
            
        Returns:
            Dictionary containing liquidity summary statistics
        """
        if not symbols:
            return {
                "total_symbols": 0,
                "avg_trading_value": 0.0,
                "min_trading_value": 0.0,
                "max_trading_value": 0.0,
                "symbols_above_threshold": 0
            }
        
        trading_values = []
        symbols_above_threshold = 0
        
        for symbol in symbols:
            try:
                metrics = self._get_liquidity_metrics(symbol)
                trading_values.append(metrics.avg_daily_value)
                
                if metrics.avg_daily_value >= self.config.min_trading_volume_krw:
                    symbols_above_threshold += 1
                    
            except Exception as e:
                self.logger.warning(f"Could not get liquidity metrics for {symbol.code}: {e}")
                continue
        
        if not trading_values:
            return {
                "total_symbols": len(symbols),
                "avg_trading_value": 0.0,
                "min_trading_value": 0.0,
                "max_trading_value": 0.0,
                "symbols_above_threshold": 0
            }
        
        return {
            "total_symbols": len(symbols),
            "avg_trading_value": sum(trading_values) / len(trading_values),
            "min_trading_value": min(trading_values),
            "max_trading_value": max(trading_values),
            "symbols_above_threshold": symbols_above_threshold,
            "threshold_pass_rate": (symbols_above_threshold / len(symbols)) * 100
        }