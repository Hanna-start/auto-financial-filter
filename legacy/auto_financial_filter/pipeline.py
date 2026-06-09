"""Main pipeline orchestrator for the stock filtering system."""

from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass

from .models.base import StockSymbol, FilterResult, BaseFilter
from .config import FilterConfig


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    stage_results: List[FilterResult]
    final_candidates: List[StockSymbol]
    total_processed: int
    execution_time_seconds: float
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the pipeline execution."""
        summary = {
            'total_processed': self.total_processed,
            'final_candidates': len(self.final_candidates),
            'execution_time_seconds': self.execution_time_seconds,
            'stages': []
        }
        
        for result in self.stage_results:
            summary['stages'].append({
                'stage': result.stage,
                'input_count': result.total_processed,
                'passed_count': len(result.passed_symbols),
                'failed_count': len(result.failed_symbols),
                'pass_rate': result.pass_rate,
                'criteria': result.criteria_applied
            })
        
        return summary


class StockFilterPipeline:
    """Main orchestrator for the 3-stage stock filtering pipeline."""
    
    def __init__(self, config: FilterConfig):
        self.config = config
        self.logger = self._setup_logging()
        self.filters: List[BaseFilter] = []
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logger = logging.getLogger('auto_financial_filter')
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler if specified
        if self.config.log_file_path:
            file_handler = logging.FileHandler(self.config.log_file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def add_filter(self, filter_instance: BaseFilter) -> None:
        """Add a filter to the pipeline."""
        self.filters.append(filter_instance)
        self.logger.info(f"Added filter: {filter_instance.get_stage_name()}")
    
    def execute(self, initial_symbols: List[StockSymbol]) -> PipelineResult:
        """
        Execute the complete filtering pipeline.
        
        Args:
            initial_symbols: Initial list of stock symbols to process
            
        Returns:
            PipelineResult with complete execution details
        """
        import time
        
        start_time = time.time()
        stage_results = []
        current_symbols = initial_symbols.copy()
        
        self.logger.info(f"Starting pipeline with {len(initial_symbols)} symbols")
        
        for i, filter_instance in enumerate(self.filters, 1):
            stage_name = filter_instance.get_stage_name()
            self.logger.info(f"Stage {i}: {stage_name} - Processing {len(current_symbols)} symbols")
            
            try:
                result = filter_instance.filter(current_symbols)
                stage_results.append(result)
                current_symbols = result.passed_symbols
                
                self.logger.info(
                    f"Stage {i} complete: {len(result.passed_symbols)} passed, "
                    f"{len(result.failed_symbols)} failed ({result.pass_rate:.1f}% pass rate)"
                )
                
                if self.config.verbose_output:
                    self.logger.info(f"Stage {i} criteria: {result.criteria_applied}")
                
            except Exception as e:
                self.logger.error(f"Stage {i} failed: {str(e)}")
                raise
        
        execution_time = time.time() - start_time
        
        pipeline_result = PipelineResult(
            stage_results=stage_results,
            final_candidates=current_symbols,
            total_processed=len(initial_symbols),
            execution_time_seconds=execution_time
        )
        
        self.logger.info(
            f"Pipeline complete: {len(current_symbols)} final candidates "
            f"from {len(initial_symbols)} initial symbols "
            f"({execution_time:.2f}s)"
        )
        
        return pipeline_result
    
    def get_stage_count(self) -> int:
        """Get the number of configured filter stages."""
        return len(self.filters)