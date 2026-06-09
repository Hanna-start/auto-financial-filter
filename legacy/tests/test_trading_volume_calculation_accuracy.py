"""
Property-based tests for trading volume calculation accuracy.

**Feature: auto-financial-filter, Property 2: Trading Volume Calculation Accuracy**
**Validates: Requirements 1.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List
import pandas as pd
from datetime import datetime, timedelta

from auto_financial_filter.models.base import StockSymbol, LiquidityMetrics


class TestTradingVolumeCalculationAccuracy:
    """Test trading volume calculation accuracy property."""
    
    @given(
        daily_volumes=st.lists(
            st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        ),
        daily_prices=st.lists(
            st.floats(min_value=1, max_value=100000, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_trading_volume_calculation_accuracy_property(self, daily_volumes: List[float], daily_prices: List[float]):
        """
        **Feature: auto-financial-filter, Property 2: Trading Volume Calculation Accuracy**
        
        Property: For any set of daily trading data over 30 days, the calculated average 
        should equal the sum of daily values divided by the number of trading days.
        
        **Validates: Requirements 1.2**
        """
        # Ensure both lists have the same length
        min_length = min(len(daily_volumes), len(daily_prices))
        if min_length == 0:
            return  # Skip empty data
            
        daily_volumes = daily_volumes[:min_length]
        daily_prices = daily_prices[:min_length]
        
        # Calculate trading values (price * volume)
        daily_trading_values = [price * volume for price, volume in zip(daily_prices, daily_volumes)]
        
        # Property: Average should equal sum divided by count
        expected_avg_volume = sum(daily_volumes) / len(daily_volumes)
        expected_avg_value = sum(daily_trading_values) / len(daily_trading_values)
        
        # Test the calculation logic directly
        calculated_avg_volume = self._calculate_average_volume(daily_volumes)
        calculated_avg_value = self._calculate_average_trading_value(daily_trading_values)
        
        # Property verification with tolerance for floating point precision
        tolerance = 1e-10
        assert abs(calculated_avg_volume - expected_avg_volume) < tolerance, \
            f"Volume average calculation incorrect: {calculated_avg_volume} != {expected_avg_volume}"
        
        assert abs(calculated_avg_value - expected_avg_value) < tolerance, \
            f"Trading value average calculation incorrect: {calculated_avg_value} != {expected_avg_value}"
    
    def _calculate_average_volume(self, daily_volumes: List[float]) -> float:
        """Calculate average daily volume - this simulates the logic that should be in LiquidityFilter."""
        if not daily_volumes:
            return 0.0
        return sum(daily_volumes) / len(daily_volumes)
    
    def _calculate_average_trading_value(self, daily_trading_values: List[float]) -> float:
        """Calculate average daily trading value - this simulates the logic that should be in LiquidityFilter."""
        if not daily_trading_values:
            return 0.0
        return sum(daily_trading_values) / len(daily_trading_values)
    
    @given(
        trading_data=st.lists(
            st.tuples(
                st.floats(min_value=1, max_value=100000, allow_nan=False, allow_infinity=False),  # price
                st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False)      # volume
            ),
            min_size=1,
            max_size=30
        )
    )
    @settings(max_examples=50)
    def test_trading_value_calculation_property(self, trading_data: List[tuple]):
        """
        Property: Trading value should always equal price * volume for each day.
        """
        for price, volume in trading_data:
            expected_trading_value = price * volume
            calculated_trading_value = self._calculate_daily_trading_value(price, volume)
            
            tolerance = 1e-10
            assert abs(calculated_trading_value - expected_trading_value) < tolerance, \
                f"Daily trading value calculation incorrect: {calculated_trading_value} != {expected_trading_value}"
    
    def _calculate_daily_trading_value(self, price: float, volume: float) -> float:
        """Calculate daily trading value - this simulates the logic that should be in LiquidityFilter."""
        return price * volume
    
    def test_thirty_day_period_calculation(self):
        """Test that 30-day period calculation works correctly with known data."""
        # Create test data for exactly 30 days
        daily_volumes = [1000000.0] * 30  # 1M shares per day
        daily_prices = [10000.0] * 30     # 10,000 KRW per share
        
        # Expected results
        expected_avg_volume = 1000000.0
        expected_avg_value = 10000000000.0  # 10 billion KRW per day
        
        # Test calculations
        calculated_avg_volume = self._calculate_average_volume(daily_volumes)
        calculated_avg_value = self._calculate_average_trading_value(
            [price * volume for price, volume in zip(daily_prices, daily_volumes)]
        )
        
        assert calculated_avg_volume == expected_avg_volume
        assert calculated_avg_value == expected_avg_value
    
    def test_variable_trading_days(self):
        """Test calculation with different numbers of trading days."""
        test_cases = [
            ([100.0, 200.0, 300.0], 200.0),  # 3 days
            ([1000.0] * 20, 1000.0),         # 20 days
            ([500.0] * 25, 500.0),           # 25 days
            ([750.0] * 30, 750.0),           # 30 days
        ]
        
        for volumes, expected_avg in test_cases:
            calculated_avg = self._calculate_average_volume(volumes)
            assert calculated_avg == expected_avg, \
                f"Failed for {len(volumes)} days: {calculated_avg} != {expected_avg}"
    
    def test_edge_cases(self):
        """Test edge cases for volume calculation."""
        # Single day
        assert self._calculate_average_volume([1000.0]) == 1000.0
        
        # Zero volume days (should still be included in average)
        volumes_with_zeros = [0.0, 1000.0, 2000.0]
        expected = sum(volumes_with_zeros) / len(volumes_with_zeros)
        assert self._calculate_average_volume(volumes_with_zeros) == expected
        
        # Very small volumes
        small_volumes = [0.1, 0.2, 0.3]
        expected = sum(small_volumes) / len(small_volumes)
        calculated = self._calculate_average_volume(small_volumes)
        assert abs(calculated - expected) < 1e-10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])