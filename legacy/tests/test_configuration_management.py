"""
Unit tests for configuration management functionality.

Tests configuration file loading, validation, parameter override mechanisms,
and default value handling.
"""

import pytest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import patch

from auto_financial_filter.config import FilterConfig, load_config


class TestFilterConfig:
    """Test FilterConfig class functionality."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = FilterConfig()
        
        # Test default values
        assert config.min_trading_volume_krw == 10_000_000_000
        assert config.trading_volume_period_days == 30
        assert config.max_debt_ratio_percent == 200.0
        assert config.min_revenue_growth_percent == 10.0
        assert config.cash_flow_quarters == 4
        assert config.min_operating_margin_percent == 10.0
        assert config.profit_trend_years == 4
        assert config.cogs_trend_quarters == 6
        assert config.data_cache_enabled is True
        assert config.data_cache_ttl_hours == 24
        assert config.api_retry_attempts == 3
        assert config.api_timeout_seconds == 30
        assert config.log_level == "INFO"
        assert config.log_file_path is None
        assert config.verbose_output is False
    
    def test_configuration_validation_success(self):
        """Test successful configuration validation."""
        config = FilterConfig()
        # Should not raise any exception
        config.validate()
    
    def test_configuration_validation_failures(self):
        """Test configuration validation with invalid values."""
        # Test negative trading volume
        config = FilterConfig(min_trading_volume_krw=-1000)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "min_trading_volume_krw must be positive" in str(exc_info.value)
        
        # Test zero trading volume period
        config = FilterConfig(trading_volume_period_days=0)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "trading_volume_period_days must be positive" in str(exc_info.value)
        
        # Test negative debt ratio
        config = FilterConfig(max_debt_ratio_percent=-50)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "max_debt_ratio_percent must be positive" in str(exc_info.value)
        
        # Test invalid revenue growth (too low)
        config = FilterConfig(min_revenue_growth_percent=-150)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "min_revenue_growth_percent cannot be less than -100%" in str(exc_info.value)
        
        # Test zero cash flow quarters
        config = FilterConfig(cash_flow_quarters=0)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "cash_flow_quarters must be positive" in str(exc_info.value)
        
        # Test invalid operating margin (too low)
        config = FilterConfig(min_operating_margin_percent=-150)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "min_operating_margin_percent cannot be less than -100%" in str(exc_info.value)
        
        # Test zero profit trend years
        config = FilterConfig(profit_trend_years=0)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "profit_trend_years must be positive" in str(exc_info.value)
        
        # Test zero COGS trend quarters
        config = FilterConfig(cogs_trend_quarters=0)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "cogs_trend_quarters must be positive" in str(exc_info.value)
        
        # Test negative retry attempts
        config = FilterConfig(api_retry_attempts=-1)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "api_retry_attempts cannot be negative" in str(exc_info.value)
        
        # Test zero timeout
        config = FilterConfig(api_timeout_seconds=0)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "api_timeout_seconds must be positive" in str(exc_info.value)
        
        # Test zero cache TTL
        config = FilterConfig(data_cache_ttl_hours=0)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "data_cache_ttl_hours must be positive" in str(exc_info.value)
    
    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are reported together."""
        config = FilterConfig(
            min_trading_volume_krw=-1000,
            trading_volume_period_days=0,
            max_debt_ratio_percent=-50
        )
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        error_message = str(exc_info.value)
        assert "min_trading_volume_krw must be positive" in error_message
        assert "trading_volume_period_days must be positive" in error_message
        assert "max_debt_ratio_percent must be positive" in error_message
    
    def test_to_dict(self):
        """Test configuration conversion to dictionary."""
        config = FilterConfig(
            min_trading_volume_krw=5_000_000_000,
            verbose_output=True
        )
        
        config_dict = config.to_dict()
        
        assert config_dict['min_trading_volume_krw'] == 5_000_000_000
        assert config_dict['verbose_output'] is True
        assert config_dict['trading_volume_period_days'] == 30  # Default value
        assert len(config_dict) == 15  # All configuration parameters


class TestConfigurationFileLoading:
    """Test configuration file loading functionality."""
    
    def test_load_from_yaml_file(self):
        """Test loading configuration from YAML file."""
        config_data = {
            'min_trading_volume_krw': 5_000_000_000,
            'trading_volume_period_days': 60,
            'max_debt_ratio_percent': 150.0,
            'verbose_output': True
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            yaml_path = f.name
        
        try:
            config = FilterConfig.from_file(yaml_path)
            
            assert config.min_trading_volume_krw == 5_000_000_000
            assert config.trading_volume_period_days == 60
            assert config.max_debt_ratio_percent == 150.0
            assert config.verbose_output is True
            # Check that defaults are preserved for unspecified values
            assert config.min_revenue_growth_percent == 10.0
            
        finally:
            Path(yaml_path).unlink()
    
    def test_load_from_json_file(self):
        """Test loading configuration from JSON file."""
        config_data = {
            'min_trading_volume_krw': 8_000_000_000,
            'api_retry_attempts': 5,
            'log_level': 'DEBUG'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            json_path = f.name
        
        try:
            config = FilterConfig.from_file(json_path)
            
            assert config.min_trading_volume_krw == 8_000_000_000
            assert config.api_retry_attempts == 5
            assert config.log_level == 'DEBUG'
            # Check that defaults are preserved
            assert config.trading_volume_period_days == 30
            
        finally:
            Path(json_path).unlink()
    
    def test_load_from_yml_extension(self):
        """Test loading configuration from .yml file."""
        config_data = {
            'min_operating_margin_percent': 15.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            yml_path = f.name
        
        try:
            config = FilterConfig.from_file(yml_path)
            assert config.min_operating_margin_percent == 15.0
            
        finally:
            Path(yml_path).unlink()
    
    def test_file_not_found_error(self):
        """Test error handling when configuration file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            FilterConfig.from_file('nonexistent_config.yaml')
        
        assert "Configuration file not found" in str(exc_info.value)
    
    def test_unsupported_file_format(self):
        """Test error handling for unsupported file formats."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("some text")
            txt_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                FilterConfig.from_file(txt_path)
            
            assert "Unsupported configuration file format" in str(exc_info.value)
            
        finally:
            Path(txt_path).unlink()
    
    def test_invalid_yaml_content(self):
        """Test error handling for invalid YAML content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            yaml_path = f.name
        
        try:
            with pytest.raises(yaml.YAMLError):
                FilterConfig.from_file(yaml_path)
                
        finally:
            Path(yaml_path).unlink()
    
    def test_invalid_json_content(self):
        """Test error handling for invalid JSON content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json content}')
            json_path = f.name
        
        try:
            with pytest.raises(json.JSONDecodeError):
                FilterConfig.from_file(json_path)
                
        finally:
            Path(json_path).unlink()


class TestLoadConfigFunction:
    """Test the load_config function."""
    
    def test_load_config_without_file(self):
        """Test loading configuration without a file (defaults only)."""
        config = load_config()
        
        # Should return default configuration
        assert config.min_trading_volume_krw == 10_000_000_000
        assert config.trading_volume_period_days == 30
        assert config.verbose_output is False
    
    def test_load_config_with_file(self):
        """Test loading configuration with a file."""
        config_data = {
            'min_trading_volume_krw': 15_000_000_000,
            'log_level': 'WARNING'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            yaml_path = f.name
        
        try:
            config = load_config(yaml_path)
            
            assert config.min_trading_volume_krw == 15_000_000_000
            assert config.log_level == 'WARNING'
            # Defaults should be preserved
            assert config.trading_volume_period_days == 30
            
        finally:
            Path(yaml_path).unlink()
    
    def test_load_config_with_overrides(self):
        """Test loading configuration with parameter overrides."""
        config = load_config(
            min_trading_volume_krw=20_000_000_000,
            verbose_output=True,
            api_retry_attempts=10
        )
        
        assert config.min_trading_volume_krw == 20_000_000_000
        assert config.verbose_output is True
        assert config.api_retry_attempts == 10
        # Defaults should be preserved for non-overridden values
        assert config.trading_volume_period_days == 30
    
    def test_load_config_file_and_overrides(self):
        """Test loading configuration with both file and overrides."""
        config_data = {
            'min_trading_volume_krw': 12_000_000_000,
            'trading_volume_period_days': 45,
            'log_level': 'ERROR'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            json_path = f.name
        
        try:
            config = load_config(
                json_path,
                trading_volume_period_days=60,  # Override file value
                verbose_output=True  # New parameter not in file
            )
            
            # File values
            assert config.min_trading_volume_krw == 12_000_000_000
            assert config.log_level == 'ERROR'
            
            # Override values
            assert config.trading_volume_period_days == 60  # Overridden
            assert config.verbose_output is True  # New
            
            # Defaults for unspecified values
            assert config.max_debt_ratio_percent == 200.0
            
        finally:
            Path(json_path).unlink()
    
    def test_load_config_unknown_parameter_override(self):
        """Test error handling for unknown parameter overrides."""
        with pytest.raises(ValueError) as exc_info:
            load_config(unknown_parameter=123)
        
        assert "Unknown configuration parameter: unknown_parameter" in str(exc_info.value)
    
    def test_load_config_invalid_override_values(self):
        """Test validation of override values."""
        with pytest.raises(ValueError) as exc_info:
            load_config(min_trading_volume_krw=-1000)
        
        assert "min_trading_volume_krw must be positive" in str(exc_info.value)
    
    def test_load_config_file_with_invalid_override(self):
        """Test that overrides can fix invalid file values."""
        config_data = {
            'min_trading_volume_krw': -1000  # Invalid value
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            yaml_path = f.name
        
        try:
            # This should succeed because override fixes the invalid value
            config = load_config(
                yaml_path,
                min_trading_volume_krw=5_000_000_000  # Valid override
            )
            
            assert config.min_trading_volume_krw == 5_000_000_000
            
        finally:
            Path(yaml_path).unlink()


class TestConfigurationEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_boundary_values(self):
        """Test configuration with boundary values."""
        config = FilterConfig(
            min_revenue_growth_percent=-99.9,  # Just above -100%
            min_operating_margin_percent=-99.9,  # Just above -100%
            api_retry_attempts=0,  # Minimum valid value
            min_trading_volume_krw=1,  # Minimum positive value
            trading_volume_period_days=1,  # Minimum positive value
            cash_flow_quarters=1,  # Minimum positive value
            profit_trend_years=1,  # Minimum positive value
            cogs_trend_quarters=1,  # Minimum positive value
            api_timeout_seconds=1,  # Minimum positive value
            data_cache_ttl_hours=1  # Minimum positive value
        )
        
        # Should not raise validation errors
        config.validate()
    
    def test_large_values(self):
        """Test configuration with very large values."""
        config = FilterConfig(
            min_trading_volume_krw=1e15,  # Very large volume
            max_debt_ratio_percent=10000.0,  # Very high debt ratio
            api_retry_attempts=1000,  # Many retries
            api_timeout_seconds=3600,  # 1 hour timeout
            data_cache_ttl_hours=8760  # 1 year TTL
        )
        
        # Should not raise validation errors
        config.validate()
    
    def test_empty_configuration_file(self):
        """Test loading from empty configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({}, f)  # Empty configuration
            yaml_path = f.name
        
        try:
            config = FilterConfig.from_file(yaml_path)
            
            # Should use all default values
            assert config.min_trading_volume_krw == 10_000_000_000
            assert config.trading_volume_period_days == 30
            assert config.verbose_output is False
            
        finally:
            Path(yaml_path).unlink()
    
    def test_partial_configuration_file(self):
        """Test loading from file with only some parameters."""
        config_data = {
            'verbose_output': True,
            'log_level': 'DEBUG'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            json_path = f.name
        
        try:
            config = FilterConfig.from_file(json_path)
            
            # Specified values
            assert config.verbose_output is True
            assert config.log_level == 'DEBUG'
            
            # Default values for unspecified parameters
            assert config.min_trading_volume_krw == 10_000_000_000
            assert config.trading_volume_period_days == 30
            assert config.max_debt_ratio_percent == 200.0
            
        finally:
            Path(json_path).unlink()