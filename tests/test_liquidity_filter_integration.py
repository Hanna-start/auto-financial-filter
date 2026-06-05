"""
Integration tests for LiquidityFilter implementation.
"""

import pytest
from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.filters import LiquidityFilter
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
from auto_financial_filter.config import FilterConfig


class TestLiquidityFilterIntegration:
    """Test LiquidityFilter integration with mock data."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
        self.data_manager = MockDataAccessManager(self.config)
        self.liquidity_filter = LiquidityFilter(self.config, self.data_manager)
    
    def test_liquidity_filter_basic_functionality(self):
        """Test basic liquidity filtering functionality."""
        # Create test symbols
        symbols = [
            StockSymbol(code="TEST001", name="Test Company 1", market="KOSPI"),
            StockSymbol(code="TEST002", name="Test Company 2", market="KOSDAQ"),
        ]
        
        # Apply filter
        result = self.liquidity_filter.filter(symbols)
        
        # Verify result structure
        assert result.stage == "filtered_symbols_step1"
        assert isinstance(result.passed_symbols, list)
        assert isinstance(result.failed_symbols, list)
        assert result.total_processed == len(symbols)
        
        # Verify criteria applied
        assert "min_trading_volume_krw" in result.criteria_applied
        assert "trading_volume_period_days" in result.criteria_applied
        assert result.criteria_applied["min_trading_volume_krw"] == self.config.min_trading_volume_krw
        assert result.criteria_applied["trading_volume_period_days"] == self.config.trading_volume_period_days
    
    def test_liquidity_filter_stage_name(self):
        """Test that the filter returns the correct stage name."""
        assert self.liquidity_filter.get_stage_name() == "filtered_symbols_step1"
    
    def test_liquidity_filter_with_empty_list(self):
        """Test liquidity filter with empty symbol list."""
        result = self.liquidity_filter.filter([])
        
        assert len(result.passed_symbols) == 0
        assert len(result.failed_symbols) == 0
        assert result.total_processed == 0
        assert result.pass_rate == 0.0
    
    def test_liquidity_filter_configuration_applied(self):
        """Test that configuration parameters are properly applied."""
        # Create custom config
        custom_config = FilterConfig(
            min_trading_volume_krw=5_000_000_000,  # 5 billion KRW
            trading_volume_period_days=20
        )
        
        custom_filter = LiquidityFilter(custom_config, self.data_manager)
        
        symbols = [StockSymbol(code="TEST001", name="Test Company", market="KOSPI")]
        result = custom_filter.filter(symbols)
        
        # Verify custom configuration is applied
        assert result.criteria_applied["min_trading_volume_krw"] == 5_000_000_000
        assert result.criteria_applied["trading_volume_period_days"] == 20
    
    def test_get_liquidity_summary(self):
        """Test liquidity summary functionality."""
        symbols = [
            StockSymbol(code="TEST001", name="Test Company 1", market="KOSPI"),
            StockSymbol(code="TEST002", name="Test Company 2", market="KOSDAQ"),
        ]
        
        summary = self.liquidity_filter.get_liquidity_summary(symbols)
        
        # Verify summary structure
        assert "total_symbols" in summary
        assert "avg_trading_value" in summary
        assert "min_trading_value" in summary
        assert "max_trading_value" in summary
        assert "symbols_above_threshold" in summary
        
        assert summary["total_symbols"] == len(symbols)
        assert isinstance(summary["avg_trading_value"], (int, float))
        assert isinstance(summary["min_trading_value"], (int, float))
        assert isinstance(summary["max_trading_value"], (int, float))
        assert isinstance(summary["symbols_above_threshold"], int)
    
    def test_get_liquidity_summary_empty_list(self):
        """Test liquidity summary with empty symbol list."""
        summary = self.liquidity_filter.get_liquidity_summary([])
        
        assert summary["total_symbols"] == 0
        assert summary["avg_trading_value"] == 0.0
        assert summary["min_trading_value"] == 0.0
        assert summary["max_trading_value"] == 0.0
        assert summary["symbols_above_threshold"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])