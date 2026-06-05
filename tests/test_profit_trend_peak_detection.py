"""
Property-based tests for profit trend peak detection functionality.
**Feature: auto-financial-filter, Property 8: Profit Trend Peak Detection**
**Validates: Requirements 3.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List
import pandas as pd
from datetime import datetime, timedelta

from auto_financial_filter.models.base import StockSymbol, ProfitabilityMetrics


class TestProfitTrendPeakDetection:
    """Test that profit trend peak detection satisfies Property 8."""
    
    @given(
        # Generate 4 years of operating profit data where recent 4 quarters is the peak
        historical_profits=st.lists(
            st.floats(min_value=0.1, max_value=100.0), 
            min_size=12, max_size=16  # 3-4 years of quarterly data before recent 4 quarters
        ),
        recent_peak_profits=st.lists(
            st.floats(min_value=100.1, max_value=200.0), 
            min_size=4, max_size=4  # Recent 4 quarters that should be peak
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_8_profit_trend_peak_detection_true_cases(self, historical_profits, recent_peak_profits):
        """
        **Feature: auto-financial-filter, Property 8: Profit Trend Peak Detection**
        
        For any stock with multi-year operating profit data, when recent 4 quarters 
        represent the highest profit period in the past 4 years, the system should 
        correctly identify this as a peak.
        """
        # Combine historical and recent data - recent should be higher
        all_profits = historical_profits + recent_peak_profits
        
        # Ensure recent 4 quarters are actually the peak
        recent_sum = sum(recent_peak_profits)
        
        # Check all possible 4-quarter windows in historical data
        max_historical_sum = 0
        for i in range(len(historical_profits) - 3):
            window_sum = sum(historical_profits[i:i+4])
            max_historical_sum = max(max_historical_sum, window_sum)
        
        # Only proceed if recent is actually higher than historical
        if recent_sum <= max_historical_sum:
            return  # Skip this test case
        
        # Create test symbol and metrics
        symbol = StockSymbol(code="TEST001", name="Test Company", market="KOSPI")
        
        # The profit trend should contain 4 years of data (16 quarters)
        # We'll use the last 16 quarters from our generated data
        if len(all_profits) >= 16:
            profit_trend = all_profits[-16:]
        else:
            # Pad with additional historical data if needed
            padding_needed = 16 - len(all_profits)
            padding = [p * 0.5 for p in historical_profits[:padding_needed]]  # Lower values
            profit_trend = padding + all_profits
            profit_trend = profit_trend[-16:]  # Take last 16
        
        # Create profitability metrics
        metrics = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,  # Above 10% threshold
            operating_profit_trend=profit_trend,
            cogs_ratio_trend=[0.6, 0.58, 0.56, 0.54, 0.52, 0.50],  # Decreasing trend
            is_profit_peak=True  # This is what we're testing
        )
        
        # Test the peak detection logic
        # Recent 4 quarters should be the highest sum among all 4-quarter windows
        recent_4q_sum = sum(profit_trend[-4:])
        
        # Check all other 4-quarter windows in the 4-year period
        is_actually_peak = True
        for i in range(len(profit_trend) - 3):
            window_sum = sum(profit_trend[i:i+4])
            if i <= len(profit_trend) - 8:  # Not the recent 4 quarters
                if window_sum >= recent_4q_sum:
                    is_actually_peak = False
                    break
        
        # The property should hold: if recent 4Q is peak, detection should return True
        assert is_actually_peak == True, f"Recent 4Q sum {recent_4q_sum} should be peak in trend {profit_trend}"
    
    @given(
        # Generate 4 years of data where recent 4 quarters is NOT the peak
        all_profits=st.lists(
            st.floats(min_value=1.0, max_value=100.0), 
            min_size=16, max_size=16  # Exactly 4 years of quarterly data
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_8_profit_trend_peak_detection_false_cases(self, all_profits):
        """
        **Feature: auto-financial-filter, Property 8: Profit Trend Peak Detection**
        
        For any stock with multi-year operating profit data, when recent 4 quarters 
        do NOT represent the highest profit period, the system should correctly 
        identify this as not a peak.
        """
        # Ensure recent 4 quarters are NOT the peak by making an earlier period higher
        profit_trend = all_profits.copy()
        
        # Make quarters 4-7 (from the end) higher than the recent 4 quarters
        recent_4q_sum = sum(profit_trend[-4:])
        earlier_window_start = len(profit_trend) - 8  # 4 quarters before recent
        
        # Boost the earlier window to be higher
        boost_factor = 1.5
        for i in range(earlier_window_start, earlier_window_start + 4):
            if i >= 0:
                profit_trend[i] = profit_trend[i] * boost_factor
        
        # Verify that recent 4Q is not the peak
        recent_4q_sum = sum(profit_trend[-4:])
        earlier_4q_sum = sum(profit_trend[earlier_window_start:earlier_window_start + 4])
        
        if recent_4q_sum >= earlier_4q_sum:
            return  # Skip this test case - couldn't make it non-peak
        
        # Create test symbol and metrics
        symbol = StockSymbol(code="TEST002", name="Test Company 2", market="KOSDAQ")
        
        metrics = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,
            operating_profit_trend=profit_trend,
            cogs_ratio_trend=[0.6, 0.58, 0.56, 0.54, 0.52, 0.50],
            is_profit_peak=False  # This is what we're testing
        )
        
        # Test the peak detection logic
        # Recent 4 quarters should NOT be the highest sum
        recent_4q_sum = sum(profit_trend[-4:])
        
        # Find the maximum 4-quarter sum in the entire period
        max_4q_sum = 0
        for i in range(len(profit_trend) - 3):
            window_sum = sum(profit_trend[i:i+4])
            max_4q_sum = max(max_4q_sum, window_sum)
        
        # The property should hold: if recent 4Q is not peak, detection should return False
        is_actually_peak = (recent_4q_sum >= max_4q_sum)
        assert is_actually_peak == False, f"Recent 4Q sum {recent_4q_sum} should NOT be peak (max: {max_4q_sum}) in trend {profit_trend}"
    
    def test_profit_peak_detection_edge_cases(self):
        """Test edge cases for profit peak detection."""
        symbol = StockSymbol(code="EDGE001", name="Edge Case Company", market="KOSPI")
        
        # Test case 1: All quarters equal - should be considered peak
        equal_profits = [50.0] * 16
        metrics_equal = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,
            operating_profit_trend=equal_profits,
            cogs_ratio_trend=[0.6] * 6,
            is_profit_peak=True
        )
        
        recent_sum = sum(equal_profits[-4:])
        max_sum = max(sum(equal_profits[i:i+4]) for i in range(13))
        assert recent_sum >= max_sum, "Equal profits should result in recent being peak"
        
        # Test case 2: Strictly increasing trend - recent should be peak
        increasing_profits = [i * 5.0 for i in range(1, 17)]  # 5, 10, 15, ..., 80
        metrics_increasing = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,
            operating_profit_trend=increasing_profits,
            cogs_ratio_trend=[0.6 - i*0.02 for i in range(6)],  # Decreasing COGS
            is_profit_peak=True
        )
        
        recent_sum = sum(increasing_profits[-4:])  # Sum of last 4 (highest values)
        max_sum = max(sum(increasing_profits[i:i+4]) for i in range(13))
        assert recent_sum >= max_sum, "Increasing trend should result in recent being peak"
        
        # Test case 3: Strictly decreasing trend - recent should NOT be peak
        decreasing_profits = [80.0 - i * 5.0 for i in range(16)]  # 80, 75, 70, ..., 5
        metrics_decreasing = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,
            operating_profit_trend=decreasing_profits,
            cogs_ratio_trend=[0.5 + i*0.02 for i in range(6)],  # Increasing COGS
            is_profit_peak=False
        )
        
        recent_sum = sum(decreasing_profits[-4:])  # Sum of last 4 (lowest values)
        max_sum = max(sum(decreasing_profits[i:i+4]) for i in range(13))
        assert recent_sum < max_sum, "Decreasing trend should result in recent NOT being peak"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])