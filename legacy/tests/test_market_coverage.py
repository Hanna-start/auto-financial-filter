"""
Property-based tests for market coverage completeness.

**Feature: auto-financial-filter, Property 1: Market Coverage Completeness**
**Validates: Requirements 1.1**
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import List, Set

from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.data_access.mock_adapters import MockFinanceDataReaderAdapter
from auto_financial_filter.config import FilterConfig


class TestMarketCoverageCompleteness:
    """Test market coverage completeness property."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
        self.adapter = MockFinanceDataReaderAdapter(self.config)
    
    def test_market_coverage_completeness_property(self):
        """
        **Feature: auto-financial-filter, Property 1: Market Coverage Completeness**
        
        Property: For any request to retrieve stock symbols, the returned list should 
        contain symbols from both KOSPI and KOSDAQ markets with no duplicates.
        
        **Validates: Requirements 1.1**
        """
        # Get symbols from both markets
        kospi_symbols = self.adapter.get_kospi_symbols()
        kosdaq_symbols = self.adapter.get_kosdaq_symbols()
        
        # Combine all symbols (simulating what the system would do)
        all_symbols = kospi_symbols + kosdaq_symbols
        
        # Property 1: Should contain symbols from both markets
        kospi_codes = {symbol.code for symbol in all_symbols if symbol.market == 'KOSPI'}
        kosdaq_codes = {symbol.code for symbol in all_symbols if symbol.market == 'KOSDAQ'}
        
        assert len(kospi_codes) > 0, "Should contain at least one KOSPI symbol"
        assert len(kosdaq_codes) > 0, "Should contain at least one KOSDAQ symbol"
        
        # Property 2: No duplicates should exist
        all_codes = [symbol.code for symbol in all_symbols]
        unique_codes = set(all_codes)
        
        assert len(all_codes) == len(unique_codes), f"Duplicate symbols found: {len(all_codes)} total vs {len(unique_codes)} unique"
        
        # Property 3: All symbols should have valid market designation
        for symbol in all_symbols:
            assert symbol.market in ['KOSPI', 'KOSDAQ'], f"Invalid market designation: {symbol.market}"
        
        # Property 4: All symbols should have non-empty codes and names
        for symbol in all_symbols:
            assert symbol.code.strip() != "", f"Empty symbol code found"
            assert symbol.name.strip() != "", f"Empty symbol name found for code: {symbol.code}"
    
    def test_kospi_symbols_only_kospi_market(self):
        """Test that KOSPI symbols are correctly marked as KOSPI market."""
        kospi_symbols = self.adapter.get_kospi_symbols()
        
        for symbol in kospi_symbols:
            assert symbol.market == 'KOSPI', f"KOSPI symbol {symbol.code} has incorrect market: {symbol.market}"
    
    def test_kosdaq_symbols_only_kosdaq_market(self):
        """Test that KOSDAQ symbols are correctly marked as KOSDAQ market."""
        kosdaq_symbols = self.adapter.get_kosdaq_symbols()
        
        for symbol in kosdaq_symbols:
            assert symbol.market == 'KOSDAQ', f"KOSDAQ symbol {symbol.code} has incorrect market: {symbol.market}"
    
    def test_no_overlap_between_markets(self):
        """Test that there's no overlap between KOSPI and KOSDAQ symbol codes."""
        kospi_symbols = self.adapter.get_kospi_symbols()
        kosdaq_symbols = self.adapter.get_kosdaq_symbols()
        
        kospi_codes = {symbol.code for symbol in kospi_symbols}
        kosdaq_codes = {symbol.code for symbol in kosdaq_symbols}
        
        overlap = kospi_codes.intersection(kosdaq_codes)
        assert len(overlap) == 0, f"Found overlapping symbol codes between markets: {overlap}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])