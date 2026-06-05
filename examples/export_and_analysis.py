#!/usr/bin/env python3
"""
Export and analysis example for the Financial Stock Filter system.

This example demonstrates how to export filtering results to different
formats and perform basic analysis on the results.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
from auto_financial_filter.filters import LiquidityFilter, FinancialHealthFilter
from auto_financial_filter.utils import DataExporter


def run_filtering_pipeline():
    """Run a sample filtering pipeline and return results."""
    print("Running filtering pipeline...")
    
    # Create configuration
    config = FilterConfig(
        min_trading_volume_krw=8_000_000_000,
        max_debt_ratio_percent=180.0,
        min_revenue_growth_percent=10.0,
        verbose_output=False  # Reduce noise for this example
    )
    
    # Initialize components
    data_manager = MockDataAccessManager(config)
    pipeline = StockFilterPipeline(config)
    
    # Add filters
    pipeline.add_filter(LiquidityFilter(config, data_manager))
    pipeline.add_filter(FinancialHealthFilter(config, data_manager))
    
    # Execute pipeline
    symbols = data_manager.get_all_symbols()
    result = pipeline.execute(symbols)
    
    print(f"  Processed {result.total_processed} stocks")
    print(f"  Final candidates: {len(result.final_candidates)}")
    print(f"  Execution time: {result.execution_time_seconds:.2f}s")
    
    return result


def example_csv_export(result):
    """Example of exporting results to CSV format."""
    print("\n=== CSV Export Example ===")
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = f.name
    
    # Export to CSV
    DataExporter.export_pipeline_result_csv(result, csv_path)
    
    print(f"Exported results to CSV: {csv_path}")
    
    # Show first few lines of the CSV
    print("\nCSV content preview:")
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines[:15]):  # Show first 15 lines
            print(f"  {i+1:2d}: {line.rstrip()}")
        if len(lines) > 15:
            print(f"  ... and {len(lines) - 15} more lines")
    
    # Clean up
    os.unlink(csv_path)
    
    return csv_path


def example_json_export(result):
    """Example of exporting results to JSON format."""
    print("\n=== JSON Export Example ===")
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json_path = f.name
    
    # Export to JSON
    DataExporter.export_pipeline_result_json(result, json_path)
    
    print(f"Exported results to JSON: {json_path}")
    
    # Show JSON structure
    import json
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("\nJSON structure:")
    print(f"  - metadata: {list(data['metadata'].keys())}")
    print(f"  - final_candidates: {len(data['final_candidates'])} items")
    print(f"  - stage_results: {len(data['stage_results'])} stages")
    
    # Show sample final candidate
    if data['final_candidates']:
        sample = data['final_candidates'][0]
        print(f"\nSample final candidate:")
        print(f"  - Code: {sample['code']}")
        print(f"  - Name: {sample['name']}")
        print(f"  - Market: {sample['market']}")
    
    # Clean up
    os.unlink(json_path)
    
    return json_path


def example_excel_export(result):
    """Example of exporting results to Excel format."""
    print("\n=== Excel Export Example ===")
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False) as f:
        excel_path = f.name
    
    try:
        # Export to Excel
        DataExporter.export_pipeline_result_excel(result, excel_path)
        
        print(f"Exported results to Excel: {excel_path}")
        print("Excel file contains multiple sheets:")
        print("  - Summary: Overall statistics")
        print("  - Final Candidates: List of passing stocks")
        print("  - Stage Results: Stage-by-stage breakdown")
        print("  - Stage N Passed: Detailed results for each stage")
        
    except ImportError:
        print("Excel export requires pandas and openpyxl packages")
        print("Falling back to CSV export...")
        csv_fallback = excel_path.replace('.xlsx', '.csv')
        DataExporter.export_pipeline_result_csv(result, csv_fallback)
        print(f"Exported to CSV instead: {csv_fallback}")
        os.unlink(csv_fallback)
    
    # Clean up
    if os.path.exists(excel_path):
        os.unlink(excel_path)
    
    return excel_path


def example_individual_stage_export(result):
    """Example of exporting individual stage results."""
    print("\n=== Individual Stage Export Example ===")
    
    for i, stage_result in enumerate(result.stage_results):
        print(f"\nExporting Stage {i+1}: {stage_result.stage}")
        
        # Create temporary file for this stage
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            stage_csv_path = f.name
        
        # Export stage result
        DataExporter.export_filter_result(stage_result, stage_csv_path, 'csv')
        
        print(f"  Exported to: {stage_csv_path}")
        print(f"  Total processed: {stage_result.total_processed}")
        print(f"  Passed: {len(stage_result.passed_symbols)}")
        print(f"  Failed: {len(stage_result.failed_symbols)}")
        print(f"  Pass rate: {stage_result.pass_rate:.1f}%")
        
        # Show criteria applied
        if stage_result.criteria_applied:
            print("  Criteria applied:")
            for key, value in stage_result.criteria_applied.items():
                print(f"    {key}: {value}")
        
        # Clean up
        os.unlink(stage_csv_path)


def example_symbols_export(result):
    """Example of exporting symbol lists."""
    print("\n=== Symbol Lists Export Example ===")
    
    # Export final candidates
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        candidates_csv = f.name
    
    DataExporter.export_symbols_csv(
        result.final_candidates, 
        candidates_csv, 
        "Final Investment Candidates"
    )
    
    print(f"Exported final candidates to: {candidates_csv}")
    
    # Show content preview
    print("\nFinal candidates preview:")
    with open(candidates_csv, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[:10]:  # Show first 10 lines
            print(f"  {line.rstrip()}")
    
    # Export to JSON as well
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        candidates_json = f.name
    
    DataExporter.export_symbols_json(
        result.final_candidates,
        candidates_json,
        "Final Investment Candidates"
    )
    
    print(f"Also exported to JSON: {candidates_json}")
    
    # Clean up
    os.unlink(candidates_csv)
    os.unlink(candidates_json)


def example_result_analysis(result):
    """Example of analyzing filtering results."""
    print("\n=== Result Analysis Example ===")
    
    # Overall statistics
    print("Overall Statistics:")
    print(f"  Total stocks processed: {result.total_processed:,}")
    print(f"  Final candidates: {len(result.final_candidates):,}")
    print(f"  Overall pass rate: {len(result.final_candidates) / result.total_processed * 100:.2f}%")
    print(f"  Processing time: {result.execution_time_seconds:.2f} seconds")
    print(f"  Average time per stock: {result.execution_time_seconds / result.total_processed:.4f} seconds")
    
    # Stage analysis
    print(f"\nStage Analysis:")
    for i, stage_result in enumerate(result.stage_results):
        print(f"  Stage {i+1}: {stage_result.stage}")
        print(f"    Input: {stage_result.total_processed:,} stocks")
        print(f"    Passed: {len(stage_result.passed_symbols):,} stocks")
        print(f"    Pass rate: {stage_result.pass_rate:.1f}%")
        
        # Calculate filtering effectiveness
        if i == 0:
            filtering_rate = (len(stage_result.failed_symbols) / stage_result.total_processed) * 100
        else:
            prev_stage = result.stage_results[i-1]
            filtering_rate = (len(stage_result.failed_symbols) / len(prev_stage.passed_symbols)) * 100
        
        print(f"    Filtering rate: {filtering_rate:.1f}%")
    
    # Market distribution analysis
    if result.final_candidates:
        print(f"\nMarket Distribution of Final Candidates:")
        kospi_count = sum(1 for s in result.final_candidates if s.market == 'KOSPI')
        kosdaq_count = sum(1 for s in result.final_candidates if s.market == 'KOSDAQ')
        
        print(f"  KOSPI: {kospi_count} stocks ({kospi_count / len(result.final_candidates) * 100:.1f}%)")
        print(f"  KOSDAQ: {kosdaq_count} stocks ({kosdaq_count / len(result.final_candidates) * 100:.1f}%)")
    
    # Filtering funnel analysis
    print(f"\nFiltering Funnel:")
    current_count = result.total_processed
    print(f"  Initial stocks: {current_count:,}")
    
    for i, stage_result in enumerate(result.stage_results):
        passed_count = len(stage_result.passed_symbols)
        reduction = current_count - passed_count
        reduction_pct = (reduction / current_count) * 100 if current_count > 0 else 0
        
        print(f"  After {stage_result.stage}: {passed_count:,} (-{reduction:,}, -{reduction_pct:.1f}%)")
        current_count = passed_count
    
    # Performance metrics
    if result.execution_time_seconds > 0:
        throughput = result.total_processed / result.execution_time_seconds
        print(f"\nPerformance Metrics:")
        print(f"  Throughput: {throughput:.1f} stocks/second")
        print(f"  Time per stage: {result.execution_time_seconds / len(result.stage_results):.2f} seconds")


def main():
    """Run all export and analysis examples."""
    print("Financial Stock Filter - Export and Analysis Examples\n")
    
    # Run filtering pipeline to get sample results
    result = run_filtering_pipeline()
    
    # Export examples
    example_csv_export(result)
    example_json_export(result)
    example_excel_export(result)
    example_individual_stage_export(result)
    example_symbols_export(result)
    
    # Analysis examples
    example_result_analysis(result)
    
    print("\n" + "=" * 60)
    print("Export and analysis examples completed!")
    print("\nKey takeaways:")
    print("- Multiple export formats support different use cases")
    print("- Individual stage results can be exported separately")
    print("- Symbol lists can be exported for further analysis")
    print("- Result analysis provides insights into filtering effectiveness")
    print("- Performance metrics help optimize the filtering process")


if __name__ == "__main__":
    main()