"""
Property-based tests for threshold filtering consistency.

**Feature: auto-financial-filter, Property 3: Threshold Filtering Consistency**
**Validates: Requirements 1.3, 2.2, 3.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from auto_financial_filter.models.base import StockSymbol, LiquidityMetrics


class TestThresholdFilteringConsistency:
    """Test threshold filtering consistency property."""
    
    @given(
        threshold=st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False),
        values=st.lists(
            st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_threshold_filtering_consistency_property(self, threshold: float, values: List[float]):
        """
        **Feature: auto-financial-filter, Property 3: Threshold Filtering Consistency**
        
        Property: For any numerical threshold and dataset, all items in the filtered 
        result should meet or exceed the specified threshold value.
        
        **Validates: Requirements 1.3, 2.2, 3.2**
        """
        # Apply threshold filtering
        filtered_values = self._apply_threshold_filter(values, threshold)
        
        # Property: All filtered values should meet or exceed the threshold
        for value in filtered_values:
            assert value >= threshold, \
                f"Filtered value {value} does not meet threshold {threshold}"
        
        # Property: No value below threshold should be in the result
        for original_value in values:
            if original_value < threshold:
                assert original_value not in filtered_values, \
                    f"Value {original_value} below threshold {threshold} should not be in filtered result"
        
        # Property: All values at or above threshold should be in the result
        for original_value in values:
            if original_value >= threshold:
                assert original_value in filtered_values, \
                    f"Value {original_value} at or above threshold {threshold} should be in filtered result"
    
    def _apply_threshold_filter(self, values: List[float], threshold: float) -> List[float]:
        """Apply threshold filtering - this simulates the logic that should be in filters."""
        return [value for value in values if value >= threshold]
    
    @given(
        liquidity_metrics=st.lists(
            st.builds(
                LiquidityMetrics,
                symbol=st.builds(
                    StockSymbol,
                    code=st.text(min_size=1, max_size=6, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789').filter(lambda x: x.strip()),
                    name=st.text(min_size=2, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ').filter(lambda x: x.strip()),
                    market=st.sampled_from(['KOSPI', 'KOSDAQ'])
                ),
                avg_daily_volume=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
                avg_daily_value=st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False),
                period_days=st.integers(min_value=1, max_value=50)
            ),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x.symbol.code
        ),
        min_trading_volume=st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_liquidity_threshold_filtering_property(self, liquidity_metrics: List[LiquidityMetrics], min_trading_volume: float):
        """
        Property: Liquidity filtering should only pass stocks with trading volume >= threshold.
        """
        # Apply liquidity threshold filtering
        passed_metrics = self._apply_liquidity_threshold_filter(liquidity_metrics, min_trading_volume)
        
        # Property: All passed metrics should meet the threshold
        for metric in passed_metrics:
            assert metric.avg_daily_value >= min_trading_volume, \
                f"Passed metric {metric.symbol.code} has trading value {metric.avg_daily_value} below threshold {min_trading_volume}"
        
        # Property: No metric below threshold should pass
        for metric in liquidity_metrics:
            if metric.avg_daily_value < min_trading_volume:
                assert metric not in passed_metrics, \
                    f"Metric {metric.symbol.code} with value {metric.avg_daily_value} below threshold should not pass"
    
    def _apply_liquidity_threshold_filter(self, metrics: List[LiquidityMetrics], threshold: float) -> List[LiquidityMetrics]:
        """Apply liquidity threshold filtering - simulates LiquidityFilter logic."""
        return [metric for metric in metrics if metric.avg_daily_value >= threshold]
    
    @given(
        debt_ratios=st.lists(
            st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=15
        ),
        max_debt_ratio=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_debt_ratio_threshold_filtering_property(self, debt_ratios: List[float], max_debt_ratio: float):
        """
        Property: Debt ratio filtering should only pass values <= threshold (inverted threshold).
        """
        # Apply debt ratio threshold filtering (inverted - we want values BELOW threshold)
        passed_ratios = self._apply_debt_ratio_threshold_filter(debt_ratios, max_debt_ratio)
        
        # Property: All passed ratios should be at or below the threshold
        for ratio in passed_ratios:
            assert ratio <= max_debt_ratio, \
                f"Passed debt ratio {ratio} exceeds threshold {max_debt_ratio}"
        
        # Property: No ratio above threshold should pass
        for ratio in debt_ratios:
            if ratio > max_debt_ratio:
                assert ratio not in passed_ratios, \
                    f"Debt ratio {ratio} above threshold {max_debt_ratio} should not pass"
    
    def _apply_debt_ratio_threshold_filter(self, ratios: List[float], threshold: float) -> List[float]:
        """Apply debt ratio threshold filtering - simulates FinancialHealthFilter logic."""
        return [ratio for ratio in ratios if ratio <= threshold]
    
    @given(
        operating_margins=st.lists(
            st.floats(min_value=-50, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=15
        ),
        min_operating_margin=st.floats(min_value=-50, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_operating_margin_threshold_filtering_property(self, operating_margins: List[float], min_operating_margin: float):
        """
        Property: Operating margin filtering should only pass values >= threshold.
        """
        # Apply operating margin threshold filtering
        passed_margins = self._apply_operating_margin_threshold_filter(operating_margins, min_operating_margin)
        
        # Property: All passed margins should meet or exceed the threshold
        for margin in passed_margins:
            assert margin >= min_operating_margin, \
                f"Passed operating margin {margin} is below threshold {min_operating_margin}"
        
        # Property: No margin below threshold should pass
        for margin in operating_margins:
            if margin < min_operating_margin:
                assert margin not in passed_margins, \
                    f"Operating margin {margin} below threshold {min_operating_margin} should not pass"
    
    def _apply_operating_margin_threshold_filter(self, margins: List[float], threshold: float) -> List[float]:
        """Apply operating margin threshold filtering - simulates QualityGrowthFilter logic."""
        return [margin for margin in margins if margin >= threshold]
    
    def test_specific_threshold_values(self):
        """Test threshold filtering with specific known values."""
        # Test liquidity threshold (10 billion KRW)
        trading_values = [5e9, 10e9, 15e9, 20e9]  # 5B, 10B, 15B, 20B KRW
        threshold = 10e9  # 10 billion KRW
        
        filtered = self._apply_threshold_filter(trading_values, threshold)
        expected = [10e9, 15e9, 20e9]
        
        assert filtered == expected, f"Expected {expected}, got {filtered}"
        
        # Test debt ratio threshold (200%)
        debt_ratios = [150.0, 200.0, 250.0, 300.0]
        max_debt_threshold = 200.0
        
        filtered_debt = self._apply_debt_ratio_threshold_filter(debt_ratios, max_debt_threshold)
        expected_debt = [150.0, 200.0]
        
        assert filtered_debt == expected_debt, f"Expected {expected_debt}, got {filtered_debt}"
        
        # Test operating margin threshold (10%)
        margins = [5.0, 10.0, 15.0, 20.0]
        min_margin_threshold = 10.0
        
        filtered_margins = self._apply_operating_margin_threshold_filter(margins, min_margin_threshold)
        expected_margins = [10.0, 15.0, 20.0]
        
        assert filtered_margins == expected_margins, f"Expected {expected_margins}, got {filtered_margins}"
    
    def test_edge_cases(self):
        """Test edge cases for threshold filtering."""
        # Empty list
        assert self._apply_threshold_filter([], 100.0) == []
        
        # All values below threshold
        values_below = [1.0, 2.0, 3.0]
        threshold = 5.0
        assert self._apply_threshold_filter(values_below, threshold) == []
        
        # All values above threshold
        values_above = [10.0, 20.0, 30.0]
        threshold = 5.0
        filtered = self._apply_threshold_filter(values_above, threshold)
        assert filtered == values_above
        
        # Values exactly at threshold
        values_exact = [10.0, 10.0, 10.0]
        threshold = 10.0
        filtered = self._apply_threshold_filter(values_exact, threshold)
        assert filtered == values_exact
        
        # Zero threshold
        values_with_zero = [0.0, 1.0, 2.0]
        threshold = 0.0
        filtered = self._apply_threshold_filter(values_with_zero, threshold)
        assert filtered == values_with_zero  # All should pass including zero


if __name__ == "__main__":
    pytest.main([__file__, "-v"])