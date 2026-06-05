"""Command-line interface for the financial stock filter system."""

import argparse
import sys
import json
import csv
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime

from .config import load_config, FilterConfig
from .pipeline import StockFilterPipeline, PipelineResult
from .models.base import StockSymbol
from .data_access.adapters import DataAccessManager
from .filters.liquidity_filter import LiquidityFilter


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="재무 건전성 기반 종목 필터링 시스템 (Financial Stock Filter)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m auto_financial_filter --config config.yaml
  python -m auto_financial_filter --min-volume 5000000000 --verbose
  python -m auto_financial_filter --debt-ratio 150 --margin 15
        """
    )
    
    # Configuration file
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to configuration file (YAML or JSON)'
    )
    
    # Liquidity filter parameters
    parser.add_argument(
        '--min-volume',
        type=float,
        help='Minimum daily average trading volume in KRW'
    )
    
    parser.add_argument(
        '--volume-days',
        type=int,
        help='Number of days for trading volume average calculation'
    )
    
    # Financial health parameters
    parser.add_argument(
        '--debt-ratio',
        type=float,
        help='Maximum debt ratio percentage'
    )
    
    parser.add_argument(
        '--revenue-growth',
        type=float,
        help='Minimum revenue growth percentage (YoY)'
    )
    
    # Quality growth parameters
    parser.add_argument(
        '--margin',
        type=float,
        help='Minimum operating margin percentage'
    )
    
    # Output options
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path for results'
    )
    
    parser.add_argument(
        '--format',
        choices=['csv', 'json', 'excel'],
        default='csv',
        help='Output format (default: csv)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        help='Path to log file'
    )
    
    return parser


def format_output(result: PipelineResult, format_type: str = 'csv') -> str:
    """
    Format pipeline results for output.
    
    Args:
        result: Pipeline execution result
        format_type: Output format ('csv', 'json', 'excel')
        
    Returns:
        Formatted output string
    """
    if format_type == 'json':
        return json.dumps(result.get_summary(), indent=2, ensure_ascii=False)
    
    elif format_type == 'csv':
        output_lines = []
        
        # Header
        output_lines.append("# Financial Stock Filter Results")
        output_lines.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"# Total processed: {result.total_processed}")
        output_lines.append(f"# Final candidates: {len(result.final_candidates)}")
        output_lines.append(f"# Execution time: {result.execution_time_seconds:.2f}s")
        output_lines.append("")
        
        # Final candidates
        output_lines.append("# Final Candidate Stocks")
        output_lines.append("Code,Name,Market")
        for symbol in result.final_candidates:
            output_lines.append(f"{symbol.code},{symbol.name},{symbol.market}")
        
        output_lines.append("")
        
        # Stage summary
        output_lines.append("# Stage Summary")
        output_lines.append("Stage,Input_Count,Passed_Count,Failed_Count,Pass_Rate")
        for stage_result in result.stage_results:
            output_lines.append(
                f"{stage_result.stage},"
                f"{stage_result.total_processed},"
                f"{len(stage_result.passed_symbols)},"
                f"{len(stage_result.failed_symbols)},"
                f"{stage_result.pass_rate:.1f}%"
            )
        
        return "\n".join(output_lines)
    
    else:  # excel format
        # For Excel, we'll return CSV format with a note
        csv_output = format_output(result, 'csv')
        return f"# Excel format requested - save this CSV output with .xlsx extension\n{csv_output}"


def save_output(result: PipelineResult, output_path: str, format_type: str) -> None:
    """
    Save pipeline results to file.
    
    Args:
        result: Pipeline execution result
        output_path: Output file path
        format_type: Output format
    """
    output_content = format_output(result, format_type)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_content)
    
    print(f"Results saved to: {output_path}")


def print_summary_report(result: PipelineResult) -> None:
    """
    Print a summary report of the pipeline execution.
    
    Args:
        result: Pipeline execution result
    """
    print("\n" + "=" * 60)
    print("FILTERING SUMMARY REPORT")
    print("=" * 60)
    
    print(f"Total stocks processed: {result.total_processed:,}")
    print(f"Final candidates: {len(result.final_candidates):,}")
    print(f"Overall pass rate: {(len(result.final_candidates) / result.total_processed * 100):.1f}%")
    print(f"Execution time: {result.execution_time_seconds:.2f} seconds")
    
    print("\nStage-by-stage breakdown:")
    print("-" * 60)
    
    for i, stage_result in enumerate(result.stage_results, 1):
        print(f"Stage {i}: {stage_result.stage}")
        print(f"  Input: {stage_result.total_processed:,} stocks")
        print(f"  Passed: {len(stage_result.passed_symbols):,} stocks")
        print(f"  Failed: {len(stage_result.failed_symbols):,} stocks")
        print(f"  Pass rate: {stage_result.pass_rate:.1f}%")
        
        if stage_result.criteria_applied:
            print("  Criteria applied:")
            for key, value in stage_result.criteria_applied.items():
                if isinstance(value, float):
                    if 'krw' in key.lower():
                        print(f"    {key}: {value:,.0f}")
                    else:
                        print(f"    {key}: {value:.1f}")
                else:
                    print(f"    {key}: {value}")
        print()
    
    if result.final_candidates:
        print("Final candidate stocks:")
        print("-" * 30)
        for symbol in result.final_candidates[:10]:  # Show first 10
            print(f"  {symbol.code} - {symbol.name} ({symbol.market})")
        
        if len(result.final_candidates) > 10:
            print(f"  ... and {len(result.final_candidates) - 10} more")
    
    print("=" * 60)


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        # Load configuration
        config_overrides = {}
        
        if args.min_volume is not None:
            config_overrides['min_trading_volume_krw'] = args.min_volume
        
        if args.volume_days is not None:
            config_overrides['trading_volume_period_days'] = args.volume_days
        
        if args.debt_ratio is not None:
            config_overrides['max_debt_ratio_percent'] = args.debt_ratio
        
        if args.revenue_growth is not None:
            config_overrides['min_revenue_growth_percent'] = args.revenue_growth
        
        if args.margin is not None:
            config_overrides['min_operating_margin_percent'] = args.margin
        
        if args.verbose:
            config_overrides['verbose_output'] = True
            config_overrides['log_level'] = 'DEBUG'
        
        if args.log_file:
            config_overrides['log_file_path'] = args.log_file
        
        config = load_config(args.config, **config_overrides)
        
        print("재무 건전성 기반 종목 필터링 시스템")
        print("Financial Stock Filter System")
        print("=" * 50)
        
        if args.verbose:
            print(f"Configuration loaded: {len(config_overrides)} overrides applied")
            print("Configuration parameters:")
            config_dict = config.to_dict()
            for key, value in config_dict.items():
                if isinstance(value, float) and 'krw' in key.lower():
                    print(f"  {key}: {value:,.0f}")
                else:
                    print(f"  {key}: {value}")
            print()
        
        # Initialize data access manager
        print("Initializing data sources...")
        data_manager = DataAccessManager(config)
        
        # Check data source availability
        availability = data_manager.get_availability_status()
        if args.verbose:
            print("Data source availability:")
            for source, available in availability.items():
                status = "✓ Available" if available else "✗ Not available"
                print(f"  {source}: {status}")
            print()
        
        # Create and configure pipeline
        pipeline = StockFilterPipeline(config)
        
        # Add available filters to pipeline
        # Note: Only adding liquidity filter for now as other filters are not yet implemented
        if availability.get('FinanceDataReader', False):
            liquidity_filter = LiquidityFilter(config, data_manager)
            pipeline.add_filter(liquidity_filter)
            print("✓ Added liquidity filter")
        else:
            print("⚠ Liquidity filter not available (FinanceDataReader required)")
        
        if pipeline.get_stage_count() == 0:
            print("Error: No filters available. Please check data source configuration.")
            return 1
        
        print(f"Pipeline configured with {pipeline.get_stage_count()} filter stage(s)")
        print()
        
        # Load initial stock symbols
        print("Loading stock symbols...")
        try:
            initial_symbols = data_manager.get_all_symbols()
            print(f"Loaded {len(initial_symbols):,} stock symbols")
            
            if args.verbose:
                kospi_count = sum(1 for s in initial_symbols if s.market == 'KOSPI')
                kosdaq_count = sum(1 for s in initial_symbols if s.market == 'KOSDAQ')
                print(f"  KOSPI: {kospi_count:,} symbols")
                print(f"  KOSDAQ: {kosdaq_count:,} symbols")
            print()
            
        except Exception as e:
            print(f"Error loading stock symbols: {e}")
            return 1
        
        # Execute pipeline
        print("Starting filtering pipeline...")
        try:
            result = pipeline.execute(initial_symbols)
            
            # Print summary report
            print_summary_report(result)
            
            # Save output if requested
            if args.output:
                save_output(result, args.output, args.format)
            
            return 0
            
        except Exception as e:
            print(f"Error during pipeline execution: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
        
    except ValueError as e:
        print(f"Configuration error: {str(e)}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())