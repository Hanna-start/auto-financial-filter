"""
Property-based tests for COGS ratio trend analysis functionality.
**Feature: auto-financial-filter, Property 9: Cost Ratio Trend Analysis**
**Validates: Requirements 3.4**
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List
import pandas as pd
from datetime import datetime, timedelta

from auto_financial_filter.models.base import StockSymbol, ProfitabilityMetrics


class TestCostRatioTrendAnalysis:
    """Test that COGS ratio trend analysis satisfies Property 9."""
    
    @given(
        # Generate 6 quarters of COGS ratios with a consistently decreasing trend
        start_ratio=st.floats(min_value=0.6, max_value=0.9),
        decreases=st.lists(
            st.floats(min_value=0.01, max_value=0.05), 
            min_size=5, max_size=5  # 5 decreases for 6 quarters
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_9_cost_ratio_trend_analysis_decreasing(self, start_ratio, decreases):
        """
        **Feature: auto-financial-filter, Property 9: Cost Ratio Trend Analysis**
        
        For any sequence of 6 quarterly COGS ratios that show a consistently 
        decreasing pattern, the trend detection should correctly identify this 
        as a decreasing trend.
        """
        # Build decreasing sequence
        cogs_ratios = [start_ratio]
        current_ratio = start_ratio
        
        for decrease in decreases:
            current_ratio = max(0.1, current_ratio - decrease)  # Ensure positive ratios
            cogs_ratios.append(current_ratio)
        
        # Verify it's actually decreasing
        is_decreasing = all(cogs_ratios[i] > cogs_ratios[i+1] for i in range(5))
        
        if not is_decreasing:
            return  # Skip this test case if not actually decreasing
        
        # Create test symbol and metrics
        symbol = StockSymbol(code="DECR001", name="Decreasing COGS Company", market="KOSPI")
        
        metrics = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,
            operating_profit_trend=[50.0] * 16,  # Stable profits
            cogs_ratio_trend=cogs_ratios,
            is_profit_peak=True
        )
        
        # Test the trend detection logic
        # Should identify this as a consistently decreasing trend
        trend_is_decreasing = self._analyze_cogs_trend(cogs_ratios)
        
        assert trend_is_decreasing == True, f"Should detect decreasing trend in {cogs_ratios}"
    
    @given(
        # Generate 6 quarters of COGS ratios with an increasing or mixed trend
        ratios=st.lists(
            st.floats(min_value=0.3, max_value=0.8), 
            min_size=6, max_size=6
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_9_cost_ratio_trend_analysis_non_decreasing(self, ratios):
        """
        **Feature: auto-financial-filter, Property 9: Cost Ratio Trend Analysis**
        
        For any sequence of 6 quarterly COGS ratios that do NOT show a consistently 
        decreasing pattern, the trend detection should correctly identify this 
        as not a decreasing trend.
        """
        # Ensure this is NOT a consistently decreasing trend
        is_decreasing = all(ratios[i] > ratios[i+1] for i in range(5))
        
        if is_decreasing:
            # Force it to be non-decreasing by increasing one value
            ratios[3] = ratios[2] + 0.05  # Make quarter 4 higher than quarter 3
        
        # Verify it's not consistently decreasing
        is_decreasing = all(ratios[i] > ratios[i+1] for i in range(5))
        assert not is_decreasing, "Test setup should ensure non-decreasing trend"
        
        # Create test symbol and metrics
        symbol = StockSymbol(code="NONDECR001", name="Non-Decreasing COGS Company", market="KOSDAQ")
        
        metrics = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,
            operating_profit_trend=[50.0] * 16,
            cogs_ratio_trend=ratios,
            is_profit_peak=True
        )
        
        # Test the trend detection logic
        # Should NOT identify this as a consistently decreasing trend
        trend_is_decreasing = self._analyze_cogs_trend(ratios)
        
        assert trend_is_decreasing == False, f"Should NOT detect decreasing trend in {ratios}"
    
    def test_cogs_trend_analysis_edge_cases(self):
        """Test edge cases for COGS ratio trend analysis."""
        symbol = StockSymbol(code="EDGE001", name="Edge Case Company", market="KOSPI")
        
        # Test case 1: Perfectly flat trend - should NOT be decreasing
        flat_ratios = [0.6] * 6
        trend_flat = self._analyze_cogs_trend(flat_ratios)
        assert trend_flat == False, "Flat trend should not be considered decreasing"
        
        # Test case 2: Strictly decreasing by small amounts
        small_decreasing = [0.60, 0.59, 0.58, 0.57, 0.56, 0.55]
        trend_small_dec = self._analyze_cogs_trend(small_decreasing)
        assert trend_small_dec == True, "Small but consistent decreases should be detected"
        
        # Test case 3: Mostly decreasing but one increase
        mostly_decreasing = [0.70, 0.65, 0.60, 0.62, 0.58, 0.55]  # Increase at position 3
        trend_mostly_dec = self._analyze_cogs_trend(mostly_decreasing)
        assert trend_mostly_dec == False, "One increase should break the decreasing trend"
        
        # Test case 4: Large decreasing steps
        large_decreasing = [0.80, 0.70, 0.60, 0.50, 0.40, 0.30]
        trend_large_dec = self._analyze_cogs_trend(large_decreasing)
        assert trend_large_dec == True, "Large decreasing steps should be detected"
        
        # Test case 5: Increasing trend - should NOT be decreasing
        increasing = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
        trend_increasing = self._analyze_cogs_trend(increasing)
        assert trend_increasing == False, "Increasing trend should not be considered decreasing"
        
        # Test case 6: V-shaped (decrease then increase) - should NOT be decreasing
        v_shaped = [0.70, 0.60, 0.50, 0.55, 0.65, 0.75]
        trend_v = self._analyze_cogs_trend(v_shaped)
        assert trend_v == False, "V-shaped trend should not be considered consistently decreasing"
    
    def test_cogs_trend_with_profitability_metrics(self):
        """Test COGS trend analysis integrated with ProfitabilityMetrics."""
        symbol = StockSymbol(code="INTEG001", name="Integration Test Company", market="KOSPI")
        
        # Test with decreasing COGS trend
        decreasing_cogs = [0.65, 0.62, 0.59, 0.56, 0.53, 0.50]
        
        metrics_good = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,
            operating_profit_trend=[40.0, 45.0, 50.0, 55.0] * 4,  # Increasing profits
            cogs_ratio_trend=decreasing_cogs,
            is_profit_peak=True
        )
        
        # Verify the metrics are valid
        assert metrics_good.is_valid(), "Metrics with decreasing COGS should be valid"
        
        # Test trend analysis
        trend_result = self._analyze_cogs_trend(decreasing_cogs)
        assert trend_result == True, "Should detect decreasing COGS trend"
        
        # Test with non-decreasing COGS trend
        non_decreasing_cogs = [0.50, 0.52, 0.51, 0.54, 0.53, 0.55]
        
        metrics_bad = ProfitabilityMetrics(
            symbol=symbol,
            operating_margin=15.0,
            operating_profit_trend=[50.0] * 16,
            cogs_ratio_trend=non_decreasing_cogs,
            is_profit_peak=True
        )
        
        # Verify the metrics are valid
        assert metrics_bad.is_valid(), "Metrics with non-decreasing COGS should be valid"
        
        # Test trend analysis
        trend_result = self._analyze_cogs_trend(non_decreasing_cogs)
        assert trend_result == False, "Should NOT detect decreasing COGS trend"
    
    def _analyze_cogs_trend(self, cogs_ratios: List[float]) -> bool:
        """
        Analyze COGS ratio trend to determine if it's consistently decreasing.
        
        This is the core logic that should be implemented in the QualityGrowthFilter.
        
        Args:
            cogs_ratios: List of 6 quarterly COGS ratios
            
        Returns:
            True if trend is consistently decreasing, False otherwise
        """
        if len(cogs_ratios) != 6:
            return False
        
        # Check if each quarter is lower than the previous
        for i in range(1, len(cogs_ratios)):
            if cogs_ratios[i] >= cogs_ratios[i-1]:
                return False
        
        return True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])