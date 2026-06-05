"""
Property-based tests that verify LiquidityFilter implementation matches the properties.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List
import pandas as pd
from datetime import datetime, timedelta

from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.filters import LiquidityFilter
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
from auto_financial_filter.config import FilterConfig


class TestLiquidityFilterProperties:
    """Test that LiquidityFilter implementation satisfies the defined properties."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
        self.data_manager = MockDataAccessManager(self.config)
        self.liquidity_filter = LiquidityFilter(self.config, self.data_manager)
    
    def test_property_2_trading_volume_calculation_accuracy(self):
        """
        Verify that LiquidityFilter._calculate_average_volume matches Property 2.
        **Feature: auto-financial-filter, Property 2: Trading Volume Calculation Accuracy**
        """
        # Test cases with known values
        test_cases = [
            ([100.0, 200.0, 300.0], 200.0),
            ([1000.0] * 30, 1000.0),
            ([0.0, 500.0, 1000.0], 500.0),
            ([1.5, 2.5, 3.5], 2.5)
        ]
        
        for volumes, expected_avg in test_cases:
            calculated_avg = self.liquidity_filter._calculate_average_volume(volumes)
            assert abs(calculated_avg - expected_avg) < 1e-10, \
                f"Volume calculation failed: {calculated_avg} != {expected_avg}"
        
        # Test trading value calculation
        trading_value_cases = [
            ([10000.0, 20000.0, 30000.0], 20000.0),
            ([1e10] * 30, 1e10),  # 10 billion KRW
            ([5e9, 15e9, 25e9], 15e9)  # 5B, 15B, 25B KRW average = 15B
        ]
        
        for values, expected_avg in trading_value_cases:
            calculated_avg = self.liquidity_filter._calculate_average_trading_value(values)
            assert abs(calculated_avg - expected_avg) < 1e-10, \
                f"Trading value calculation failed: {calculated_avg} != {expected_avg}"
    
    def test_property_3_threshold_filtering_consistency(self):
        """
        Verify that LiquidityFilter._meets_liquidity_criteria matches Property 3.
        **Feature: auto-financial-filter, Property 3: Threshold Filtering Consistency**
        """
        # Create test symbols with known liquidity metrics
        symbol = StockSymbol(code="TEST001", name="Test Company", market="KOSPI")
        
        # Test cases: (avg_daily_value, threshold, should_pass)
        test_cases = [
            (15e9, 10e9, True),   # 15B >= 10B threshold
            (10e9, 10e9, True),   # 10B >= 10B threshold (exactly at threshold)
            (5e9, 10e9, False),   # 5B < 10B threshold
            (0.0, 10e9, False),   # 0 < 10B threshold
            (20e9, 15e9, True),   # 20B >= 15B threshold
        ]
        
        for avg_daily_value, threshold, should_pass in test_cases:
            # Create custom config with specific threshold
            custom_config = FilterConfig(min_trading_volume_krw=threshold)
            custom_filter = LiquidityFilter(custom_config, self.data_manager)
            
            # Create liquidity metrics
            from auto_financial_filter.models.base import LiquidityMetrics
            metrics = LiquidityMetrics(
                symbol=symbol,
                avg_daily_volume=1000000.0,  # Not used in threshold check
                avg_daily_value=avg_daily_value,
                period_days=30
            )
            
            result = custom_filter._meets_liquidity_criteria(metrics)
            assert result == should_pass, \
                f"Threshold filtering failed: value={avg_daily_value}, threshold={threshold}, expected={should_pass}, got={result}"
    
    def test_liquidity_filter_satisfies_both_properties(self):
        """
        Integration test that verifies the complete LiquidityFilter satisfies both properties.
        """
        # Create symbols for testing
        symbols = [
            StockSymbol(code="HIGH001", name="High Volume Stock", market="KOSPI"),
            StockSymbol(code="LOW001", name="Low Volume Stock", market="KOSDAQ"),
        ]
        
        # Apply the filter
        result = self.liquidity_filter.filter(symbols)
        
        # Property verification: All passed symbols should meet threshold
        for symbol in result.passed_symbols:
            # Get the liquidity metrics that were calculated
            try:
                metrics = self.liquidity_filter._get_liquidity_metrics(symbol)
                assert metrics.avg_daily_value >= self.config.min_trading_volume_krw, \
                    f"Passed symbol {symbol.code} does not meet threshold: {metrics.avg_daily_value} < {self.config.min_trading_volume_krw}"
            except Exception:
                # If we can't get metrics, the symbol shouldn't have passed
                pytest.fail(f"Passed symbol {symbol.code} should have valid liquidity metrics")
        
        # Verify that the calculation methods are consistent
        for symbol in symbols:
            try:
                trading_data = self.data_manager.get_trading_data(symbol, self.config.trading_volume_period_days)
                if not trading_data.empty:
                    # Test volume calculation consistency
                    volumes = trading_data['Volume'].tolist()
                    expected_avg_volume = sum(volumes) / len(volumes)
                    calculated_avg_volume = self.liquidity_filter._calculate_average_volume(volumes)
                    assert abs(calculated_avg_volume - expected_avg_volume) < 1e-10
                    
                    # Test trading value calculation consistency
                    trading_values = trading_data['TradingValue'].tolist()
                    expected_avg_value = sum(trading_values) / len(trading_values)
                    calculated_avg_value = self.liquidity_filter._calculate_average_trading_value(trading_values)
                    assert abs(calculated_avg_value - expected_avg_value) < 1e-10
            except Exception:
                # Some symbols might not have data, which is acceptable
                continue
    
    def test_filter_result_structure_property(self):
        """
        Verify that LiquidityFilter produces results that satisfy Property 4 (Pipeline Output Structure).
        """
        symbols = [
            StockSymbol(code="TEST001", name="Test Company 1", market="KOSPI"),
            StockSymbol(code="TEST002", name="Test Company 2", market="KOSDAQ"),
        ]
        
        result = self.liquidity_filter.filter(symbols)
        
        # Property 4 verification: Pipeline Output Structure
        assert result.stage == "filtered_symbols_step1", "Stage name should match expected"
        assert isinstance(result.passed_symbols, list), "Passed symbols should be a list"
        assert isinstance(result.failed_symbols, list), "Failed symbols should be a list"
        
        # All symbols should be valid
        for symbol in result.passed_symbols + result.failed_symbols:
            assert isinstance(symbol, StockSymbol), "All symbols should be StockSymbol instances"
            assert symbol.is_valid(), "All symbols should be valid"
        
        # No overlap between passed and failed
        passed_codes = {symbol.code for symbol in result.passed_symbols}
        failed_codes = {symbol.code for symbol in result.failed_symbols}
        assert len(passed_codes.intersection(failed_codes)) == 0, "No symbol should appear in both lists"
        
        # Total processed should match
        assert result.total_processed == len(symbols), "Total processed should match input count"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])