"""
Integration test to verify LiquidityFilter works with the pipeline.
"""

import pytest
from auto_financial_filter.models.base import StockSymbol
from auto_financial_filter.filters import LiquidityFilter
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
from auto_financial_filter.config import FilterConfig


class TestPipelineIntegration:
    """Test LiquidityFilter integration with the main pipeline."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
        self.data_manager = MockDataAccessManager(self.config)
        self.pipeline = StockFilterPipeline(self.config)
    
    def test_liquidity_filter_in_pipeline(self):
        """Test that LiquidityFilter works correctly when added to the pipeline."""
        # Create and add the liquidity filter to the pipeline
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        self.pipeline.add_filter(liquidity_filter)
        
        # Create test symbols
        symbols = [
            StockSymbol(code="TEST001", name="Test Company 1", market="KOSPI"),
            StockSymbol(code="TEST002", name="Test Company 2", market="KOSDAQ"),
            StockSymbol(code="TEST003", name="Test Company 3", market="KOSPI"),
        ]
        
        # Execute the pipeline
        result = self.pipeline.execute(symbols)
        
        # Verify pipeline result structure
        assert len(result.stage_results) == 1, "Should have one stage result"
        assert result.total_processed == len(symbols), "Should process all input symbols"
        assert isinstance(result.final_candidates, list), "Final candidates should be a list"
        assert result.execution_time_seconds > 0, "Should have positive execution time"
        
        # Verify the stage result
        stage_result = result.stage_results[0]
        assert stage_result.stage == "filtered_symbols_step1", "Should be liquidity filter stage"
        assert stage_result.total_processed == len(symbols), "Should process all symbols"
        
        # Verify criteria were applied
        assert "min_trading_volume_krw" in stage_result.criteria_applied
        assert "trading_volume_period_days" in stage_result.criteria_applied
        
        # Verify final candidates match passed symbols
        assert result.final_candidates == stage_result.passed_symbols
    
    def test_pipeline_summary_generation(self):
        """Test that pipeline generates correct summary with LiquidityFilter."""
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        self.pipeline.add_filter(liquidity_filter)
        
        symbols = [StockSymbol(code="TEST001", name="Test Company", market="KOSPI")]
        result = self.pipeline.execute(symbols)
        
        # Get summary
        summary = result.get_summary()
        
        # Verify summary structure
        assert "total_processed" in summary
        assert "final_candidates" in summary
        assert "execution_time_seconds" in summary
        assert "stages" in summary
        
        assert summary["total_processed"] == 1
        assert len(summary["stages"]) == 1
        
        # Verify stage summary
        stage_summary = summary["stages"][0]
        assert stage_summary["stage"] == "filtered_symbols_step1"
        assert "input_count" in stage_summary
        assert "passed_count" in stage_summary
        assert "failed_count" in stage_summary
        assert "pass_rate" in stage_summary
        assert "criteria" in stage_summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])