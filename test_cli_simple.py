#!/usr/bin/env python3
"""Simple CLI test to verify functionality."""

import sys
import os
sys.path.insert(0, os.getcwd())

from auto_financial_filter.cli import create_parser, format_output
from auto_financial_filter.pipeline import PipelineResult
from auto_financial_filter.models.base import FilterResult
from auto_financial_filter.models.base import StockSymbol

def test_cli_basic():
    """Test basic CLI functionality."""
    # Test parser creation
    parser = create_parser()
    assert "Financial Stock Filter" in parser.description
    print("✓ Parser creation test passed")
    
    # Test argument parsing
    args = parser.parse_args(['--config', 'test.yaml', '--verbose'])
    assert args.config == 'test.yaml'
    assert args.verbose is True
    print("✓ Argument parsing test passed")
    
    # Test output formatting
    sample_symbols = [StockSymbol("005930", "삼성전자", "KOSPI")]
    stage_results = [
        FilterResult(
            stage="Test Filter",
            passed_symbols=sample_symbols,
            failed_symbols=[],
            criteria_applied={"test": "value"}
        )
    ]
    
    result = PipelineResult(
        total_processed=100,
        final_candidates=sample_symbols,
        stage_results=stage_results,
        execution_time_seconds=1.0
    )
    
    csv_output = format_output(result, 'csv')
    assert "# Financial Stock Filter Results" in csv_output
    assert "005930,삼성전자,KOSPI" in csv_output
    print("✓ Output formatting test passed")
    
    print("All CLI tests passed successfully!")

if __name__ == "__main__":
    test_cli_basic()