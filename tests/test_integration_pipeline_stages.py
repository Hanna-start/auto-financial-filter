"""
Integration tests for pipeline stages.

Tests data flow between filtering stages, error propagation and recovery,
and performance with large datasets.
"""

import pytest
import time
from unittest.mock import Mock, patch
from typing import List

from auto_financial_filter.pipeline import StockFilterPipeline, PipelineResult
from auto_financial_filter.config import FilterConfig
from auto_financial_filter.models.base import StockSymbol, FilterResult
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
from auto_financial_filter.filters.liquidity_filter import LiquidityFilter
from auto_financial_filter.filters.financial_health_filter import FinancialHealthFilter
from auto_financial_filter.filters.quality_growth_filter import QualityGrowthFilter


class TestPipelineStageIntegration:
    """Test integration between different pipeline stages."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig(
            min_trading_volume_krw=5_000_000_000,
            max_debt_ratio_percent=150.0,
            min_revenue_growth_percent=5.0,
            min_operating_margin_percent=8.0
        )
        self.data_manager = MockDataAccessManager(self.config)
        self.pipeline = StockFilterPipeline(self.config)
        
        # Create test symbols
        self.test_symbols = [
            StockSymbol("005930", "삼성전자", "KOSPI"),
            StockSymbol("000660", "SK하이닉스", "KOSPI"),
            StockSymbol("035420", "NAVER", "KOSDAQ"),
            StockSymbol("051910", "LG화학", "KOSPI"),
            StockSymbol("006400", "삼성SDI", "KOSPI")
        ]
    
    def test_single_stage_pipeline_execution(self):
        """Test pipeline execution with a single filter stage."""
        # Add only liquidity filter
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        self.pipeline.add_filter(liquidity_filter)
        
        result = self.pipeline.execute(self.test_symbols)
        
        # Verify result structure
        assert isinstance(result, PipelineResult)
        assert result.total_processed == len(self.test_symbols)
        assert len(result.stage_results) == 1
        assert result.stage_results[0].stage == "filtered_symbols_step1"
        assert result.execution_time_seconds > 0
        
        # Verify data flow
        stage_result = result.stage_results[0]
        assert stage_result.total_processed == len(self.test_symbols)
        assert len(stage_result.passed_symbols) + len(stage_result.failed_symbols) == len(self.test_symbols)
        
        # Final candidates should match the passed symbols from the last stage
        assert result.final_candidates == stage_result.passed_symbols
    
    def test_two_stage_pipeline_execution(self):
        """Test pipeline execution with two filter stages."""
        # Add liquidity and financial health filters
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        financial_filter = FinancialHealthFilter(self.config, self.data_manager)
        
        self.pipeline.add_filter(liquidity_filter)
        self.pipeline.add_filter(financial_filter)
        
        result = self.pipeline.execute(self.test_symbols)
        
        # Verify result structure
        assert len(result.stage_results) == 2
        assert result.stage_results[0].stage == "filtered_symbols_step1"
        assert result.stage_results[1].stage == "Financial Health Filter"
        
        # Verify data flow between stages
        stage1_result = result.stage_results[0]
        stage2_result = result.stage_results[1]
        
        # Stage 2 input should equal Stage 1 output
        assert stage2_result.total_processed == len(stage1_result.passed_symbols)
        
        # Final candidates should match Stage 2 output
        assert result.final_candidates == stage2_result.passed_symbols
        
        # Verify progressive filtering (each stage should have <= input)
        assert len(stage1_result.passed_symbols) <= stage1_result.total_processed
        assert len(stage2_result.passed_symbols) <= stage2_result.total_processed
    
    def test_three_stage_pipeline_execution(self):
        """Test complete pipeline execution with all three filter stages."""
        # Add all three filters
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        financial_filter = FinancialHealthFilter(self.config, self.data_manager)
        quality_filter = QualityGrowthFilter(self.config, self.data_manager)
        
        self.pipeline.add_filter(liquidity_filter)
        self.pipeline.add_filter(financial_filter)
        self.pipeline.add_filter(quality_filter)
        
        result = self.pipeline.execute(self.test_symbols)
        
        # Verify complete pipeline structure
        assert len(result.stage_results) == 3
        assert result.stage_results[0].stage == "filtered_symbols_step1"
        assert result.stage_results[1].stage == "Financial Health Filter"
        assert result.stage_results[2].stage == "final_candidate_list"
        
        # Verify data flow through all stages
        stage1_result = result.stage_results[0]
        stage2_result = result.stage_results[1]
        stage3_result = result.stage_results[2]
        
        # Verify progressive data flow
        assert stage1_result.total_processed == len(self.test_symbols)
        assert stage2_result.total_processed == len(stage1_result.passed_symbols)
        assert stage3_result.total_processed == len(stage2_result.passed_symbols)
        
        # Final candidates should match final stage output
        assert result.final_candidates == stage3_result.passed_symbols
        
        # Verify progressive filtering effect
        assert len(stage1_result.passed_symbols) <= len(self.test_symbols)
        assert len(stage2_result.passed_symbols) <= len(stage1_result.passed_symbols)
        assert len(stage3_result.passed_symbols) <= len(stage2_result.passed_symbols)
    
    def test_empty_pipeline_execution(self):
        """Test pipeline execution with no filters."""
        result = self.pipeline.execute(self.test_symbols)
        
        # Should return all symbols as final candidates
        assert result.total_processed == len(self.test_symbols)
        assert result.final_candidates == self.test_symbols
        assert len(result.stage_results) == 0
        assert result.execution_time_seconds > 0
    
    def test_empty_symbol_list_execution(self):
        """Test pipeline execution with empty symbol list."""
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        self.pipeline.add_filter(liquidity_filter)
        
        result = self.pipeline.execute([])
        
        assert result.total_processed == 0
        assert len(result.final_candidates) == 0
        assert len(result.stage_results) == 1
        assert result.stage_results[0].total_processed == 0


class TestErrorPropagationAndRecovery:
    """Test error handling and recovery in pipeline stages."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
        self.test_symbols = [
            StockSymbol("005930", "삼성전자", "KOSPI"),
            StockSymbol("000660", "SK하이닉스", "KOSPI"),
            StockSymbol("INVALID", "Invalid Symbol", "KOSPI")
        ]
    
    def test_error_recovery_in_single_stage(self):
        """Test that pipeline continues processing after individual symbol errors."""
        # Create a mock data manager that fails for specific symbols
        mock_data_manager = Mock()
        mock_data_manager.get_availability_status.return_value = {'FinanceDataReader': True}
        
        def mock_get_trading_data(symbol, days):
            if symbol.code == "INVALID":
                raise Exception("Data not available for invalid symbol")
            # Return mock data for valid symbols
            import pandas as pd
            return pd.DataFrame({
                'Close': [100, 101, 102],
                'Volume': [1000000, 1100000, 1200000],
                'TradingValue': [100000000, 111100000, 122400000]
            })
        
        mock_data_manager.get_trading_data = mock_get_trading_data
        
        pipeline = StockFilterPipeline(self.config)
        liquidity_filter = LiquidityFilter(self.config, mock_data_manager)
        pipeline.add_filter(liquidity_filter)
        
        # Should not raise exception despite invalid symbol
        result = pipeline.execute(self.test_symbols)
        
        # Should process all symbols (some may fail but pipeline continues)
        assert result.total_processed == len(self.test_symbols)
        assert len(result.stage_results) == 1
        
        # Invalid symbol should be in failed list
        stage_result = result.stage_results[0]
        failed_codes = [s.code for s in stage_result.failed_symbols]
        assert "INVALID" in failed_codes
    
    def test_error_recovery_between_stages(self):
        """Test error recovery when one stage fails but pipeline continues."""
        mock_data_manager = MockDataAccessManager(self.config)
        pipeline = StockFilterPipeline(self.config)
        
        # Add a filter that will work
        liquidity_filter = LiquidityFilter(self.config, mock_data_manager)
        pipeline.add_filter(liquidity_filter)
        
        # Add a filter that might have issues
        financial_filter = FinancialHealthFilter(self.config, mock_data_manager)
        pipeline.add_filter(financial_filter)
        
        # Execute pipeline - should handle any data issues gracefully
        result = pipeline.execute(self.test_symbols)
        
        # Pipeline should complete even if some symbols fail
        assert isinstance(result, PipelineResult)
        assert result.total_processed == len(self.test_symbols)
        assert len(result.stage_results) == 2
    
    def test_complete_stage_failure_handling(self):
        """Test handling when an entire stage fails."""
        mock_data_manager = Mock()
        mock_data_manager.get_availability_status.return_value = {'FinanceDataReader': False}
        
        pipeline = StockFilterPipeline(self.config)
        
        # Create a filter that will fail due to unavailable data source
        liquidity_filter = LiquidityFilter(self.config, mock_data_manager)
        
        # Mock the filter method to raise an exception
        def failing_filter(symbols):
            raise RuntimeError("Data source unavailable")
        
        liquidity_filter.filter = failing_filter
        pipeline.add_filter(liquidity_filter)
        
        # Pipeline should propagate the error
        with pytest.raises(RuntimeError):
            pipeline.execute(self.test_symbols)


class TestPerformanceWithLargeDatasets:
    """Test pipeline performance with large datasets."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
        self.data_manager = MockDataAccessManager(self.config)
    
    def create_large_symbol_list(self, size: int) -> List[StockSymbol]:
        """Create a large list of test symbols."""
        symbols = []
        for i in range(size):
            code = f"{i:06d}"
            name = f"Test Company {i}"
            market = "KOSPI" if i % 2 == 0 else "KOSDAQ"
            symbols.append(StockSymbol(code, name, market))
        return symbols
    
    def test_performance_with_100_symbols(self):
        """Test pipeline performance with 100 symbols."""
        symbols = self.create_large_symbol_list(100)
        
        pipeline = StockFilterPipeline(self.config)
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        pipeline.add_filter(liquidity_filter)
        
        start_time = time.time()
        result = pipeline.execute(symbols)
        execution_time = time.time() - start_time
        
        # Verify results
        assert result.total_processed == 100
        assert len(result.stage_results) == 1
        
        # Performance check - should complete within reasonable time
        assert execution_time < 30.0  # Should complete within 30 seconds
        assert result.execution_time_seconds > 0
        
        # Log performance for monitoring
        print(f"100 symbols processed in {execution_time:.2f} seconds")
    
    def test_performance_with_500_symbols(self):
        """Test pipeline performance with 500 symbols."""
        symbols = self.create_large_symbol_list(500)
        
        pipeline = StockFilterPipeline(self.config)
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        financial_filter = FinancialHealthFilter(self.config, self.data_manager)
        pipeline.add_filter(liquidity_filter)
        pipeline.add_filter(financial_filter)
        
        start_time = time.time()
        result = pipeline.execute(symbols)
        execution_time = time.time() - start_time
        
        # Verify results
        assert result.total_processed == 500
        assert len(result.stage_results) == 2
        
        # Performance check - should complete within reasonable time
        assert execution_time < 120.0  # Should complete within 2 minutes
        
        # Log performance for monitoring
        print(f"500 symbols processed in {execution_time:.2f} seconds")
    
    @pytest.mark.slow
    def test_performance_with_1000_symbols(self):
        """Test pipeline performance with 1000 symbols (marked as slow test)."""
        symbols = self.create_large_symbol_list(1000)
        
        pipeline = StockFilterPipeline(self.config)
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        financial_filter = FinancialHealthFilter(self.config, self.data_manager)
        quality_filter = QualityGrowthFilter(self.config, self.data_manager)
        
        pipeline.add_filter(liquidity_filter)
        pipeline.add_filter(financial_filter)
        pipeline.add_filter(quality_filter)
        
        start_time = time.time()
        result = pipeline.execute(symbols)
        execution_time = time.time() - start_time
        
        # Verify results
        assert result.total_processed == 1000
        assert len(result.stage_results) == 3
        
        # Performance check - should complete within reasonable time
        assert execution_time < 300.0  # Should complete within 5 minutes
        
        # Log performance for monitoring
        print(f"1000 symbols processed in {execution_time:.2f} seconds")
        print(f"Average time per symbol: {execution_time/1000:.3f} seconds")
    
    def test_memory_efficiency_with_large_datasets(self):
        """Test that pipeline handles large datasets without excessive memory usage."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process a moderately large dataset
        symbols = self.create_large_symbol_list(200)
        
        pipeline = StockFilterPipeline(self.config)
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        pipeline.add_filter(liquidity_filter)
        
        result = pipeline.execute(symbols)
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Verify results
        assert result.total_processed == 200
        
        # Memory check - should not use excessive memory
        assert memory_increase < 100  # Should not increase by more than 100MB
        
        print(f"Memory increase: {memory_increase:.2f} MB for 200 symbols")


class TestDataFlowValidation:
    """Test data flow validation between pipeline stages."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = FilterConfig()
        self.data_manager = MockDataAccessManager(self.config)
        self.test_symbols = [
            StockSymbol("005930", "삼성전자", "KOSPI"),
            StockSymbol("000660", "SK하이닉스", "KOSPI"),
            StockSymbol("035420", "NAVER", "KOSDAQ")
        ]
    
    def test_symbol_consistency_between_stages(self):
        """Test that symbols are consistently handled between stages."""
        pipeline = StockFilterPipeline(self.config)
        
        # Add filters
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        financial_filter = FinancialHealthFilter(self.config, self.data_manager)
        
        pipeline.add_filter(liquidity_filter)
        pipeline.add_filter(financial_filter)
        
        result = pipeline.execute(self.test_symbols)
        
        # Verify symbol consistency
        stage1_result = result.stage_results[0]
        stage2_result = result.stage_results[1]
        
        # All symbols from stage 1 should be accounted for in stage 2
        stage1_all_symbols = set(s.code for s in stage1_result.passed_symbols + stage1_result.failed_symbols)
        stage2_all_symbols = set(s.code for s in stage2_result.passed_symbols + stage2_result.failed_symbols)
        
        # Stage 2 should only process symbols that passed stage 1
        stage1_passed_codes = set(s.code for s in stage1_result.passed_symbols)
        assert stage2_all_symbols.issubset(stage1_passed_codes)
    
    def test_no_symbol_duplication(self):
        """Test that no symbols are duplicated in results."""
        pipeline = StockFilterPipeline(self.config)
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        pipeline.add_filter(liquidity_filter)
        
        result = pipeline.execute(self.test_symbols)
        
        stage_result = result.stage_results[0]
        
        # Check for duplicates in passed symbols
        passed_codes = [s.code for s in stage_result.passed_symbols]
        assert len(passed_codes) == len(set(passed_codes))
        
        # Check for duplicates in failed symbols
        failed_codes = [s.code for s in stage_result.failed_symbols]
        assert len(failed_codes) == len(set(failed_codes))
        
        # Check that no symbol appears in both passed and failed
        passed_set = set(passed_codes)
        failed_set = set(failed_codes)
        assert passed_set.isdisjoint(failed_set)
    
    def test_stage_result_completeness(self):
        """Test that stage results account for all input symbols."""
        pipeline = StockFilterPipeline(self.config)
        liquidity_filter = LiquidityFilter(self.config, self.data_manager)
        financial_filter = FinancialHealthFilter(self.config, self.data_manager)
        
        pipeline.add_filter(liquidity_filter)
        pipeline.add_filter(financial_filter)
        
        result = pipeline.execute(self.test_symbols)
        
        # Check each stage
        for i, stage_result in enumerate(result.stage_results):
            total_symbols = len(stage_result.passed_symbols) + len(stage_result.failed_symbols)
            assert total_symbols == stage_result.total_processed
            
            if i == 0:
                # First stage should process all input symbols
                assert stage_result.total_processed == len(self.test_symbols)
            else:
                # Subsequent stages should process passed symbols from previous stage
                prev_stage = result.stage_results[i-1]
                assert stage_result.total_processed == len(prev_stage.passed_symbols)