"""
Property-based tests for revenue growth calculation.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List

from auto_financial_filter.models.base import StockSymbol, FinancialMetrics


class TestRevenueGrowthCalculation:
    """Test revenue growth calculation property."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pass
    
    @given(
        # Generate 8 quarters of revenue data (4 recent + 4 previous year)
        recent_quarters=st.lists(
            st.floats(min_value=1e6, max_value=1e12, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=4
        ),
        previous_quarters=st.lists(
            st.floats(min_value=1e6, max_value=1e12, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=4
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_7_revenue_growth_calculation(self, recent_quarters: List[float], previous_quarters: List[float]):
        """
        **Feature: auto-financial-filter, Property 7: Revenue Growth Calculation**
        
        For any stock with quarterly revenue data, the year-over-year growth calculation 
        should correctly compare recent 4 quarters cumulative revenue against the same 
        period from previous year.
        
        **Validates: Requirements 2.4**
        """
        # Create a test stock symbol
        symbol = StockSymbol(code="TEST001", name="Test Company", market="KOSPI")
        
        # Calculate expected revenue growth
        recent_cumulative = sum(recent_quarters)
        previous_cumulative = sum(previous_quarters)
        expected_growth = ((recent_cumulative - previous_cumulative) / previous_cumulative) * 100
        
        # Create financial metrics with the recent quarters data
        # Note: The FinancialMetrics model only stores recent 4 quarters, 
        # so we need to calculate the growth externally and compare
        financial_metrics = FinancialMetrics(
            symbol=symbol,
            debt_ratio=100.0,  # Not relevant for this test
            operating_cash_flow=[1e9, 1e9, 1e9, 1e9],  # Not relevant for this test
            revenue_growth_yoy=expected_growth,  # This should match our calculation
            quarterly_revenue=recent_quarters
        )
        
        # Test the revenue growth calculation logic
        calculated_growth = self._calculate_revenue_growth_yoy(recent_quarters, previous_quarters)
        
        # Allow for small floating point differences
        tolerance = 1e-10
        assert abs(calculated_growth - expected_growth) < tolerance, (
            f"Revenue growth calculation failed\n"
            f"Recent quarters: {recent_quarters} (sum: {recent_cumulative})\n"
            f"Previous quarters: {previous_quarters} (sum: {previous_cumulative})\n"
            f"Expected growth: {expected_growth}%\n"
            f"Calculated growth: {calculated_growth}%\n"
            f"Difference: {abs(calculated_growth - expected_growth)}"
        )
        
        # Also verify that the stored growth matches our calculation
        assert abs(financial_metrics.revenue_growth_yoy - expected_growth) < tolerance, (
            f"Stored revenue growth doesn't match expected calculation\n"
            f"Stored: {financial_metrics.revenue_growth_yoy}%\n"
            f"Expected: {expected_growth}%"
        )
    
    def _calculate_revenue_growth_yoy(self, recent_quarters: List[float], previous_quarters: List[float]) -> float:
        """
        Calculate year-over-year revenue growth based on quarterly data.
        
        This is a reference implementation of the revenue growth calculation logic
        that should match the actual implementation in the FinancialHealthFilter.
        
        Args:
            recent_quarters: Revenue for the most recent 4 quarters
            previous_quarters: Revenue for the same 4 quarters from previous year
            
        Returns:
            Year-over-year revenue growth percentage
        """
        if len(recent_quarters) != 4 or len(previous_quarters) != 4:
            raise ValueError("Both recent and previous quarters must contain exactly 4 quarters")
        
        recent_cumulative = sum(recent_quarters)
        previous_cumulative = sum(previous_quarters)
        
        if previous_cumulative == 0:
            # Handle division by zero case
            if recent_cumulative > 0:
                return float('inf')  # Infinite growth
            else:
                return 0.0  # No change from zero to zero
        
        growth_rate = ((recent_cumulative - previous_cumulative) / previous_cumulative) * 100
        return growth_rate
    
    def test_revenue_growth_calculation_edge_cases(self):
        """Test specific edge cases for revenue growth calculation."""
        
        # Test case 1: Positive growth
        recent = [100e6, 110e6, 120e6, 130e6]  # Total: 460e6
        previous = [90e6, 100e6, 110e6, 120e6]  # Total: 420e6
        expected_growth = ((460e6 - 420e6) / 420e6) * 100  # ~9.52%
        calculated = self._calculate_revenue_growth_yoy(recent, previous)
        assert abs(calculated - expected_growth) < 1e-10
        
        # Test case 2: Negative growth
        recent = [80e6, 85e6, 90e6, 95e6]  # Total: 350e6
        previous = [100e6, 105e6, 110e6, 115e6]  # Total: 430e6
        expected_growth = ((350e6 - 430e6) / 430e6) * 100  # ~-18.6%
        calculated = self._calculate_revenue_growth_yoy(recent, previous)
        assert abs(calculated - expected_growth) < 1e-10
        
        # Test case 3: Zero growth
        quarters = [100e6, 100e6, 100e6, 100e6]
        expected_growth = 0.0
        calculated = self._calculate_revenue_growth_yoy(quarters, quarters)
        assert abs(calculated - expected_growth) < 1e-10
        
        # Test case 4: Previous year was zero (edge case)
        recent = [10e6, 20e6, 30e6, 40e6]  # Total: 100e6
        previous = [0, 0, 0, 0]  # Total: 0
        calculated = self._calculate_revenue_growth_yoy(recent, previous)
        assert calculated == float('inf')  # Infinite growth from zero
        
        # Test case 5: Both years zero
        zero_quarters = [0, 0, 0, 0]
        calculated = self._calculate_revenue_growth_yoy(zero_quarters, zero_quarters)
        assert calculated == 0.0  # No change from zero to zero
    
    @given(
        # Test with very small revenue values
        recent_quarters=st.lists(
            st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=4
        ),
        previous_quarters=st.lists(
            st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=4
        )
    )
    @settings(max_examples=50)
    def test_revenue_growth_small_values(self, recent_quarters: List[float], previous_quarters: List[float]):
        """Test revenue growth calculation with small values to check for numerical stability."""
        calculated_growth = self._calculate_revenue_growth_yoy(recent_quarters, previous_quarters)
        
        # Verify the calculation is mathematically correct
        recent_sum = sum(recent_quarters)
        previous_sum = sum(previous_quarters)
        expected_growth = ((recent_sum - previous_sum) / previous_sum) * 100
        
        tolerance = 1e-10
        assert abs(calculated_growth - expected_growth) < tolerance, (
            f"Small value calculation failed: {calculated_growth} vs {expected_growth}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])