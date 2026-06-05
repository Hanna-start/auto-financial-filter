"""
Data export utilities for the financial stock filter system.

This module provides functions to export filtering results and data
to various formats including CSV, Excel, and JSON.
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from ..models.base import StockSymbol, FilterResult
from ..pipeline import PipelineResult

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Utility class for exporting financial stock filter data to various formats.
    """
    
    @staticmethod
    def export_pipeline_result_csv(result: PipelineResult, output_path: str) -> None:
        """
        Export pipeline result to CSV format.
        
        Args:
            result: PipelineResult to export
            output_path: Path to output CSV file
        """
        output_file = Path(output_path)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header information
            writer.writerow(['# Financial Stock Filter Results'])
            writer.writerow([f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow([f'# Total processed: {result.total_processed}'])
            writer.writerow([f'# Final candidates: {len(result.final_candidates)}'])
            writer.writerow([f'# Execution time: {result.execution_time_seconds:.2f}s'])
            writer.writerow([])
            
            # Write final candidates
            writer.writerow(['# Final Candidate Stocks'])
            writer.writerow(['Code', 'Name', 'Market'])
            
            for symbol in result.final_candidates:
                writer.writerow([symbol.code, symbol.name, symbol.market])
            
            writer.writerow([])
            
            # Write stage summary
            writer.writerow(['# Stage Summary'])
            writer.writerow(['Stage', 'Input_Count', 'Passed_Count', 'Failed_Count', 'Pass_Rate'])
            
            for stage_result in result.stage_results:
                writer.writerow([
                    stage_result.stage,
                    stage_result.total_processed,
                    len(stage_result.passed_symbols),
                    len(stage_result.failed_symbols),
                    f"{stage_result.pass_rate:.1f}%"
                ])
        
        logger.info(f"Pipeline result exported to CSV: {output_path}")
    
    @staticmethod
    def export_pipeline_result_json(result: PipelineResult, output_path: str) -> None:
        """
        Export pipeline result to JSON format.
        
        Args:
            result: PipelineResult to export
            output_path: Path to output JSON file
        """
        # Convert result to dictionary
        export_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_processed': result.total_processed,
                'final_candidates_count': len(result.final_candidates),
                'execution_time_seconds': result.execution_time_seconds
            },
            'final_candidates': [
                {
                    'code': symbol.code,
                    'name': symbol.name,
                    'market': symbol.market
                }
                for symbol in result.final_candidates
            ],
            'stage_results': [
                {
                    'stage': stage_result.stage,
                    'input_count': stage_result.total_processed,
                    'passed_count': len(stage_result.passed_symbols),
                    'failed_count': len(stage_result.failed_symbols),
                    'pass_rate': stage_result.pass_rate,
                    'criteria_applied': stage_result.criteria_applied,
                    'passed_symbols': [
                        {
                            'code': symbol.code,
                            'name': symbol.name,
                            'market': symbol.market
                        }
                        for symbol in stage_result.passed_symbols
                    ]
                }
                for stage_result in result.stage_results
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Pipeline result exported to JSON: {output_path}")
    
    @staticmethod
    def export_pipeline_result_excel(result: PipelineResult, output_path: str) -> None:
        """
        Export pipeline result to Excel format.
        
        Args:
            result: PipelineResult to export
            output_path: Path to output Excel file
        """
        if not PANDAS_AVAILABLE:
            logger.warning("Pandas not available. Falling back to CSV export.")
            csv_path = str(Path(output_path).with_suffix('.csv'))
            DataExporter.export_pipeline_result_csv(result, csv_path)
            return
        
        # Create Excel writer
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            
            # Summary sheet
            summary_data = {
                'Metric': [
                    'Total Processed',
                    'Final Candidates',
                    'Overall Pass Rate (%)',
                    'Execution Time (seconds)',
                    'Generated At'
                ],
                'Value': [
                    result.total_processed,
                    len(result.final_candidates),
                    f"{len(result.final_candidates) / result.total_processed * 100:.2f}",
                    result.execution_time_seconds,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Final candidates sheet
            if result.final_candidates:
                candidates_data = {
                    'Code': [s.code for s in result.final_candidates],
                    'Name': [s.name for s in result.final_candidates],
                    'Market': [s.market for s in result.final_candidates]
                }
                
                candidates_df = pd.DataFrame(candidates_data)
                candidates_df.to_excel(writer, sheet_name='Final Candidates', index=False)
            
            # Stage results sheet
            stage_data = {
                'Stage': [sr.stage for sr in result.stage_results],
                'Input Count': [sr.total_processed for sr in result.stage_results],
                'Passed Count': [len(sr.passed_symbols) for sr in result.stage_results],
                'Failed Count': [len(sr.failed_symbols) for sr in result.stage_results],
                'Pass Rate (%)': [sr.pass_rate for sr in result.stage_results]
            }
            
            stage_df = pd.DataFrame(stage_data)
            stage_df.to_excel(writer, sheet_name='Stage Results', index=False)
            
            # Individual stage sheets
            for i, stage_result in enumerate(result.stage_results):
                if stage_result.passed_symbols:
                    stage_symbols_data = {
                        'Code': [s.code for s in stage_result.passed_symbols],
                        'Name': [s.name for s in stage_result.passed_symbols],
                        'Market': [s.market for s in stage_result.passed_symbols]
                    }
                    
                    stage_symbols_df = pd.DataFrame(stage_symbols_data)
                    sheet_name = f"Stage {i+1} Passed"
                    stage_symbols_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        logger.info(f"Pipeline result exported to Excel: {output_path}")
    
    @staticmethod
    def export_symbols_csv(symbols: List[StockSymbol], output_path: str, 
                          title: str = "Stock Symbols") -> None:
        """
        Export a list of stock symbols to CSV format.
        
        Args:
            symbols: List of StockSymbol objects
            output_path: Path to output CSV file
            title: Title for the export
        """
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([f'# {title}'])
            writer.writerow([f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow([f'# Total symbols: {len(symbols)}'])
            writer.writerow([])
            
            # Write symbols
            writer.writerow(['Code', 'Name', 'Market'])
            for symbol in symbols:
                writer.writerow([symbol.code, symbol.name, symbol.market])
        
        logger.info(f"Symbols exported to CSV: {output_path}")
    
    @staticmethod
    def export_symbols_json(symbols: List[StockSymbol], output_path: str,
                           title: str = "Stock Symbols") -> None:
        """
        Export a list of stock symbols to JSON format.
        
        Args:
            symbols: List of StockSymbol objects
            output_path: Path to output JSON file
            title: Title for the export
        """
        export_data = {
            'metadata': {
                'title': title,
                'generated_at': datetime.now().isoformat(),
                'total_symbols': len(symbols)
            },
            'symbols': [
                {
                    'code': symbol.code,
                    'name': symbol.name,
                    'market': symbol.market
                }
                for symbol in symbols
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Symbols exported to JSON: {output_path}")
    
    @staticmethod
    def export_filter_result(filter_result: FilterResult, output_path: str, 
                            format_type: str = 'csv') -> None:
        """
        Export a single filter result to the specified format.
        
        Args:
            filter_result: FilterResult to export
            output_path: Path to output file
            format_type: Export format ('csv', 'json', 'excel')
        """
        if format_type.lower() == 'csv':
            DataExporter._export_filter_result_csv(filter_result, output_path)
        elif format_type.lower() == 'json':
            DataExporter._export_filter_result_json(filter_result, output_path)
        elif format_type.lower() == 'excel':
            DataExporter._export_filter_result_excel(filter_result, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    @staticmethod
    def _export_filter_result_csv(filter_result: FilterResult, output_path: str) -> None:
        """Export FilterResult to CSV format."""
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([f'# Filter Result: {filter_result.stage}'])
            writer.writerow([f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow([f'# Total processed: {filter_result.total_processed}'])
            writer.writerow([f'# Passed: {len(filter_result.passed_symbols)}'])
            writer.writerow([f'# Failed: {len(filter_result.failed_symbols)}'])
            writer.writerow([f'# Pass rate: {filter_result.pass_rate:.1f}%'])
            writer.writerow([])
            
            # Write criteria
            writer.writerow(['# Criteria Applied'])
            for key, value in filter_result.criteria_applied.items():
                writer.writerow([key, value])
            writer.writerow([])
            
            # Write passed symbols
            writer.writerow(['# Passed Symbols'])
            writer.writerow(['Code', 'Name', 'Market'])
            for symbol in filter_result.passed_symbols:
                writer.writerow([symbol.code, symbol.name, symbol.market])
    
    @staticmethod
    def _export_filter_result_json(filter_result: FilterResult, output_path: str) -> None:
        """Export FilterResult to JSON format."""
        export_data = {
            'metadata': {
                'stage': filter_result.stage,
                'generated_at': datetime.now().isoformat(),
                'total_processed': filter_result.total_processed,
                'passed_count': len(filter_result.passed_symbols),
                'failed_count': len(filter_result.failed_symbols),
                'pass_rate': filter_result.pass_rate
            },
            'criteria_applied': filter_result.criteria_applied,
            'passed_symbols': [
                {
                    'code': symbol.code,
                    'name': symbol.name,
                    'market': symbol.market
                }
                for symbol in filter_result.passed_symbols
            ],
            'failed_symbols': [
                {
                    'code': symbol.code,
                    'name': symbol.name,
                    'market': symbol.market
                }
                for symbol in filter_result.failed_symbols
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def _export_filter_result_excel(filter_result: FilterResult, output_path: str) -> None:
        """Export FilterResult to Excel format."""
        if not PANDAS_AVAILABLE:
            logger.warning("Pandas not available. Falling back to CSV export.")
            csv_path = str(Path(output_path).with_suffix('.csv'))
            DataExporter._export_filter_result_csv(filter_result, csv_path)
            return
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            
            # Summary sheet
            summary_data = {
                'Metric': [
                    'Stage',
                    'Total Processed',
                    'Passed Count',
                    'Failed Count',
                    'Pass Rate (%)',
                    'Generated At'
                ],
                'Value': [
                    filter_result.stage,
                    filter_result.total_processed,
                    len(filter_result.passed_symbols),
                    len(filter_result.failed_symbols),
                    f"{filter_result.pass_rate:.1f}",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Passed symbols sheet
            if filter_result.passed_symbols:
                passed_data = {
                    'Code': [s.code for s in filter_result.passed_symbols],
                    'Name': [s.name for s in filter_result.passed_symbols],
                    'Market': [s.market for s in filter_result.passed_symbols]
                }
                
                passed_df = pd.DataFrame(passed_data)
                passed_df.to_excel(writer, sheet_name='Passed Symbols', index=False)