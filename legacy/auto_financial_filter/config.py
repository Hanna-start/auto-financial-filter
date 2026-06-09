"""Configuration management for the financial stock filter system."""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import yaml
import json
from pathlib import Path


@dataclass
class FilterConfig:
    """Configuration parameters for the stock filtering pipeline."""
    
    # Liquidity filter parameters
    min_trading_volume_krw: float = 10_000_000_000  # 10 billion KRW
    trading_volume_period_days: int = 30
    
    # Financial health filter parameters
    max_debt_ratio_percent: float = 200.0
    min_revenue_growth_percent: float = 10.0
    cash_flow_quarters: int = 4
    
    # Quality growth filter parameters
    min_operating_margin_percent: float = 10.0
    profit_trend_years: int = 4
    cogs_trend_quarters: int = 6
    
    # Data source configuration
    data_cache_enabled: bool = True
    data_cache_ttl_hours: int = 24
    api_retry_attempts: int = 3
    api_timeout_seconds: int = 30
    
    # Logging configuration
    log_level: str = "INFO"
    log_file_path: Optional[str] = None
    verbose_output: bool = False

    def validate(self) -> None:
        """Validate configuration parameters."""
        errors = []
        
        if self.min_trading_volume_krw <= 0:
            errors.append("min_trading_volume_krw must be positive")
        
        if self.trading_volume_period_days <= 0:
            errors.append("trading_volume_period_days must be positive")
        
        if self.max_debt_ratio_percent <= 0:
            errors.append("max_debt_ratio_percent must be positive")
        
        if self.min_revenue_growth_percent < -100:
            errors.append("min_revenue_growth_percent cannot be less than -100%")
        
        if self.cash_flow_quarters <= 0:
            errors.append("cash_flow_quarters must be positive")
        
        if self.min_operating_margin_percent < -100:
            errors.append("min_operating_margin_percent cannot be less than -100%")
        
        if self.profit_trend_years <= 0:
            errors.append("profit_trend_years must be positive")
        
        if self.cogs_trend_quarters <= 0:
            errors.append("cogs_trend_quarters must be positive")
        
        if self.api_retry_attempts < 0:
            errors.append("api_retry_attempts cannot be negative")
        
        if self.api_timeout_seconds <= 0:
            errors.append("api_timeout_seconds must be positive")
        
        if self.data_cache_ttl_hours <= 0:
            errors.append("data_cache_ttl_hours must be positive")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

    @classmethod
    def from_file(cls, config_path: str) -> 'FilterConfig':
        """Load configuration from a file (JSON or YAML)."""
        path = Path(config_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            if path.suffix.lower() in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif path.suffix.lower() == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {path.suffix}")
        
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'min_trading_volume_krw': self.min_trading_volume_krw,
            'trading_volume_period_days': self.trading_volume_period_days,
            'max_debt_ratio_percent': self.max_debt_ratio_percent,
            'min_revenue_growth_percent': self.min_revenue_growth_percent,
            'cash_flow_quarters': self.cash_flow_quarters,
            'min_operating_margin_percent': self.min_operating_margin_percent,
            'profit_trend_years': self.profit_trend_years,
            'cogs_trend_quarters': self.cogs_trend_quarters,
            'data_cache_enabled': self.data_cache_enabled,
            'data_cache_ttl_hours': self.data_cache_ttl_hours,
            'api_retry_attempts': self.api_retry_attempts,
            'api_timeout_seconds': self.api_timeout_seconds,
            'log_level': self.log_level,
            'log_file_path': self.log_file_path,
            'verbose_output': self.verbose_output
        }


def load_config(config_path: Optional[str] = None, **overrides) -> FilterConfig:
    """
    Load configuration with optional file and parameter overrides.
    
    Args:
        config_path: Path to configuration file (optional)
        **overrides: Parameter overrides
    
    Returns:
        FilterConfig instance
    """
    if config_path:
        config = FilterConfig.from_file(config_path)
    else:
        config = FilterConfig()
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            raise ValueError(f"Unknown configuration parameter: {key}")
    
    config.validate()
    return config