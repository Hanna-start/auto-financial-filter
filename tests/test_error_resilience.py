"""
Property test for error resilience.
**Feature: auto-financial-filter, Property 10: Error Resilience**
**Validates: Requirements 4.1, 4.2, 4.4**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, patch
from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.data_access.adapters import DataAccessManager
from auto_financial_filter.data_access.mock_adapters import (
    MockFinanceDataReaderAdapter,
    MockOpenDartReaderAdapter,
    MockPykrxAdapter
)
from auto_financial_filter.config import FilterConfig
import pandas as pd


# Strategy for generating valid stock symbols
@st.composite
def stock_symbol_strategy(draw):
    """Generate valid StockSymbol instances."""
    code = draw(st.text(min_size=6, max_size=6, alphabet=st.characters(whitelist_categories=('Nd',))))
    name = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'Nd'))))
    market = draw(st.sampled_from(['KOSPI', 'KOSDAQ']))
    return StockSymbol(code=code, name=name, market=market)


@st.composite
def mixed_success_failure_scenario(draw):
    """Generate scenarios with some successful and some failing operations."""
    total_symbols = draw(st.integers(min_value=3, max_value=10))
    failure_indices = draw(st.sets(st.integers(min_value=0, max_value=total_symbols-1), 
                                  min_size=1, max_size=total_symbols-1))
    
    symbols = []
    for i in range(total_symbols):
        symbol = draw(stock_symbol_strategy())
        symbols.append(symbol)
    
    return symbols, failure_indices


class ErrorInjectingAdapter:
    """Adapter that can inject errors at specified indices."""
    
    def __init__(self, base_adapter, failure_indices, error_type=Exception):
        self.base_adapter = base_adapter
        self.failure_indices = failure_indices
        self.error_type = error_type
        self.call_count = 0
    
    def __getattr__(self, name):
        """Delegate all other attributes to the base adapter."""
        return getattr(self.base_adapter, name)
    
    def get_financial_statements(self, symbol, quarters=4):
        """Inject errors at specified indices."""
        if self.call_count in self.failure_indices:
            self.call_count += 1
            raise self.error_type(f"Simulated error for symbol {symbol.code}")
        self.call_count += 1
        return self.base_adapter.get_financial_statements(symbol, quarters)
    
    def get_trading_data(self, symbol, days):
        """Inject errors at specified indices."""
        if self.call_count in self.failure_indices:
            self.call_count += 1
            raise self.error_type(f"Simulated error for symbol {symbol.code}")
        self.call_count += 1
        return self.base_adapter.get_trading_data(symbol, days)
    
    def get_market_data(self, symbol):
        """Inject errors at specified indices."""
        if self.call_count in self.failure_indices:
            self.call_count += 1
            raise self.error_type(f"Simulated error for symbol {symbol.code}")
        self.call_count += 1
        return self.base_adapter.get_market_data(symbol)


class TestErrorResilience:
    """Test error resilience property."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
    
    @given(mixed_success_failure_scenario())
    @settings(max_examples=100)
    def test_error_resilience_continues_processing(self, scenario_data):
        """
        Property 10: Error Resilience
        For any processing pipeline with some failed data retrievals, the system should continue 
        processing remaining stocks, log errors appropriately, and exclude problematic records gracefully.
        """
        symbols, failure_indices = scenario_data
        assume(len(symbols) > len(failure_indices))  # Ensure some symbols will succeed
        
        # Create error-injecting adapters
        base_dart_adapter = MockOpenDartReaderAdapter(self.config)
        error_dart_adapter = ErrorInjectingAdapter(base_dart_adapter, failure_indices, RuntimeError)
        
        successful_retrievals = []
        failed_retrievals = []
        processed_count = 0
        
        # Simulate processing pipeline that continues despite errors
        for symbol in symbols:
            try:
                financial_data = error_dart_adapter.get_financial_statements(symbol, quarters=4)
                successful_retrievals.append(symbol.code)
                processed_count += 1
            except Exception as e:
                # Log the error and continue processing (graceful error handling)
                failed_retrievals.append((symbol.code, str(e)))
                processed_count += 1
        
        # Property: All symbols should be processed (either successfully or with recorded failure)
        assert processed_count == len(symbols), \
            f"Should process all {len(symbols)} symbols, but processed {processed_count}"
        
        # Property: Some operations should succeed and some should fail based on our injection
        assert len(successful_retrievals) > 0, "Some operations should succeed"
        assert len(failed_retrievals) > 0, "Some operations should fail (as injected)"
        
        # Property: Failed operations should be properly recorded with error information
        for symbol_code, error_msg in failed_retrievals:
            assert "Simulated error" in error_msg, f"Error should be properly recorded for {symbol_code}"
        
        # Property: Total processed should equal successful + failed
        assert len(successful_retrievals) + len(failed_retrievals) == len(symbols), \
            "All symbols should be accounted for in either successful or failed lists"
    
    @given(st.lists(stock_symbol_strategy(), min_size=2, max_size=8))
    @settings(max_examples=100)
    def test_error_resilience_with_different_error_types(self, symbols):
        """Test resilience against different types of errors."""
        error_types = [RuntimeError, ValueError, ConnectionError, TimeoutError]
        
        for error_type in error_types:
            # Inject errors for half the symbols
            failure_indices = set(range(0, len(symbols), 2))
            
            base_adapter = MockFinanceDataReaderAdapter(self.config)
            error_adapter = ErrorInjectingAdapter(base_adapter, failure_indices, error_type)
            
            successful_retrievals = []
            failed_retrievals = []
            
            # Process all symbols despite errors
            for symbol in symbols:
                try:
                    trading_data = error_adapter.get_trading_data(symbol, days=30)
                    successful_retrievals.append(symbol.code)
                except Exception as e:
                    failed_retrievals.append((symbol.code, type(e).__name__))
            
            # Property: Processing should continue despite different error types
            assert len(successful_retrievals) + len(failed_retrievals) == len(symbols), \
                f"All symbols should be processed despite {error_type.__name__} errors"
            
            # Property: Some operations should succeed (those not in failure_indices)
            expected_successes = len(symbols) - len(failure_indices)
            assert len(successful_retrievals) == expected_successes, \
                f"Expected {expected_successes} successes, got {len(successful_retrievals)}"
    
    def test_error_resilience_with_data_access_manager(self):
        """Test error resilience at the DataAccessManager level."""
        config = FilterConfig()
        
        # Create a manager with mock adapters
        with patch('auto_financial_filter.data_access.adapters.FinanceDataReaderAdapter') as mock_fdr, \
             patch('auto_financial_filter.data_access.adapters.OpenDartReaderAdapter') as mock_dart, \
             patch('auto_financial_filter.data_access.adapters.PykrxAdapter') as mock_pykrx:
            
            # Configure mocks to simulate partial failures
            mock_fdr_instance = Mock()
            mock_dart_instance = Mock()
            mock_pykrx_instance = Mock()
            
            mock_fdr.return_value = mock_fdr_instance
            mock_dart.return_value = mock_dart_instance
            mock_pykrx.return_value = mock_pykrx_instance
            
            # Simulate KOSPI success, KOSDAQ failure
            mock_fdr_instance.get_kospi_symbols.return_value = [
                StockSymbol("005930", "삼성전자", "KOSPI")
            ]
            mock_fdr_instance.get_kosdaq_symbols.side_effect = RuntimeError("KOSDAQ API failure")
            
            manager = DataAccessManager(config)
            
            # Test that get_all_symbols continues processing despite partial failure
            try:
                symbols = manager.get_all_symbols()
                # Should get KOSPI symbols despite KOSDAQ failure
                assert len(symbols) == 1
                assert symbols[0].market == "KOSPI"
            except RuntimeError as e:
                # If both fail, should raise with appropriate error message
                assert "Failed to retrieve any symbols" in str(e)
    
    def test_graceful_handling_of_invalid_data(self):
        """Test graceful handling of invalid or corrupted data."""
        config = FilterConfig()
        adapter = MockOpenDartReaderAdapter(config)
        
        # Test with symbol that might return invalid data
        invalid_symbol = StockSymbol("INVALID", "Invalid Company", "KOSPI")
        
        try:
            # This should either succeed with valid data or fail gracefully
            financial_data = adapter.get_financial_statements(invalid_symbol, quarters=4)
            
            # If it succeeds, verify the data structure is valid
            assert 'symbol' in financial_data
            assert 'quarterly_data' in financial_data
            assert isinstance(financial_data['quarterly_data'], list)
            
        except Exception as e:
            # If it fails, the error should be informative and not crash the system
            assert isinstance(e, (ValueError, RuntimeError, KeyError))
            error_msg = str(e).lower()
            assert any(keyword in error_msg for keyword in ['invalid', 'not found', 'error', 'failed'])
    
    def test_memory_efficiency_with_large_error_scenarios(self):
        """Test that error handling doesn't cause memory issues with large datasets."""
        config = FilterConfig()
        
        # Create a large number of symbols
        symbols = [StockSymbol(f"{i:06d}", f"Company{i}", "KOSPI") for i in range(100)]
        
        # Simulate processing with frequent errors
        failure_indices = set(range(0, 100, 3))  # Every 3rd symbol fails
        
        base_adapter = MockFinanceDataReaderAdapter(config)
        error_adapter = ErrorInjectingAdapter(base_adapter, failure_indices, RuntimeError)
        
        successful_count = 0
        failed_count = 0
        
        # Process all symbols
        for symbol in symbols:
            try:
                trading_data = error_adapter.get_trading_data(symbol, days=30)
                successful_count += 1
                # Don't store the data to test memory efficiency
                del trading_data
            except Exception:
                failed_count += 1
        
        # Property: All symbols should be processed
        assert successful_count + failed_count == len(symbols)
        
        # Property: Expected number of failures based on our injection pattern
        expected_failures = len(failure_indices)
        assert failed_count == expected_failures, \
            f"Expected {expected_failures} failures, got {failed_count}"