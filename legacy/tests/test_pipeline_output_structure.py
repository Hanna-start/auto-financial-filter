"""
Property-based tests for pipeline output structure.

**Feature: auto-financial-filter, Property 4: Pipeline Output Structure**
**Validates: Requirements 1.4, 2.5, 3.5**
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any

from auto_financial_filter.models.base import StockSymbol, FilterResult


class TestPipelineOutputStructure:
    """Test pipeline output structure property."""
    
    @given(
        passed_symbols=st.lists(
            st.builds(
                StockSymbol,
                code=st.text(min_size=1, max_size=6, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789').filter(lambda x: x.strip()),
                name=st.text(min_size=2, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ').filter(lambda x: x.strip()),
                market=st.sampled_from(['KOSPI', 'KOSDAQ'])
            ),
            min_size=0,
            max_size=5,
            unique_by=lambda x: x.code
        ),
        failed_symbols=st.lists(
            st.builds(
                StockSymbol,
                code=st.text(min_size=1, max_size=6, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789').filter(lambda x: x.strip()),
                name=st.text(min_size=2, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ').filter(lambda x: x.strip()),
                market=st.sampled_from(['KOSPI', 'KOSDAQ'])
            ),
            min_size=0,
            max_size=5,
            unique_by=lambda x: x.code
        ),
        stage=st.text(min_size=1, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ_').filter(lambda x: x.strip()),
        criteria_applied=st.dictionaries(
            keys=st.text(min_size=1, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ').filter(lambda x: x.strip()),
            values=st.one_of(st.floats(min_value=-1000, max_value=1000), st.integers(min_value=-100, max_value=100)),
            min_size=0,
            max_size=3
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_pipeline_output_structure_property(self, passed_symbols: List[StockSymbol], 
                                              failed_symbols: List[StockSymbol], 
                                              stage: str, 
                                              criteria_applied: Dict[str, Any]):
        """
        **Feature: auto-financial-filter, Property 4: Pipeline Output Structure**
        
        Property: For any completed filtering stage, the output should be a properly named 
        list containing only valid stock codes that passed all criteria for that stage.
        
        **Validates: Requirements 1.4, 2.5, 3.5**
        """
        # Ensure no overlap between passed and failed symbols
        passed_codes = {symbol.code for symbol in passed_symbols}
        failed_codes = {symbol.code for symbol in failed_symbols}
        
        # Remove any overlapping symbols from failed list to ensure valid input
        filtered_failed_symbols = [symbol for symbol in failed_symbols if symbol.code not in passed_codes]
        
        # Create filter result
        filter_result = FilterResult(
            passed_symbols=passed_symbols,
            failed_symbols=filtered_failed_symbols,
            stage=stage,
            criteria_applied=criteria_applied
        )
        
        # Property 1: Output should be a properly structured FilterResult
        assert isinstance(filter_result, FilterResult), "Output must be a FilterResult instance"
        
        # Property 2: Should contain properly named lists
        assert hasattr(filter_result, 'passed_symbols'), "Must have passed_symbols attribute"
        assert hasattr(filter_result, 'failed_symbols'), "Must have failed_symbols attribute"
        assert isinstance(filter_result.passed_symbols, list), "passed_symbols must be a list"
        assert isinstance(filter_result.failed_symbols, list), "failed_symbols must be a list"
        
        # Property 3: Should contain only valid stock codes
        for symbol in filter_result.passed_symbols:
            assert isinstance(symbol, StockSymbol), "All passed symbols must be StockSymbol instances"
            assert symbol.is_valid(), f"Passed symbol must be valid: {symbol}"
            assert symbol.code.strip() != "", "Stock code cannot be empty"
            
        for symbol in filter_result.failed_symbols:
            assert isinstance(symbol, StockSymbol), "All failed symbols must be StockSymbol instances"
            assert symbol.is_valid(), f"Failed symbol must be valid: {symbol}"
            assert symbol.code.strip() != "", "Stock code cannot be empty"
        
        # Property 4: No symbol should appear in both passed and failed lists
        passed_codes_final = {symbol.code for symbol in filter_result.passed_symbols}
        failed_codes_final = {symbol.code for symbol in filter_result.failed_symbols}
        overlap = passed_codes_final.intersection(failed_codes_final)
        assert len(overlap) == 0, f"No symbol should appear in both lists: {overlap}"
        
        # Property 5: Stage name should be properly set
        assert filter_result.stage == stage, "Stage name should match input"
        assert filter_result.stage.strip() != "", "Stage name cannot be empty"
        
        # Property 6: Criteria applied should be preserved
        assert filter_result.criteria_applied == criteria_applied, "Criteria should be preserved"
        
        # Property 7: Total processed should equal sum of passed and failed
        expected_total = len(filter_result.passed_symbols) + len(filter_result.failed_symbols)
        assert filter_result.total_processed == expected_total, "Total processed should equal sum of passed and failed"
        
        # Property 8: Pass rate should be calculated correctly
        if filter_result.total_processed > 0:
            expected_pass_rate = len(filter_result.passed_symbols) / filter_result.total_processed * 100
            assert abs(filter_result.pass_rate - expected_pass_rate) < 0.001, "Pass rate calculation should be accurate"
        else:
            assert filter_result.pass_rate == 0.0, "Pass rate should be 0 when no symbols processed"
    
    def test_specific_stage_names(self):
        """Test that specific stage names produce valid outputs."""
        stage_names = ["filtered_symbols_step1", "filtered_symbols_step2", "final_candidate_list"]
        
        for stage_name in stage_names:
            # Create a simple filter result
            symbol = StockSymbol(code="TEST001", name="Test Company", market="KOSPI")
            filter_result = FilterResult(
                passed_symbols=[symbol],
                failed_symbols=[],
                stage=stage_name,
                criteria_applied={"test_criteria": "test_value"}
            )
            
            # Verify the structure is valid
            assert filter_result.is_valid(), f"Filter result should be valid for stage: {stage_name}"
            assert filter_result.stage == stage_name, f"Stage name should be preserved: {stage_name}"
            assert len(filter_result.passed_symbols) == 1, "Should have one passed symbol"
            assert filter_result.passed_symbols[0].code == "TEST001", "Symbol code should be preserved"
    
    def test_empty_results_valid(self):
        """Test that empty results are still valid structures."""
        filter_result = FilterResult(
            passed_symbols=[],
            failed_symbols=[],
            stage="empty_test",
            criteria_applied={}
        )
        
        assert filter_result.is_valid(), "Empty filter result should be valid"
        assert filter_result.total_processed == 0, "Total processed should be 0"
        assert filter_result.pass_rate == 0.0, "Pass rate should be 0 for empty result"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])