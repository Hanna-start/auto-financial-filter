# API Reference

This document provides comprehensive API documentation for the Financial Stock Filter system.

## Table of Contents

- [Core Classes](#core-classes)
- [Configuration](#configuration)
- [Pipeline](#pipeline)
- [Filters](#filters)
- [Data Access](#data-access)
- [Utilities](#utilities)
- [Models](#models)

## Core Classes

### FilterConfig

Configuration class for the stock filtering pipeline.

```python
from auto_financial_filter.config import FilterConfig

config = FilterConfig(
    min_trading_volume_krw=10_000_000_000,
    max_debt_ratio_percent=200.0,
    min_revenue_growth_percent=10.0,
    verbose_output=True
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_trading_volume_krw` | float | 10,000,000,000 | Minimum daily average trading volume in KRW |
| `trading_volume_period_days` | int | 30 | Number of days for volume calculation |
| `max_debt_ratio_percent` | float | 200.0 | Maximum debt-to-equity ratio percentage |
| `min_revenue_growth_percent` | float | 10.0 | Minimum year-over-year revenue growth |
| `cash_flow_quarters` | int | 4 | Number of quarters for cash flow analysis |
| `min_operating_margin_percent` | float | 10.0 | Minimum operating margin percentage |
| `profit_trend_years` | int | 4 | Years of profit trend analysis |
| `cogs_trend_quarters` | int | 6 | Quarters for COGS trend analysis |
| `data_cache_enabled` | bool | True | Enable data caching |
| `data_cache_ttl_hours` | int | 24 | Cache time-to-live in hours |
| `api_retry_attempts` | int | 3 | Number of API retry attempts |
| `api_timeout_seconds` | int | 30 | API timeout in seconds |
| `log_level` | str | "INFO" | Logging level |
| `log_file_path` | str | None | Path to log file (optional) |
| `verbose_output` | bool | False | Enable verbose console output |

#### Methods

- `validate()`: Validate configuration parameters
- `to_dict()`: Convert configuration to dictionary
- `from_file(config_path)`: Load configuration from file (class method)

### StockFilterPipeline

Main orchestrator for the filtering pipeline.

```python
from auto_financial_filter.pipeline import StockFilterPipeline
from auto_financial_filter.config import FilterConfig

config = FilterConfig()
pipeline = StockFilterPipeline(config)
```

#### Methods

- `add_filter(filter_instance)`: Add a filter to the pipeline
- `execute(symbols)`: Execute the pipeline on a list of symbols
- `get_stage_count()`: Get the number of configured filter stages

#### Example Usage

```python
from auto_financial_filter.filters import LiquidityFilter, FinancialHealthFilter

# Add filters to pipeline
pipeline.add_filter(LiquidityFilter(config, data_manager))
pipeline.add_filter(FinancialHealthFilter(config, data_manager))

# Execute pipeline
result = pipeline.execute(symbols)
```

## Configuration

### load_config()

Load configuration with optional file and parameter overrides.

```python
from auto_financial_filter.config import load_config

# Load from file
config = load_config('config.yaml')

# Load with overrides
config = load_config(
    'config.yaml',
    min_trading_volume_krw=5_000_000_000,
    verbose_output=True
)

# Load defaults with overrides
config = load_config(
    config_path=None,
    max_debt_ratio_percent=150.0
)
```

#### Parameters

- `config_path` (str, optional): Path to configuration file
- `**overrides`: Parameter overrides as keyword arguments

#### Returns

- `FilterConfig`: Configured FilterConfig instance

## Pipeline

### PipelineResult

Result object returned by pipeline execution.

#### Attributes

- `total_processed` (int): Total number of symbols processed
- `final_candidates` (List[StockSymbol]): Final candidate symbols
- `stage_results` (List[FilterResult]): Results from each stage
- `execution_time_seconds` (float): Total execution time

#### Methods

- `get_summary()`: Get a summary dictionary of the pipeline execution

## Filters

### LiquidityFilter

First stage filter that evaluates stocks based on liquidity criteria.

```python
from auto_financial_filter.filters import LiquidityFilter

liquidity_filter = LiquidityFilter(config, data_manager)
result = liquidity_filter.filter(symbols)
```

#### Configuration Parameters Used

- `min_trading_volume_krw`
- `trading_volume_period_days`

### FinancialHealthFilter

Second stage filter that evaluates financial health metrics.

```python
from auto_financial_filter.filters import FinancialHealthFilter

financial_filter = FinancialHealthFilter(config, data_manager)
result = financial_filter.filter(symbols)
```

#### Configuration Parameters Used

- `max_debt_ratio_percent`
- `min_revenue_growth_percent`
- `cash_flow_quarters`

### QualityGrowthFilter

Third stage filter that analyzes profitability and growth trends.

```python
from auto_financial_filter.filters import QualityGrowthFilter

quality_filter = QualityGrowthFilter(config, data_manager)
result = quality_filter.filter(symbols)
```

#### Configuration Parameters Used

- `min_operating_margin_percent`
- `profit_trend_years`
- `cogs_trend_quarters`

### BaseFilter (Abstract)

Abstract base class for all filters.

#### Abstract Methods

- `filter(symbols)`: Apply the filter to a list of symbols
- `get_stage_name()`: Get the name of this filtering stage

## Data Access

### DataAccessManager

Manager class for coordinating multiple data source adapters.

```python
from auto_financial_filter.data_access.adapters import DataAccessManager

data_manager = DataAccessManager(config)
```

#### Methods

- `get_all_symbols()`: Get all stock symbols from both markets
- `get_trading_data(symbol, days)`: Get trading data for a symbol
- `get_financial_data(symbol, quarters)`: Get financial data for a symbol
- `get_market_data(symbol)`: Get market data for a symbol
- `get_availability_status()`: Get availability status of all data sources
- `get_retry_counts()`: Get retry counts for all adapters

### MockDataAccessManager

Mock data access manager for testing and development.

```python
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager

mock_data_manager = MockDataAccessManager(config)
```

Provides the same interface as `DataAccessManager` but with mock data.

## Utilities

### DataCache

File-based data cache with TTL support.

```python
from auto_financial_filter.utils import DataCache

cache = DataCache(cache_dir=".cache", ttl_hours=24)

# Store data
cache.set("key", data)

# Retrieve data
data = cache.get("key")

# Clear cache
cache.clear()
```

#### Methods

- `get(key)`: Retrieve data from cache
- `set(key, data)`: Store data in cache
- `delete(key)`: Delete cached data
- `clear()`: Clear all cached data
- `cleanup_expired()`: Remove expired cache files
- `get_cache_info()`: Get cache statistics

### DataExporter

Utility class for exporting data to various formats.

```python
from auto_financial_filter.utils import DataExporter

# Export pipeline results
DataExporter.export_pipeline_result_csv(result, "results.csv")
DataExporter.export_pipeline_result_json(result, "results.json")
DataExporter.export_pipeline_result_excel(result, "results.xlsx")

# Export symbol lists
DataExporter.export_symbols_csv(symbols, "symbols.csv", "Stock List")
DataExporter.export_symbols_json(symbols, "symbols.json", "Stock List")
```

#### Methods

- `export_pipeline_result_csv(result, output_path)`: Export pipeline result to CSV
- `export_pipeline_result_json(result, output_path)`: Export pipeline result to JSON
- `export_pipeline_result_excel(result, output_path)`: Export pipeline result to Excel
- `export_symbols_csv(symbols, output_path, title)`: Export symbols to CSV
- `export_symbols_json(symbols, output_path, title)`: Export symbols to JSON
- `export_filter_result(filter_result, output_path, format_type)`: Export filter result

### LoggingConfig

Centralized logging configuration.

```python
from auto_financial_filter.utils import LoggingConfig

# Setup logging
LoggingConfig.setup_logging(
    level='INFO',
    log_file='app.log',
    verbose=True
)

# Setup filter-specific logging
logger = LoggingConfig.setup_filter_logging('liquidity_filter', 'DEBUG')
```

#### Methods

- `setup_logging(level, log_file, verbose, format_style)`: Set up application logging
- `setup_filter_logging(filter_name, level)`: Set up filter-specific logging
- `setup_progress_logging(show_progress)`: Set up progress logging
- `get_performance_logger()`: Get performance logger
- `silence_external_loggers(libraries)`: Silence external library loggers

### ProgressReporter

Utility for reporting progress during long operations.

```python
from auto_financial_filter.utils import ProgressReporter

reporter = ProgressReporter(
    total_items=1000,
    operation_name="Processing stocks",
    report_interval=50
)

for item in items:
    # Process item
    reporter.update()

reporter.finish()
```

### PerformanceTimer

Context manager for measuring performance.

```python
from auto_financial_filter.utils import PerformanceTimer

with PerformanceTimer("Data loading"):
    # Long-running operation
    data = load_data()

# Or get duration
timer = PerformanceTimer("Processing")
with timer:
    process_data()

duration = timer.get_duration()
```

## Models

### StockSymbol

Represents a stock symbol with market information.

```python
from auto_financial_filter.models.base import StockSymbol

symbol = StockSymbol(
    code="005930",
    name="삼성전자",
    market="KOSPI"
)
```

#### Attributes

- `code` (str): Stock code
- `name` (str): Stock name
- `market` (str): Market ('KOSPI' or 'KOSDAQ')

#### Methods

- `validate()`: Validate the stock symbol data
- `is_valid()`: Check if the stock symbol is valid

### FilterResult

Result of a filtering stage.

```python
from auto_financial_filter.models.base import FilterResult

result = FilterResult(
    passed_symbols=[symbol1, symbol2],
    failed_symbols=[symbol3],
    stage="Liquidity Filter",
    criteria_applied={"min_volume": 10000000000}
)
```

#### Attributes

- `passed_symbols` (List[StockSymbol]): Symbols that passed the filter
- `failed_symbols` (List[StockSymbol]): Symbols that failed the filter
- `stage` (str): Name of the filtering stage
- `criteria_applied` (Dict[str, Any]): Criteria applied in this stage

#### Properties

- `total_processed`: Total number of symbols processed
- `pass_rate`: Percentage of symbols that passed

### LiquidityMetrics

Liquidity metrics for a stock symbol.

```python
from auto_financial_filter.models.base import LiquidityMetrics

metrics = LiquidityMetrics(
    symbol=stock_symbol,
    avg_daily_volume=1000000,
    avg_daily_value=50000000000,
    period_days=30
)
```

### FinancialMetrics

Financial health metrics for a stock symbol.

```python
from auto_financial_filter.models.base import FinancialMetrics

metrics = FinancialMetrics(
    symbol=stock_symbol,
    debt_ratio=150.0,
    operating_cash_flow=[100, 120, 110, 130],
    revenue_growth_yoy=15.0,
    quarterly_revenue=[1000, 1100, 1050, 1200]
)
```

### ProfitabilityMetrics

Profitability and trend metrics for a stock symbol.

```python
from auto_financial_filter.models.base import ProfitabilityMetrics

metrics = ProfitabilityMetrics(
    symbol=stock_symbol,
    operating_margin=12.5,
    operating_profit_trend=[100, 110, 120, 130] * 4,  # 16 quarters
    cogs_ratio_trend=[60, 58, 55, 53, 50, 48],  # 6 quarters
    is_profit_peak=True
)
```

## Error Handling

All classes and methods include comprehensive error handling:

- **Configuration Errors**: Invalid parameter values raise `ValueError` with descriptive messages
- **Data Access Errors**: Network and API errors are handled with retry logic
- **Validation Errors**: Invalid data raises `ValueError` with specific error details
- **File Errors**: File operations handle `FileNotFoundError` and permission errors

## Type Hints

All public APIs include comprehensive type hints for better IDE support and code clarity.

## Examples

See the `examples/` directory for complete usage examples:

- `basic_usage.py`: Basic filtering pipeline usage
- `configuration_examples.py`: Configuration examples for different strategies
- `export_and_analysis.py`: Export and analysis examples