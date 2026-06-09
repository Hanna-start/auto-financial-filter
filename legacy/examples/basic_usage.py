#!/usr/bin/env python3
"""
Basic usage example for the Financial Stock Filter system.

This example demonstrates the most common usage patterns for filtering
Korean stocks using the three-stage pipeline.
"""

import sys
import os

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_financial_filter.config import FilterConfig
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager
from auto_financial_filter.filters import LiquidityFilter, FinancialHealthFilter, QualityGrowthFilter


def main():
    """Run basic filtering example."""
    print("=== Financial Stock Filter - Basic Usage Example ===\n")
    
    # 1. Create configuration with custom parameters
    print("1. Setting up configuration...")
    config = FilterConfig(
        min_trading_volume_krw=8_000_000_000,  # 8 billion KRW minimum
        max_debt_ratio_percent=180.0,          # 180% max debt ratio
        min_revenue_growth_percent=8.0,        # 8% minimum revenue growth
        min_operating_margin_percent=12.0,     # 12% minimum operating margin
        verbose_output=True
    )
    
    print(f"  - Min trading volume: {config.min_trading_volume_krw:,.0f} KRW")
    print(f"  - Max debt ratio: {config.max_debt_ratio_percent}%")
    print(f"  - Min revenue growth: {config.min_revenue_growth_percent}%")
    print(f"  - Min operating margin: {config.min_operating_margin_percent}%")
    
    # 2. Initialize data access (using mock data for this example)
    print("\n2. Initializing data access...")
    data_manager = MockDataAccessManager(config)
    
    # Check data source availability
    availability = data_manager.get_availability_status()
    print("  Data source availability:")
    for source, available in availability.items():
        status = "✓ Available" if available else "✗ Not available"
        print(f"    {source}: {status}")
    
    # 3. Create and configure the filtering pipeline
    print("\n3. Setting up filtering pipeline...")
    pipeline = StockFilterPipeline(config)
    
    # Add all three filters
    liquidity_filter = LiquidityFilter(config, data_manager)
    financial_filter = FinancialHealthFilter(config, data_manager)
    quality_filter = QualityGrowthFilter(config, data_manager)
    
    pipeline.add_filter(liquidity_filter)
    pipeline.add_filter(financial_filter)
    pipeline.add_filter(quality_filter)
    
    print(f"  Pipeline configured with {pipeline.get_stage_count()} filter stages")
    
    # 4. Load stock symbols
    print("\n4. Loading stock symbols...")
    try:
        symbols = data_manager.get_all_symbols()
        print(f"  Loaded {len(symbols)} stock symbols")
        
        # Show sample symbols
        print("  Sample symbols:")
        for symbol in symbols[:5]:
            print(f"    {symbol.code} - {symbol.name} ({symbol.market})")
        if len(symbols) > 5:
            print(f"    ... and {len(symbols) - 5} more")
            
    except Exception as e:
        print(f"  Error loading symbols: {e}")
        return 1
    
    # 5. Execute the filtering pipeline
    print(f"\n5. Executing filtering pipeline on {len(symbols)} symbols...")
    print("  This may take a moment...\n")
    
    try:
        result = pipeline.execute(symbols)
        
        # 6. Display results
        print("6. Filtering Results:")
        print("=" * 50)
        
        print(f"Total stocks processed: {result.total_processed:,}")
        print(f"Final candidates: {len(result.final_candidates):,}")
        print(f"Overall pass rate: {len(result.final_candidates) / result.total_processed * 100:.1f}%")
        print(f"Execution time: {result.execution_time_seconds:.2f} seconds")
        
        # Stage-by-stage breakdown
        print(f"\nStage-by-stage breakdown:")
        print("-" * 50)
        
        for i, stage_result in enumerate(result.stage_results, 1):
            print(f"Stage {i}: {stage_result.stage}")
            print(f"  Input: {stage_result.total_processed:,} stocks")
            print(f"  Passed: {len(stage_result.passed_symbols):,} stocks")
            print(f"  Failed: {len(stage_result.failed_symbols):,} stocks")
            print(f"  Pass rate: {stage_result.pass_rate:.1f}%")
            
            # Show criteria applied
            if stage_result.criteria_applied:
                print("  Criteria applied:")
                for key, value in stage_result.criteria_applied.items():
                    if isinstance(value, float) and 'krw' in key.lower():
                        print(f"    {key}: {value:,.0f}")
                    else:
                        print(f"    {key}: {value}")
            print()
        
        # Show final candidates
        if result.final_candidates:
            print("Final candidate stocks:")
            print("-" * 30)
            for symbol in result.final_candidates[:10]:  # Show first 10
                print(f"  {symbol.code} - {symbol.name} ({symbol.market})")
            
            if len(result.final_candidates) > 10:
                print(f"  ... and {len(result.final_candidates) - 10} more")
        else:
            print("No stocks passed all filtering criteria.")
        
        print("\n" + "=" * 50)
        print("Filtering completed successfully!")
        
        return 0
        
    except Exception as e:
        print(f"Error during pipeline execution: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())