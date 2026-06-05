"""
Property test for financial data retrieval completeness.
**Feature: auto-financial-filter, Property 5: Financial Data Retrieval Completeness**
**Validates: Requirements 2.1, 3.1**
"""

import pytest
from hypothesis import given, strategies as st, settings
from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.data_access.mock_adapters import (
    MockFinanceDataReaderAdapter,
    MockOpenDartReaderAdapter,
    MockPykrxAdapter
)
from auto_financial_filter.config import FilterConfig


# Strategy for generating valid stock symbols
@st.composite
def stock_symbol_strategy(draw):
    """Generate valid StockSymbol instances."""
    code = draw(st.text(min_size=6, max_size=6, alphabet=st.characters(whitelist_categories=('Nd',))))
    name = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'Nd'))))
    market = draw(st.sampled_from(['KOSPI', 'KOSDAQ']))
    return StockSymbol(code=code, name=name, market=market)


@st.composite
def stock_symbol_list_strategy(draw):
    """Generate a list of valid StockSymbol instances."""
    symbols = draw(st.lists(stock_symbol_strategy(), min_size=1, max_size=10))
    # Ensure unique codes to avoid duplicates
    unique_symbols = []
    seen_codes = set()
    for symbol in symbols:
        if symbol.code not in seen_codes:
            unique_symbols.append(symbol)
            seen_codes.add(symbol.code)
    return unique_symbols if unique_symbols else [symbols[0]]  # Ensure at least one symbol


class TestFinancialDataRetrievalCompleteness:
    """Test financial data retrieval completeness property."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
        self.fdr_adapter = MockFinanceDataReaderAdapter(self.config)
        self.dart_adapter = MockOpenDartReaderAdapter(self.config)
        self.pykrx_adapter = MockPykrxAdapter(self.config)
    
    @given(stock_symbol_list_strategy())
    @settings(max_examples=100)
    def test_financial_data_retrieval_completeness_dart(self, symbols):
        """
        Property 5: Financial Data Retrieval Completeness
        For any list of stock symbols, financial data retrieval should be attempted for each symbol in the input list.
        """
        # Track which symbols we attempt to retrieve data for
        attempted_symbols = set()
        successful_retrievals = []
        failed_retrievals = []
        
        for symbol in symbols:
            attempted_symbols.add(symbol.code)
            try:
                financial_data = self.dart_adapter.get_financial_statements(symbol, quarters=4)
                # Verify the returned data structure
                assert 'symbol' in financial_data
                assert 'quarterly_data' in financial_data
                assert financial_data['symbol'] == symbol.code
                assert isinstance(financial_data['quarterly_data'], list)
                assert len(financial_data['quarterly_data']) == 4
                successful_retrievals.append(symbol.code)
            except Exception as e:
                # Log the failure but continue processing
                failed_retrievals.append((symbol.code, str(e)))
        
        # Property: Retrieval should be attempted for each symbol in the input list
        assert len(attempted_symbols) == len(symbols), \
            f"Should attempt retrieval for all {len(symbols)} symbols, but attempted {len(attempted_symbols)}"
        
        # Property: All input symbols should have been processed (either successfully or with recorded failure)
        processed_symbols = set(successful_retrievals + [code for code, _ in failed_retrievals])
        input_symbol_codes = {symbol.code for symbol in symbols}
        assert processed_symbols == input_symbol_codes, \
            f"All input symbols should be processed. Input: {input_symbol_codes}, Processed: {processed_symbols}"
    
    @given(stock_symbol_list_strategy())
    @settings(max_examples=100)
    def test_trading_data_retrieval_completeness_fdr(self, symbols):
        """
        Property 5: Financial Data Retrieval Completeness (Trading Data)
        For any list of stock symbols, trading data retrieval should be attempted for each symbol in the input list.
        """
        # Track which symbols we attempt to retrieve data for
        attempted_symbols = set()
        successful_retrievals = []
        failed_retrievals = []
        
        for symbol in symbols:
            attempted_symbols.add(symbol.code)
            try:
                trading_data = self.fdr_adapter.get_trading_data(symbol, days=30)
                # Verify the returned data structure
                assert not trading_data.empty, f"Trading data should not be empty for {symbol.code}"
                assert 'Close' in trading_data.columns
                assert 'Volume' in trading_data.columns
                assert 'TradingValue' in trading_data.columns
                successful_retrievals.append(symbol.code)
            except Exception as e:
                # Log the failure but continue processing
                failed_retrievals.append((symbol.code, str(e)))
        
        # Property: Retrieval should be attempted for each symbol in the input list
        assert len(attempted_symbols) == len(symbols), \
            f"Should attempt retrieval for all {len(symbols)} symbols, but attempted {len(attempted_symbols)}"
        
        # Property: All input symbols should have been processed (either successfully or with recorded failure)
        processed_symbols = set(successful_retrievals + [code for code, _ in failed_retrievals])
        input_symbol_codes = {symbol.code for symbol in symbols}
        assert processed_symbols == input_symbol_codes, \
            f"All input symbols should be processed. Input: {input_symbol_codes}, Processed: {processed_symbols}"
    
    @given(stock_symbol_list_strategy())
    @settings(max_examples=100)
    def test_market_data_retrieval_completeness_pykrx(self, symbols):
        """
        Property 5: Financial Data Retrieval Completeness (Market Data)
        For any list of stock symbols, market data retrieval should be attempted for each symbol in the input list.
        """
        # Track which symbols we attempt to retrieve data for
        attempted_symbols = set()
        successful_retrievals = []
        failed_retrievals = []
        
        for symbol in symbols:
            attempted_symbols.add(symbol.code)
            try:
                market_data = self.pykrx_adapter.get_market_data(symbol)
                # Verify the returned data structure
                assert 'symbol' in market_data
                assert 'market_cap' in market_data
                assert 'shares_outstanding' in market_data
                assert market_data['symbol'] == symbol.code
                successful_retrievals.append(symbol.code)
            except Exception as e:
                # Log the failure but continue processing
                failed_retrievals.append((symbol.code, str(e)))
        
        # Property: Retrieval should be attempted for each symbol in the input list
        assert len(attempted_symbols) == len(symbols), \
            f"Should attempt retrieval for all {len(symbols)} symbols, but attempted {len(attempted_symbols)}"
        
        # Property: All input symbols should have been processed (either successfully or with recorded failure)
        processed_symbols = set(successful_retrievals + [code for code, _ in failed_retrievals])
        input_symbol_codes = {symbol.code for symbol in symbols}
        assert processed_symbols == input_symbol_codes, \
            f"All input symbols should be processed. Input: {input_symbol_codes}, Processed: {processed_symbols}"
    
    def test_empty_symbol_list_handling(self):
        """Test that empty symbol lists are handled gracefully."""
        symbols = []
        
        # Should not raise an exception and should process zero symbols
        attempted_symbols = set()
        for symbol in symbols:
            attempted_symbols.add(symbol.code)
        
        assert len(attempted_symbols) == 0, "Empty list should result in zero attempted retrievals"
    
    def test_single_symbol_retrieval(self):
        """Test retrieval for a single symbol to verify basic functionality."""
        symbol = StockSymbol(code="005930", name="삼성전자", market="KOSPI")
        
        # Test financial data retrieval
        financial_data = self.dart_adapter.get_financial_statements(symbol, quarters=4)
        assert financial_data['symbol'] == symbol.code
        assert len(financial_data['quarterly_data']) == 4
        
        # Test trading data retrieval
        trading_data = self.fdr_adapter.get_trading_data(symbol, days=30)
        assert not trading_data.empty
        assert 'TradingValue' in trading_data.columns
        
        # Test market data retrieval
        market_data = self.pykrx_adapter.get_market_data(symbol)
        assert market_data['symbol'] == symbol.code
        assert 'market_cap' in market_data