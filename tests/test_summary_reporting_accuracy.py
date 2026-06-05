"""
Property-based tests for summary reporting accuracy.

**Feature: auto-financial-filter, Property 11: Summary Reporting Accuracy**
**Validates: Requirements 4.5**
"""

import pytest
from hypothesis import given, strategies as st
from typing import List

from auto_financial_filter.models.base import StockSymbol, FilterResult
from auto_financial_filter.pipeline import PipelineResult


class MockFilter:
    """Mock filter for testing pipeline results."""
    
    def __init__(self, stage_name: str, pass_rate: float = 0.5):
        self.stage_name = stage_name
        self.pass_rate = pass_rate
    
    def filter(self, symbols: List[StockSymbol]) -> FilterResult:
        """Mock filter that passes a percentage of symbols."""
        # Ensure unique symbols by creating new ones with unique codes
        unique_symbols = []
        seen_codes = set()
        for i, symbol in enumerate(symbols):
            if symbol.code not in seen_codes:
                unique_symbols.append(symbol)
                seen_codes.add(symbol.code)
            else:
                # Create a unique variant
                new_code = f"{symbol.code}_{i}"
                unique_symbols.append(StockSymbol(code=new_code, name=symbol.name, market=symbol.market))
        
        num_passed = int(len(unique_symbols) * self.pass_rate)
        passed_symbols = unique_symbols[:num_passed]
        failed_symbols = unique_symbols[num_passed:]
        
        return FilterResult(
            passed_symbols=passed_symbols,
            failed_symbols=failed_symbols,
            stage=self.stage_name,
            criteria_applied={"mock_criteria": True}
        )


@st.composite
def stock_symbols(draw):
    """Generate valid stock symbols."""
    code = draw(st.text(min_size=3, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'))
    name = draw(st.text(min_size=1, max_size=50, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '))
    market = draw(st.sampled_from(['KOSPI', 'KOSDAQ']))
    
    return StockSymbol(code=code, name=name.strip() or "TestCompany", market=market)


@st.composite
def filter_results(draw):
    """Generate valid filter results."""
    # Generate symbols with unique codes
    num_passed = draw(st.integers(min_value=0, max_value=20))
    num_failed = draw(st.integers(min_value=0, max_value=20))
    
    # Generate unique codes first
    total_symbols = num_passed + num_failed
    if total_symbols == 0:
        unique_passed = []
        unique_failed = []
    else:
        codes = [f"SYM{i:03d}" for i in range(total_symbols)]
        names = [f"Company{i}" for i in range(total_symbols)]
        markets = draw(st.lists(st.sampled_from(['KOSPI', 'KOSDAQ']), min_size=total_symbols, max_size=total_symbols))
        
        symbols = [StockSymbol(code=codes[i], name=names[i], market=markets[i]) for i in range(total_symbols)]
        
        unique_passed = symbols[:num_passed]
        unique_failed = symbols[num_passed:]
    
    stage = draw(st.text(min_size=1, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_'))
    
    return FilterResult(
        passed_symbols=unique_passed,
        failed_symbols=unique_failed,
        stage=stage.strip() or "test_stage",
        criteria_applied={"test_criteria": True}
    )


@given(st.lists(filter_results(), min_size=1, max_size=5))
def test_pipeline_result_summary_accuracy(stage_results: List[FilterResult]):
    """
    **Feature: auto-financial-filter, Property 11: Summary Reporting Accuracy**
    
    For any completed filtering process, the summary report should contain 
    accurate counts matching the actual number of stocks processed and filtered at each stage.
    """
    # Calculate expected values
    total_initial = stage_results[0].total_processed if stage_results else 0
    final_candidates = stage_results[-1].passed_symbols if stage_results else []
    
    # Create pipeline result
    pipeline_result = PipelineResult(
        stage_results=stage_results,
        final_candidates=final_candidates,
        total_processed=total_initial,
        execution_time_seconds=1.0
    )
    
    # Get summary
    summary = pipeline_result.get_summary()
    
    # Verify summary accuracy
    assert summary['total_processed'] == total_initial
    assert summary['final_candidates'] == len(final_candidates)
    assert len(summary['stages']) == len(stage_results)
    
    # Verify each stage summary
    for i, (stage_result, stage_summary) in enumerate(zip(stage_results, summary['stages'])):
        assert stage_summary['stage'] == stage_result.stage
        assert stage_summary['input_count'] == stage_result.total_processed
        assert stage_summary['passed_count'] == len(stage_result.passed_symbols)
        assert stage_summary['failed_count'] == len(stage_result.failed_symbols)
        assert stage_summary['pass_rate'] == stage_result.pass_rate
        assert stage_summary['criteria'] == stage_result.criteria_applied
        
        # Verify counts add up correctly
        assert stage_summary['passed_count'] + stage_summary['failed_count'] == stage_summary['input_count']


@given(st.lists(stock_symbols(), min_size=1, max_size=100))
def test_pipeline_result_final_candidate_count_accuracy(initial_symbols: List[StockSymbol]):
    """
    **Feature: auto-financial-filter, Property 11: Summary Reporting Accuracy**
    
    For any pipeline execution, the final candidate count should match 
    the actual number of symbols that passed all stages.
    """
    # Create mock filters with different pass rates
    filters = [
        MockFilter("stage1", 0.8),
        MockFilter("stage2", 0.6),
        MockFilter("stage3", 0.4)
    ]
    
    # Simulate pipeline execution
    current_symbols = initial_symbols.copy()
    stage_results = []
    
    for filter_mock in filters:
        result = filter_mock.filter(current_symbols)
        stage_results.append(result)
        current_symbols = result.passed_symbols
    
    # Create pipeline result
    pipeline_result = PipelineResult(
        stage_results=stage_results,
        final_candidates=current_symbols,
        total_processed=len(initial_symbols),
        execution_time_seconds=1.0
    )
    
    # Verify final candidate count accuracy
    summary = pipeline_result.get_summary()
    assert summary['final_candidates'] == len(current_symbols)
    assert summary['total_processed'] == len(initial_symbols)
    
    # Verify that final candidates match the last stage's passed symbols
    if stage_results:
        assert len(pipeline_result.final_candidates) == len(stage_results[-1].passed_symbols)


@given(st.integers(min_value=0, max_value=1000))
def test_empty_pipeline_summary_accuracy(total_processed: int):
    """
    **Feature: auto-financial-filter, Property 11: Summary Reporting Accuracy**
    
    For any pipeline with no stages, the summary should accurately reflect zero results.
    """
    pipeline_result = PipelineResult(
        stage_results=[],
        final_candidates=[],
        total_processed=total_processed,
        execution_time_seconds=0.5
    )
    
    summary = pipeline_result.get_summary()
    
    assert summary['total_processed'] == total_processed
    assert summary['final_candidates'] == 0
    assert summary['execution_time_seconds'] == 0.5
    assert len(summary['stages']) == 0


@given(filter_results())
def test_single_stage_summary_accuracy(stage_result: FilterResult):
    """
    **Feature: auto-financial-filter, Property 11: Summary Reporting Accuracy**
    
    For any single-stage pipeline, the summary should accurately reflect 
    the stage's input and output counts.
    """
    pipeline_result = PipelineResult(
        stage_results=[stage_result],
        final_candidates=stage_result.passed_symbols,
        total_processed=stage_result.total_processed,
        execution_time_seconds=2.0
    )
    
    summary = pipeline_result.get_summary()
    
    assert summary['total_processed'] == stage_result.total_processed
    assert summary['final_candidates'] == len(stage_result.passed_symbols)
    assert len(summary['stages']) == 1
    
    stage_summary = summary['stages'][0]
    assert stage_summary['input_count'] == stage_result.total_processed
    assert stage_summary['passed_count'] == len(stage_result.passed_symbols)
    assert stage_summary['failed_count'] == len(stage_result.failed_symbols)