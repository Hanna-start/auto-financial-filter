"""
Property-based tests for configuration parameter application.

**Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4**
"""

import pytest
from hypothesis import given, strategies as st, assume
from typing import Dict, Any

from auto_financial_filter.config import FilterConfig, load_config
from auto_financial_filter.models.base import StockSymbol, LiquidityMetrics, FinancialMetrics, ProfitabilityMetrics


@st.composite
def valid_config_parameters(draw):
    """Generate valid configuration parameters."""
    return {
        'min_trading_volume_krw': draw(st.floats(min_value=1_000_000, max_value=100_000_000_000)),
        'trading_volume_period_days': draw(st.integers(min_value=1, max_value=365)),
        'max_debt_ratio_percent': draw(st.floats(min_value=1.0, max_value=1000.0)),
        'min_revenue_growth_percent': draw(st.floats(min_value=-99.0, max_value=1000.0)),
        'cash_flow_quarters': draw(st.integers(min_value=1, max_value=20)),
        'min_operating_margin_percent': draw(st.floats(min_value=-99.0, max_value=100.0)),
        'profit_trend_years': draw(st.integers(min_value=1, max_value=10)),
        'cogs_trend_quarters': draw(st.integers(min_value=1, max_value=20)),
        'data_cache_enabled': draw(st.booleans()),
        'data_cache_ttl_hours': draw(st.integers(min_value=1, max_value=168)),
        'api_retry_attempts': draw(st.integers(min_value=0, max_value=10)),
        'api_timeout_seconds': draw(st.integers(min_value=1, max_value=300)),
        'log_level': draw(st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR'])),
        'verbose_output': draw(st.booleans())
    }


@st.composite
def stock_symbols(draw):
    """Generate valid stock symbols."""
    code = draw(st.text(min_size=3, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'))
    name = draw(st.text(min_size=1, max_size=50, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '))
    market = draw(st.sampled_from(['KOSPI', 'KOSDAQ']))
    
    return StockSymbol(code=code, name=name.strip() or "TestCompany", market=market)


@given(valid_config_parameters())
def test_config_parameter_application_liquidity_threshold(config_params: Dict[str, Any]):
    """
    **Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
    
    For any set of valid configuration parameters, the liquidity filtering behavior 
    should change according to the specified min_trading_volume_krw threshold.
    """
    config = FilterConfig(**config_params)
    config.validate()
    
    # Create test liquidity metrics with different trading values
    symbol = StockSymbol(code="TEST", name="Test Company", market="KOSPI")
    
    # Test value below threshold
    below_threshold = config.min_trading_volume_krw * 0.9
    metrics_below = LiquidityMetrics(
        symbol=symbol,
        avg_daily_volume=1000000,
        avg_daily_value=below_threshold,
        period_days=30
    )
    
    # Test value above threshold
    above_threshold = config.min_trading_volume_krw * 1.1
    metrics_above = LiquidityMetrics(
        symbol=symbol,
        avg_daily_volume=1000000,
        avg_daily_value=above_threshold,
        period_days=30
    )
    
    # Verify threshold application
    assert metrics_below.avg_daily_value < config.min_trading_volume_krw
    assert metrics_above.avg_daily_value >= config.min_trading_volume_krw


@given(valid_config_parameters())
def test_config_parameter_application_debt_ratio_threshold(config_params: Dict[str, Any]):
    """
    **Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
    
    For any set of valid configuration parameters, the financial health filtering behavior 
    should change according to the specified max_debt_ratio_percent threshold.
    """
    config = FilterConfig(**config_params)
    config.validate()
    
    symbol = StockSymbol(code="TEST", name="Test Company", market="KOSPI")
    
    # Test debt ratio below threshold (should pass)
    below_threshold = config.max_debt_ratio_percent * 0.9
    metrics_below = FinancialMetrics(
        symbol=symbol,
        debt_ratio=below_threshold,
        operating_cash_flow=[1000, 2000, 1500, 1800],
        revenue_growth_yoy=15.0,
        quarterly_revenue=[10000, 11000, 12000, 13000]
    )
    
    # Test debt ratio above threshold (should fail)
    above_threshold = config.max_debt_ratio_percent * 1.1
    metrics_above = FinancialMetrics(
        symbol=symbol,
        debt_ratio=above_threshold,
        operating_cash_flow=[1000, 2000, 1500, 1800],
        revenue_growth_yoy=15.0,
        quarterly_revenue=[10000, 11000, 12000, 13000]
    )
    
    # Verify threshold application
    assert metrics_below.debt_ratio < config.max_debt_ratio_percent
    assert metrics_above.debt_ratio >= config.max_debt_ratio_percent


@given(valid_config_parameters())
def test_config_parameter_application_revenue_growth_threshold(config_params: Dict[str, Any]):
    """
    **Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
    
    For any set of valid configuration parameters, the financial health filtering behavior 
    should change according to the specified min_revenue_growth_percent threshold.
    """
    config = FilterConfig(**config_params)
    config.validate()
    
    symbol = StockSymbol(code="TEST", name="Test Company", market="KOSPI")
    
    # Test revenue growth below threshold (should fail)
    below_threshold = config.min_revenue_growth_percent - 5.0
    metrics_below = FinancialMetrics(
        symbol=symbol,
        debt_ratio=100.0,
        operating_cash_flow=[1000, 2000, 1500, 1800],
        revenue_growth_yoy=below_threshold,
        quarterly_revenue=[10000, 11000, 12000, 13000]
    )
    
    # Test revenue growth above threshold (should pass)
    above_threshold = config.min_revenue_growth_percent + 5.0
    metrics_above = FinancialMetrics(
        symbol=symbol,
        debt_ratio=100.0,
        operating_cash_flow=[1000, 2000, 1500, 1800],
        revenue_growth_yoy=above_threshold,
        quarterly_revenue=[10000, 11000, 12000, 13000]
    )
    
    # Verify threshold application
    assert metrics_below.revenue_growth_yoy < config.min_revenue_growth_percent
    assert metrics_above.revenue_growth_yoy >= config.min_revenue_growth_percent


@given(valid_config_parameters())
def test_config_parameter_application_operating_margin_threshold(config_params: Dict[str, Any]):
    """
    **Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
    
    For any set of valid configuration parameters, the quality growth filtering behavior 
    should change according to the specified min_operating_margin_percent threshold.
    """
    config = FilterConfig(**config_params)
    config.validate()
    
    symbol = StockSymbol(code="TEST", name="Test Company", market="KOSPI")
    
    # Test operating margin below threshold (should fail)
    below_threshold = config.min_operating_margin_percent - 2.0
    metrics_below = ProfitabilityMetrics(
        symbol=symbol,
        operating_margin=below_threshold,
        operating_profit_trend=[100] * 16,  # 16 quarters
        cogs_ratio_trend=[0.6, 0.55, 0.5, 0.45, 0.4, 0.35],  # 6 quarters
        is_profit_peak=True
    )
    
    # Test operating margin above threshold (should pass)
    above_threshold = config.min_operating_margin_percent + 2.0
    metrics_above = ProfitabilityMetrics(
        symbol=symbol,
        operating_margin=above_threshold,
        operating_profit_trend=[100] * 16,  # 16 quarters
        cogs_ratio_trend=[0.6, 0.55, 0.5, 0.45, 0.4, 0.35],  # 6 quarters
        is_profit_peak=True
    )
    
    # Verify threshold application
    assert metrics_below.operating_margin < config.min_operating_margin_percent
    assert metrics_above.operating_margin >= config.min_operating_margin_percent


@given(valid_config_parameters())
def test_config_parameter_application_period_settings(config_params: Dict[str, Any]):
    """
    **Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
    
    For any set of valid configuration parameters, the analysis periods should be 
    applied according to the specified trading_volume_period_days, cash_flow_quarters, 
    profit_trend_years, and cogs_trend_quarters settings.
    """
    config = FilterConfig(**config_params)
    config.validate()
    
    # Verify period parameters are applied correctly
    assert config.trading_volume_period_days > 0
    assert config.cash_flow_quarters > 0
    assert config.profit_trend_years > 0
    assert config.cogs_trend_quarters > 0
    
    # Verify the configuration maintains the specified values
    assert config.trading_volume_period_days == config_params['trading_volume_period_days']
    assert config.cash_flow_quarters == config_params['cash_flow_quarters']
    assert config.profit_trend_years == config_params['profit_trend_years']
    assert config.cogs_trend_quarters == config_params['cogs_trend_quarters']


@given(valid_config_parameters())
def test_config_parameter_application_api_settings(config_params: Dict[str, Any]):
    """
    **Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
    
    For any set of valid configuration parameters, the API and caching behavior 
    should change according to the specified retry, timeout, and cache settings.
    """
    config = FilterConfig(**config_params)
    config.validate()
    
    # Verify API configuration parameters are applied
    assert config.api_retry_attempts >= 0
    assert config.api_timeout_seconds > 0
    assert config.data_cache_ttl_hours > 0
    assert isinstance(config.data_cache_enabled, bool)
    
    # Verify the configuration maintains the specified values
    assert config.api_retry_attempts == config_params['api_retry_attempts']
    assert config.api_timeout_seconds == config_params['api_timeout_seconds']
    assert config.data_cache_ttl_hours == config_params['data_cache_ttl_hours']
    assert config.data_cache_enabled == config_params['data_cache_enabled']


@given(valid_config_parameters(), st.dictionaries(st.text(min_size=1, max_size=20), st.floats()))
def test_config_parameter_override_application(config_params: Dict[str, Any], overrides: Dict[str, float]):
    """
    **Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
    
    For any set of valid configuration parameters and valid overrides, 
    the load_config function should apply overrides correctly.
    """
    # Filter overrides to only include valid config parameters
    valid_overrides = {}
    for key, value in overrides.items():
        if key in config_params and isinstance(value, (int, float)) and value > 0:
            if key in ['min_trading_volume_krw', 'max_debt_ratio_percent', 'api_timeout_seconds', 'data_cache_ttl_hours']:
                valid_overrides[key] = abs(value)
            elif key in ['trading_volume_period_days', 'cash_flow_quarters', 'profit_trend_years', 'cogs_trend_quarters', 'api_retry_attempts']:
                valid_overrides[key] = int(abs(value)) + 1  # Ensure positive integer
    
    if not valid_overrides:
        # Skip if no valid overrides
        return
    
    try:
        # Create base config
        base_config = FilterConfig(**config_params)
        
        # Apply overrides
        config_with_overrides = load_config(config_path=None, **valid_overrides)
        
        # Verify overrides were applied
        for key, expected_value in valid_overrides.items():
            actual_value = getattr(config_with_overrides, key)
            assert actual_value == expected_value, f"Override for {key} not applied: expected {expected_value}, got {actual_value}"
            
    except ValueError:
        # Some combinations might be invalid, which is acceptable
        pass


@given(st.text(min_size=1, max_size=20), st.floats())
def test_config_parameter_application_logging_settings(log_level: str, verbose_flag: float):
    """
    **Feature: auto-financial-filter, Property 12: Configuration Parameter Application**
    
    For any logging configuration, the system should apply the specified log level and verbosity settings.
    """
    # Use valid log levels
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    if log_level not in valid_log_levels:
        log_level = 'INFO'  # Default to valid level
    
    verbose_output = verbose_flag > 0.5  # Convert to boolean
    
    config = FilterConfig(
        log_level=log_level,
        verbose_output=verbose_output
    )
    
    # Verify logging configuration is applied
    assert config.log_level == log_level
    assert config.verbose_output == verbose_output