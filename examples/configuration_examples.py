#!/usr/bin/env python3
"""
Configuration examples for the Financial Stock Filter system.

This example demonstrates different ways to configure the system
for various investment strategies and market conditions.
"""

import sys
import os
import tempfile
import yaml
import json

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_financial_filter.config import FilterConfig, load_config


def example_conservative_strategy():
    """Example configuration for conservative investment strategy."""
    print("=== Conservative Investment Strategy ===")
    
    config = FilterConfig(
        # Higher liquidity requirements for safety
        min_trading_volume_krw=15_000_000_000,  # 15 billion KRW
        trading_volume_period_days=30,
        
        # Stricter financial health criteria
        max_debt_ratio_percent=100.0,           # Lower debt tolerance
        min_revenue_growth_percent=5.0,         # Modest growth requirement
        cash_flow_quarters=4,
        
        # Conservative profitability requirements
        min_operating_margin_percent=15.0,      # Higher margin requirement
        profit_trend_years=4,
        cogs_trend_quarters=6,
        
        # System settings
        verbose_output=True,
        log_level="INFO"
    )
    
    print("Configuration for conservative investors:")
    print(f"  - High liquidity requirement: {config.min_trading_volume_krw:,.0f} KRW")
    print(f"  - Low debt tolerance: {config.max_debt_ratio_percent}%")
    print(f"  - Modest growth requirement: {config.min_revenue_growth_percent}%")
    print(f"  - High profitability requirement: {config.min_operating_margin_percent}%")
    
    return config


def example_growth_strategy():
    """Example configuration for growth investment strategy."""
    print("\n=== Growth Investment Strategy ===")
    
    config = FilterConfig(
        # Moderate liquidity requirements
        min_trading_volume_krw=5_000_000_000,   # 5 billion KRW
        trading_volume_period_days=30,
        
        # Flexible financial health for growth companies
        max_debt_ratio_percent=250.0,           # Higher debt tolerance
        min_revenue_growth_percent=20.0,        # Strong growth requirement
        cash_flow_quarters=4,
        
        # Growth-focused profitability
        min_operating_margin_percent=8.0,       # Lower margin tolerance
        profit_trend_years=4,
        cogs_trend_quarters=6,
        
        # System settings
        verbose_output=True,
        log_level="INFO"
    )
    
    print("Configuration for growth investors:")
    print(f"  - Moderate liquidity requirement: {config.min_trading_volume_krw:,.0f} KRW")
    print(f"  - Higher debt tolerance: {config.max_debt_ratio_percent}%")
    print(f"  - Strong growth requirement: {config.min_revenue_growth_percent}%")
    print(f"  - Flexible profitability: {config.min_operating_margin_percent}%")
    
    return config


def example_value_strategy():
    """Example configuration for value investment strategy."""
    print("\n=== Value Investment Strategy ===")
    
    config = FilterConfig(
        # Lower liquidity requirements for value opportunities
        min_trading_volume_krw=3_000_000_000,   # 3 billion KRW
        trading_volume_period_days=30,
        
        # Strong financial health requirements
        max_debt_ratio_percent=120.0,           # Moderate debt tolerance
        min_revenue_growth_percent=0.0,         # No growth requirement
        cash_flow_quarters=4,
        
        # Value-focused profitability
        min_operating_margin_percent=12.0,      # Good profitability
        profit_trend_years=4,
        cogs_trend_quarters=6,
        
        # System settings
        verbose_output=True,
        log_level="INFO"
    )
    
    print("Configuration for value investors:")
    print(f"  - Lower liquidity requirement: {config.min_trading_volume_krw:,.0f} KRW")
    print(f"  - Moderate debt tolerance: {config.max_debt_ratio_percent}%")
    print(f"  - No growth requirement: {config.min_revenue_growth_percent}%")
    print(f"  - Good profitability requirement: {config.min_operating_margin_percent}%")
    
    return config


def example_yaml_configuration():
    """Example of creating and loading YAML configuration."""
    print("\n=== YAML Configuration Example ===")
    
    # Create a sample YAML configuration
    yaml_config = {
        'min_trading_volume_krw': 12000000000,
        'trading_volume_period_days': 30,
        'max_debt_ratio_percent': 180.0,
        'min_revenue_growth_percent': 12.0,
        'cash_flow_quarters': 4,
        'min_operating_margin_percent': 10.0,
        'profit_trend_years': 4,
        'cogs_trend_quarters': 6,
        'data_cache_enabled': True,
        'data_cache_ttl_hours': 24,
        'api_retry_attempts': 3,
        'api_timeout_seconds': 30,
        'log_level': 'INFO',
        'verbose_output': False
    }
    
    # Write to temporary YAML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(yaml_config, f, default_flow_style=False)
        yaml_path = f.name
    
    print(f"Created YAML configuration file: {yaml_path}")
    print("YAML content:")
    with open(yaml_path, 'r') as f:
        print(f.read())
    
    # Load configuration from YAML
    config = load_config(yaml_path)
    print("Loaded configuration from YAML:")
    print(f"  - Trading volume: {config.min_trading_volume_krw:,.0f} KRW")
    print(f"  - Debt ratio: {config.max_debt_ratio_percent}%")
    print(f"  - Revenue growth: {config.min_revenue_growth_percent}%")
    
    # Clean up
    os.unlink(yaml_path)
    
    return config


def example_json_configuration():
    """Example of creating and loading JSON configuration."""
    print("\n=== JSON Configuration Example ===")
    
    # Create a sample JSON configuration
    json_config = {
        "min_trading_volume_krw": 8000000000,
        "max_debt_ratio_percent": 200.0,
        "min_revenue_growth_percent": 15.0,
        "min_operating_margin_percent": 8.0,
        "verbose_output": True,
        "log_level": "DEBUG"
    }
    
    # Write to temporary JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(json_config, f, indent=2)
        json_path = f.name
    
    print(f"Created JSON configuration file: {json_path}")
    print("JSON content:")
    with open(json_path, 'r') as f:
        print(f.read())
    
    # Load configuration from JSON
    config = load_config(json_path)
    print("Loaded configuration from JSON:")
    print(f"  - Trading volume: {config.min_trading_volume_krw:,.0f} KRW")
    print(f"  - Debt ratio: {config.max_debt_ratio_percent}%")
    print(f"  - Revenue growth: {config.min_revenue_growth_percent}%")
    print(f"  - Verbose output: {config.verbose_output}")
    
    # Clean up
    os.unlink(json_path)
    
    return config


def example_parameter_overrides():
    """Example of using parameter overrides."""
    print("\n=== Parameter Override Example ===")
    
    # Start with default configuration
    base_config = FilterConfig()
    print("Base configuration:")
    print(f"  - Trading volume: {base_config.min_trading_volume_krw:,.0f} KRW")
    print(f"  - Debt ratio: {base_config.max_debt_ratio_percent}%")
    
    # Override specific parameters
    overridden_config = load_config(
        config_path=None,  # No file, use defaults
        min_trading_volume_krw=20_000_000_000,  # Override to 20 billion
        max_debt_ratio_percent=100.0,           # Override to 100%
        verbose_output=True                     # Enable verbose output
    )
    
    print("\nConfiguration with overrides:")
    print(f"  - Trading volume: {overridden_config.min_trading_volume_krw:,.0f} KRW")
    print(f"  - Debt ratio: {overridden_config.max_debt_ratio_percent}%")
    print(f"  - Verbose output: {overridden_config.verbose_output}")
    
    return overridden_config


def example_validation_errors():
    """Example of configuration validation errors."""
    print("\n=== Configuration Validation Example ===")
    
    print("Testing configuration validation...")
    
    # Example 1: Invalid trading volume
    try:
        invalid_config = FilterConfig(min_trading_volume_krw=-1000)
        invalid_config.validate()
    except ValueError as e:
        print(f"✓ Caught expected error for negative trading volume: {e}")
    
    # Example 2: Invalid debt ratio
    try:
        invalid_config = FilterConfig(max_debt_ratio_percent=-50)
        invalid_config.validate()
    except ValueError as e:
        print(f"✓ Caught expected error for negative debt ratio: {e}")
    
    # Example 3: Invalid revenue growth (too low)
    try:
        invalid_config = FilterConfig(min_revenue_growth_percent=-150)
        invalid_config.validate()
    except ValueError as e:
        print(f"✓ Caught expected error for invalid revenue growth: {e}")
    
    # Example 4: Valid configuration
    try:
        valid_config = FilterConfig(
            min_trading_volume_krw=5_000_000_000,
            max_debt_ratio_percent=150.0,
            min_revenue_growth_percent=10.0
        )
        valid_config.validate()
        print("✓ Valid configuration passed validation")
    except ValueError as e:
        print(f"✗ Unexpected validation error: {e}")


def main():
    """Run all configuration examples."""
    print("Financial Stock Filter - Configuration Examples\n")
    
    # Investment strategy examples
    conservative_config = example_conservative_strategy()
    growth_config = example_growth_strategy()
    value_config = example_value_strategy()
    
    # File format examples
    yaml_config = example_yaml_configuration()
    json_config = example_json_configuration()
    
    # Override examples
    override_config = example_parameter_overrides()
    
    # Validation examples
    example_validation_errors()
    
    print("\n" + "=" * 60)
    print("Configuration examples completed!")
    print("\nKey takeaways:")
    print("- Use different configurations for different investment strategies")
    print("- YAML and JSON files provide persistent configuration")
    print("- Parameter overrides allow runtime customization")
    print("- Configuration validation prevents invalid settings")
    print("- Adjust parameters based on market conditions and risk tolerance")


if __name__ == "__main__":
    main()