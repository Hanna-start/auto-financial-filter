# Data Source Requirements and API Limitations

This document describes the data sources used by the Financial Stock Filter system, their requirements, limitations, and setup instructions.

## Overview

The Financial Stock Filter system integrates with three primary Korean financial data sources:

1. **FinanceDataReader** - Market data and trading volumes
2. **OpenDartReader** - Quarterly financial statements from DART
3. **Pykrx** - Additional market data from KRX

The system is designed to work with mock data adapters when real data sources are unavailable, making it suitable for development and testing environments.

## Data Sources

### 1. FinanceDataReader

**Purpose**: Provides market data, stock prices, and trading volumes for Korean stocks.

#### Installation
```bash
pip install FinanceDataReader
```

#### API Limitations
- **Rate Limits**: No explicit rate limits, but excessive requests may be throttled
- **Data Availability**: Historical data availability varies by stock
- **Market Coverage**: Supports both KOSPI and KOSDAQ markets
- **Update Frequency**: Daily updates, typically available after market close

#### Required Data
- Stock listings (KOSPI/KOSDAQ)
- Daily trading data (price, volume, trading value)
- Historical data for volume calculations (30+ days)

#### Usage Example
```python
import FinanceDataReader as fdr

# Get stock listings
kospi_stocks = fdr.StockListing('KOSPI')
kosdaq_stocks = fdr.StockListing('KOSDAQ')

# Get trading data
data = fdr.DataReader('005930', '2024-01-01', '2024-12-31')
```

#### Error Handling
- Network timeouts: Automatic retry with exponential backoff
- Invalid symbols: Graceful handling with logging
- Data unavailability: Skip symbol and continue processing

### 2. OpenDartReader

**Purpose**: Provides quarterly financial statements and corporate filings from the Korean DART system.

#### Installation
```bash
pip install OpenDartReader
```

#### API Key Setup
1. Register at [OpenDART](https://opendart.fss.or.kr/)
2. Apply for API access
3. Obtain API key
4. Set API key in environment or configuration

```python
import OpenDartReader

# Initialize with API key
dart = OpenDartReader(api_key='your_api_key_here')
```

#### API Limitations
- **Rate Limits**: 10,000 requests per day per API key
- **Request Frequency**: Maximum 1 request per second
- **Data Lag**: Financial statements available 1-2 quarters after reporting period
- **Coverage**: Only covers companies that file with DART (most public companies)

#### Required Data
- Quarterly financial statements (income statement, balance sheet, cash flow)
- Company information and corporate codes
- Historical financial data (8+ quarters for YoY calculations)

#### Key Financial Metrics Retrieved
- Revenue (매출액)
- Operating profit (영업이익)
- Total assets (자산총계)
- Total debt (부채총계)
- Total equity (자본총계)
- Operating cash flow (영업활동현금흐름)
- Cost of goods sold (매출원가)

#### Usage Example
```python
import OpenDartReader

dart = OpenDartReader(api_key='your_api_key')

# Get company list
companies = dart.list()

# Get financial statements
fs = dart.finstate('00126380', 2023, reprt_code='11013')  # Quarterly
```

#### Error Handling
- API rate limit exceeded: Automatic retry with delay
- Invalid company codes: Skip and log error
- Missing financial data: Mark as insufficient data
- Network errors: Retry with exponential backoff

### 3. Pykrx

**Purpose**: Provides additional market data directly from the Korea Exchange (KRX).

#### Installation
```bash
pip install pykrx
```

#### API Limitations
- **Rate Limits**: Implicit rate limiting, excessive requests may be blocked
- **Data Availability**: Real-time and historical market data
- **Market Hours**: Some data only available during market hours
- **Maintenance Windows**: Periodic maintenance may affect availability

#### Required Data
- Market capitalization data
- Shares outstanding
- Sector information
- Additional market metrics

#### Usage Example
```python
from pykrx import stock

# Get market cap data
market_cap = stock.get_market_cap_by_ticker('20241201', market='KOSPI')

# Get sector information
sector_info = stock.get_market_sector_classifications('20241201')
```

#### Error Handling
- Service unavailable: Fallback to cached data or skip
- Invalid dates: Use alternative date ranges
- Network timeouts: Retry with backoff

## Data Flow Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ FinanceDataReader│    │  OpenDartReader  │    │     Pykrx       │
│                 │    │                  │    │                 │
│ • Stock listings│    │ • Financial      │    │ • Market cap    │
│ • Trading data  │    │   statements     │    │ • Sector info   │
│ • Price/volume  │    │ • Quarterly data │    │ • Additional    │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   DataAccessManager      │
                    │                          │
                    │ • Coordinates adapters   │
                    │ • Handles errors         │
                    │ • Manages retries        │
                    │ • Provides caching       │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Filtering Pipeline     │
                    │                          │
                    │ • Liquidity Filter       │
                    │ • Financial Health       │
                    │ • Quality Growth         │
                    └──────────────────────────┘
```

## Configuration Requirements

### Environment Variables (Optional)
```bash
# OpenDart API Key
export DART_API_KEY="your_api_key_here"

# Cache directory
export FINANCIAL_FILTER_CACHE_DIR="/path/to/cache"

# Log level
export FINANCIAL_FILTER_LOG_LEVEL="INFO"
```

### Configuration File
```yaml
# Data source settings
api_retry_attempts: 3
api_timeout_seconds: 30
data_cache_enabled: true
data_cache_ttl_hours: 24

# Logging
log_level: "INFO"
verbose_output: false
```

## Mock Data Adapters

For development and testing, the system includes mock data adapters that simulate real data sources:

### MockDataAccessManager

Provides realistic mock data for all required operations:

- **Stock Listings**: Generates sample KOSPI/KOSDAQ stocks
- **Trading Data**: Creates realistic price and volume data
- **Financial Data**: Generates quarterly financial statements
- **Market Data**: Provides mock market capitalization data

#### Usage
```python
from auto_financial_filter.data_access.mock_adapters import MockDataAccessManager

# Use mock data (no API keys required)
mock_data_manager = MockDataAccessManager(config)
symbols = mock_data_manager.get_all_symbols()
```

#### Benefits
- No API keys or network access required
- Consistent data for testing
- Faster execution for development
- Predictable results for unit tests

## Performance Considerations

### Data Caching

The system implements intelligent caching to minimize API calls:

- **Symbol Lists**: Cached for 24 hours (configurable)
- **Trading Data**: Cached per symbol and date range
- **Financial Data**: Cached per symbol and quarter count
- **Cache Management**: Automatic cleanup of expired entries

### Rate Limit Management

- **Request Throttling**: Automatic delays between requests
- **Exponential Backoff**: Increasing delays on failures
- **Retry Logic**: Configurable retry attempts
- **Error Recovery**: Graceful handling of rate limit errors

### Batch Processing

- **Parallel Processing**: Multiple symbols processed concurrently (where safe)
- **Progress Reporting**: Real-time progress updates
- **Memory Management**: Efficient memory usage for large datasets
- **Error Isolation**: Individual symbol failures don't stop processing

## Troubleshooting

### Common Issues

#### 1. API Key Issues
**Problem**: OpenDart API authentication failures
**Solution**: 
- Verify API key is correct
- Check API key hasn't expired
- Ensure proper environment variable setup

#### 2. Rate Limit Exceeded
**Problem**: Too many API requests
**Solution**:
- Increase `api_retry_attempts` in configuration
- Enable caching with longer TTL
- Reduce batch sizes for processing

#### 3. Network Connectivity
**Problem**: Network timeouts or connection errors
**Solution**:
- Increase `api_timeout_seconds`
- Check firewall settings
- Verify internet connectivity
- Use mock adapters for offline development

#### 4. Data Availability
**Problem**: Missing or incomplete data for certain stocks
**Solution**:
- Check if company files with DART
- Verify stock is actively traded
- Use longer historical periods
- Review data source coverage

### Debugging

Enable verbose logging for detailed debugging:

```python
from auto_financial_filter.config import FilterConfig

config = FilterConfig(
    verbose_output=True,
    log_level="DEBUG",
    log_file_path="debug.log"
)
```

### Data Source Status Check

```python
# Check data source availability
availability = data_manager.get_availability_status()
for source, available in availability.items():
    print(f"{source}: {'Available' if available else 'Not Available'}")

# Check retry counts
retry_counts = data_manager.get_retry_counts()
for source, count in retry_counts.items():
    print(f"{source} retries: {count}")
```

## Best Practices

### 1. API Key Management
- Store API keys in environment variables
- Never commit API keys to version control
- Use different keys for development and production
- Monitor API usage and quotas

### 2. Error Handling
- Always handle network errors gracefully
- Log errors for debugging but continue processing
- Use fallback data sources when available
- Implement circuit breakers for failing services

### 3. Performance Optimization
- Enable caching for repeated runs
- Use appropriate batch sizes
- Monitor memory usage with large datasets
- Implement progress reporting for long operations

### 4. Data Quality
- Validate data before processing
- Handle missing or invalid data gracefully
- Log data quality issues for review
- Implement data freshness checks

## Compliance and Legal

### Data Usage
- Respect API terms of service
- Follow rate limits and usage guidelines
- Ensure proper attribution where required
- Monitor for changes in API terms

### Privacy
- Handle financial data according to regulations
- Implement appropriate data retention policies
- Secure API keys and sensitive information
- Follow data protection best practices

## Support and Resources

### Official Documentation
- [FinanceDataReader GitHub](https://github.com/FinanceData/FinanceDataReader)
- [OpenDartReader GitHub](https://github.com/josw123/dart-fss)
- [Pykrx GitHub](https://github.com/sharebook-kr/pykrx)
- [OpenDART API Documentation](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018)

### Community Resources
- Korean financial data communities
- Stack Overflow for technical issues
- GitHub issues for library-specific problems

### System Support
- Check system logs for detailed error information
- Use mock adapters to isolate data source issues
- Enable debug logging for troubleshooting
- Monitor system performance and resource usage