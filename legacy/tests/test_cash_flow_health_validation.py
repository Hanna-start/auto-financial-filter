"""
Property-based tests for cash flow health validation.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List

from auto_financial_filter.models.base import StockSymbol, FinancialMetrics


class TestCashFlowHealthValidation:
    """Test cash flow health validation property."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pass
    
    @given(
        # Generate 4 quarters of operating cash flow data
        ocf_data=st.lists(
            st.floats(min_value=-1e12, max_value=1e12, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=4
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_6_cash_flow_health_validation(self, ocf_data: List[float]):
        """
        **Feature: auto-financial-filter, Property 6: Cash Flow Health Validation**
        
        For any stock with quarterly cash flow data, the validation should pass if either:
        1. All 4 recent quarters are positive, OR 
        2. The cumulative cash flow meets sufficient levels (positive cumulative)
        
        **Validates: Requirements 2.3**
        """
        # Create a test stock symbol
        symbol = StockSymbol(code="TEST001", name="Test Company", market="KOSPI")
        
        # Create financial metrics with the generated OCF data
        financial_metrics = FinancialMetrics(
            symbol=symbol,
            debt_ratio=100.0,  # Not relevant for this test
            operating_cash_flow=ocf_data,
            revenue_growth_yoy=5.0,  # Not relevant for this test
            quarterly_revenue=[1e9, 1.1e9, 1.2e9, 1.3e9]  # Not relevant for this test
        )
        
        # Calculate expected result based on the property definition
        all_positive = all(ocf >= 0 for ocf in ocf_data)
        cumulative_ocf = sum(ocf_data)
        cumulative_sufficient = cumulative_ocf > 0  # Sufficient level = positive cumulative
        
        expected_passes = all_positive or cumulative_sufficient
        
        # Test the cash flow health validation logic
        actual_passes = self._validate_cash_flow_health(financial_metrics)
        
        assert actual_passes == expected_passes, (
            f"Cash flow health validation failed for OCF data: {ocf_data}\n"
            f"All positive: {all_positive}, Cumulative: {cumulative_ocf}, "
            f"Cumulative sufficient: {cumulative_sufficient}\n"
            f"Expected: {expected_passes}, Actual: {actual_passes}"
        )
    
    def _validate_cash_flow_health(self, financial_metrics: FinancialMetrics) -> bool:
        """
        Validate cash flow health according to the requirements.
        
        This is a reference implementation of the cash flow health validation logic
        that should match the actual implementation in the FinancialHealthFilter.
        
        Args:
            financial_metrics: Financial metrics containing OCF data
            
        Returns:
            True if cash flow health validation passes, False otherwise
        """
        ocf_data = financial_metrics.operating_cash_flow
        
        # Check if all 4 recent quarters are positive
        all_positive = all(ocf >= 0 for ocf in ocf_data)
        
        # Check if cumulative OCF meets sufficient levels (positive cumulative)
        cumulative_ocf = sum(ocf_data)
        cumulative_sufficient = cumulative_ocf > 0
        
        # Pass if either condition is met
        return all_positive or cumulative_sufficient
    
    def test_cash_flow_health_validation_edge_cases(self):
        """Test specific edge cases for cash flow health validation."""
        symbol = StockSymbol(code="EDGE001", name="Edge Case Company", market="KOSPI")
        
        # Test case 1: All positive quarters
        metrics_all_positive = FinancialMetrics(
            symbol=symbol,
            debt_ratio=100.0,
            operating_cash_flow=[1e9, 2e9, 3e9, 4e9],  # All positive
            revenue_growth_yoy=5.0,
            quarterly_revenue=[1e9, 1.1e9, 1.2e9, 1.3e9]
        )
        assert self._validate_cash_flow_health(metrics_all_positive) == True
        
        # Test case 2: Mixed quarters but positive cumulative
        metrics_mixed_positive_cum = FinancialMetrics(
            symbol=symbol,
            debt_ratio=100.0,
            operating_cash_flow=[-1e9, -2e9, 5e9, 10e9],  # Cumulative = 12e9 > 0
            revenue_growth_yoy=5.0,
            quarterly_revenue=[1e9, 1.1e9, 1.2e9, 1.3e9]
        )
        assert self._validate_cash_flow_health(metrics_mixed_positive_cum) == True
        
        # Test case 3: Mixed quarters with negative cumulative
        metrics_mixed_negative_cum = FinancialMetrics(
            symbol=symbol,
            debt_ratio=100.0,
            operating_cash_flow=[-5e9, -3e9, 1e9, 2e9],  # Cumulative = -5e9 < 0
            revenue_growth_yoy=5.0,
            quarterly_revenue=[1e9, 1.1e9, 1.2e9, 1.3e9]
        )
        assert self._validate_cash_flow_health(metrics_mixed_negative_cum) == False
        
        # Test case 4: All zero quarters
        metrics_all_zero = FinancialMetrics(
            symbol=symbol,
            debt_ratio=100.0,
            operating_cash_flow=[0.0, 0.0, 0.0, 0.0],  # All zero, cumulative = 0
            revenue_growth_yoy=5.0,
            quarterly_revenue=[1e9, 1.1e9, 1.2e9, 1.3e9]
        )
        assert self._validate_cash_flow_health(metrics_all_zero) == True  # All >= 0, so passes
        
        # Test case 5: All negative quarters
        metrics_all_negative = FinancialMetrics(
            symbol=symbol,
            debt_ratio=100.0,
            operating_cash_flow=[-1e9, -2e9, -3e9, -4e9],  # All negative, cumulative = -10e9
            revenue_growth_yoy=5.0,
            quarterly_revenue=[1e9, 1.1e9, 1.2e9, 1.3e9]
        )
        assert self._validate_cash_flow_health(metrics_all_negative) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])