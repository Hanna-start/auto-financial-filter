"""
Logging configuration utilities for the financial stock filter system.

This module provides centralized logging configuration with different
verbosity levels and output options.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
import sys


class LoggingConfig:
    """
    Centralized logging configuration for the financial stock filter system.
    """
    
    # Log level mappings
    LOG_LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    @classmethod
    def setup_logging(cls, 
                     level: str = 'INFO',
                     log_file: Optional[str] = None,
                     verbose: bool = False,
                     format_style: str = 'standard') -> None:
        """
        Set up logging configuration for the application.
        
        Args:
            level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            log_file: Optional path to log file
            verbose: Enable verbose output
            format_style: Log format style ('standard', 'detailed', 'simple')
        """
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Set logging level
        log_level = cls.LOG_LEVELS.get(level.upper(), logging.INFO)
        root_logger.setLevel(log_level)
        
        # Choose format based on verbosity and style
        if verbose or format_style == 'detailed':
            log_format = cls._get_detailed_format()
        elif format_style == 'simple':
            log_format = cls._get_simple_format()
        else:
            log_format = cls._get_standard_format()
        
        formatter = logging.Formatter(log_format)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            cls._setup_file_handler(root_logger, log_file, formatter, log_level)
        
        # Log the configuration
        logger = logging.getLogger(__name__)
        logger.info(f"Logging configured: level={level}, file={log_file}, verbose={verbose}")
    
    @classmethod
    def _setup_file_handler(cls, logger: logging.Logger, log_file: str, 
                           formatter: logging.Formatter, level: int) -> None:
        """Set up file logging handler with rotation."""
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use rotating file handler to prevent huge log files
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    @classmethod
    def _get_standard_format(cls) -> str:
        """Get standard log format."""
        return '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    @classmethod
    def _get_detailed_format(cls) -> str:
        """Get detailed log format with more information."""
        return ('%(asctime)s - %(name)s - %(levelname)s - '
                '%(filename)s:%(lineno)d - %(funcName)s() - %(message)s')
    
    @classmethod
    def _get_simple_format(cls) -> str:
        """Get simple log format."""
        return '%(levelname)s: %(message)s'
    
    @classmethod
    def setup_filter_logging(cls, filter_name: str, level: str = 'INFO') -> logging.Logger:
        """
        Set up logging for a specific filter with appropriate naming.
        
        Args:
            filter_name: Name of the filter
            level: Logging level
            
        Returns:
            Configured logger instance
        """
        logger_name = f"auto_financial_filter.filters.{filter_name.lower().replace(' ', '_')}"
        logger = logging.getLogger(logger_name)
        
        # Set level if different from root
        log_level = cls.LOG_LEVELS.get(level.upper(), logging.INFO)
        logger.setLevel(log_level)
        
        return logger
    
    @classmethod
    def setup_progress_logging(cls, show_progress: bool = True) -> logging.Logger:
        """
        Set up progress logging for long-running operations.
        
        Args:
            show_progress: Whether to show progress messages
            
        Returns:
            Progress logger instance
        """
        progress_logger = logging.getLogger('auto_financial_filter.progress')
        
        if show_progress:
            progress_logger.setLevel(logging.INFO)
        else:
            progress_logger.setLevel(logging.WARNING)
        
        return progress_logger
    
    @classmethod
    def get_performance_logger(cls) -> logging.Logger:
        """
        Get a logger specifically for performance metrics.
        
        Returns:
            Performance logger instance
        """
        return logging.getLogger('auto_financial_filter.performance')
    
    @classmethod
    def silence_external_loggers(cls, libraries: Optional[list] = None) -> None:
        """
        Silence noisy external library loggers.
        
        Args:
            libraries: List of library names to silence (uses defaults if None)
        """
        if libraries is None:
            libraries = [
                'urllib3.connectionpool',
                'requests.packages.urllib3.connectionpool',
                'matplotlib',
                'PIL'
            ]
        
        for lib in libraries:
            logging.getLogger(lib).setLevel(logging.WARNING)
    
    @classmethod
    def create_context_logger(cls, context: str, base_logger: Optional[logging.Logger] = None) -> logging.Logger:
        """
        Create a logger with additional context information.
        
        Args:
            context: Context string (e.g., symbol code, operation name)
            base_logger: Base logger to derive from
            
        Returns:
            Logger with context
        """
        if base_logger:
            logger_name = f"{base_logger.name}.{context}"
        else:
            logger_name = f"auto_financial_filter.{context}"
        
        return logging.getLogger(logger_name)


class ProgressReporter:
    """
    Utility class for reporting progress during long-running operations.
    """
    
    def __init__(self, total_items: int, operation_name: str = "Processing", 
                 report_interval: int = 50):
        """
        Initialize progress reporter.
        
        Args:
            total_items: Total number of items to process
            operation_name: Name of the operation being performed
            report_interval: Report progress every N items
        """
        self.total_items = total_items
        self.operation_name = operation_name
        self.report_interval = report_interval
        self.processed_items = 0
        self.logger = logging.getLogger('auto_financial_filter.progress')
    
    def update(self, increment: int = 1) -> None:
        """
        Update progress counter and report if needed.
        
        Args:
            increment: Number of items processed
        """
        self.processed_items += increment
        
        if (self.processed_items % self.report_interval == 0 or 
            self.processed_items == self.total_items):
            
            percentage = (self.processed_items / self.total_items) * 100
            self.logger.info(
                f"{self.operation_name}: {self.processed_items}/{self.total_items} "
                f"({percentage:.1f}%) completed"
            )
    
    def finish(self) -> None:
        """Report completion."""
        self.logger.info(f"{self.operation_name} completed: {self.processed_items} items processed")


class PerformanceTimer:
    """
    Utility class for measuring and logging performance metrics.
    """
    
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        """
        Initialize performance timer.
        
        Args:
            operation_name: Name of the operation being timed
            logger: Logger to use (creates default if None)
        """
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger('auto_financial_filter.performance')
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        """Start timing when entering context."""
        import time
        self.start_time = time.time()
        self.logger.debug(f"Started: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and log results when exiting context."""
        import time
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        if exc_type is None:
            self.logger.info(f"Completed: {self.operation_name} in {duration:.2f} seconds")
        else:
            self.logger.error(f"Failed: {self.operation_name} after {duration:.2f} seconds")
    
    def get_duration(self) -> Optional[float]:
        """
        Get the duration of the timed operation.
        
        Returns:
            Duration in seconds, or None if not completed
        """
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None