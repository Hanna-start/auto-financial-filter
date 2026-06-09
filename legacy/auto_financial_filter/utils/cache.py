"""
Data caching utilities for the financial stock filter system.

This module provides caching mechanisms to improve performance for repeated runs
by storing frequently accessed data with configurable TTL (Time To Live).
"""

import json
import pickle
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, Union
import logging

logger = logging.getLogger(__name__)


class DataCache:
    """
    File-based data cache with TTL support.
    
    Provides caching for expensive data operations like API calls and
    financial data retrieval to improve performance on repeated runs.
    """
    
    def __init__(self, cache_dir: str = ".cache", ttl_hours: int = 24):
        """
        Initialize the data cache.
        
        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Time to live for cached data in hours
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_hours = ttl_hours
        self.cache_dir.mkdir(exist_ok=True)
        
        logger.info(f"DataCache initialized: dir={cache_dir}, ttl={ttl_hours}h")
    
    def _get_cache_key(self, key: str) -> str:
        """
        Generate a safe cache key from the input key.
        
        Args:
            key: Original cache key
            
        Returns:
            Safe filename for cache storage
        """
        # Create a hash of the key to ensure safe filenames
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        return f"cache_{key_hash}.pkl"
    
    def _get_cache_path(self, key: str) -> Path:
        """Get the full path for a cache file."""
        cache_key = self._get_cache_key(key)
        return self.cache_dir / cache_key
    
    def _is_expired(self, cache_path: Path) -> bool:
        """
        Check if a cache file has expired.
        
        Args:
            cache_path: Path to the cache file
            
        Returns:
            True if expired, False otherwise
        """
        if not cache_path.exists():
            return True
        
        # Get file modification time
        mod_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = mod_time + timedelta(hours=self.ttl_hours)
        
        return datetime.now() > expiry_time
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve data from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data if available and not expired, None otherwise
        """
        cache_path = self._get_cache_path(key)
        
        if self._is_expired(cache_path):
            logger.debug(f"Cache miss or expired for key: {key}")
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
            logger.debug(f"Cache hit for key: {key}")
            return data
        except Exception as e:
            logger.warning(f"Error reading cache for key {key}: {e}")
            return None
    
    def set(self, key: str, data: Any) -> None:
        """
        Store data in cache.
        
        Args:
            key: Cache key
            data: Data to cache
        """
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            logger.debug(f"Data cached for key: {key}")
        except Exception as e:
            logger.warning(f"Error writing cache for key {key}: {e}")
    
    def delete(self, key: str) -> bool:
        """
        Delete cached data.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False if not found
        """
        cache_path = self._get_cache_path(key)
        
        if cache_path.exists():
            try:
                cache_path.unlink()
                logger.debug(f"Cache deleted for key: {key}")
                return True
            except Exception as e:
                logger.warning(f"Error deleting cache for key {key}: {e}")
        
        return False
    
    def clear(self) -> int:
        """
        Clear all cached data.
        
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        
        for cache_file in self.cache_dir.glob("cache_*.pkl"):
            try:
                cache_file.unlink()
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Error deleting cache file {cache_file}: {e}")
        
        logger.info(f"Cache cleared: {deleted_count} files deleted")
        return deleted_count
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache files.
        
        Returns:
            Number of expired files deleted
        """
        deleted_count = 0
        
        for cache_file in self.cache_dir.glob("cache_*.pkl"):
            if self._is_expired(cache_file):
                try:
                    cache_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Error deleting expired cache file {cache_file}: {e}")
        
        logger.info(f"Expired cache cleanup: {deleted_count} files deleted")
        return deleted_count
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        cache_files = list(self.cache_dir.glob("cache_*.pkl"))
        total_files = len(cache_files)
        
        total_size = sum(f.stat().st_size for f in cache_files)
        expired_files = sum(1 for f in cache_files if self._is_expired(f))
        
        return {
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl_hours,
            "total_files": total_files,
            "expired_files": expired_files,
            "active_files": total_files - expired_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }


class CachedDataAccessManager:
    """
    Wrapper for DataAccessManager that adds caching capabilities.
    
    This class wraps the standard DataAccessManager to provide transparent
    caching of expensive data operations.
    """
    
    def __init__(self, data_manager, cache: Optional[DataCache] = None):
        """
        Initialize cached data access manager.
        
        Args:
            data_manager: Base DataAccessManager instance
            cache: DataCache instance (creates default if None)
        """
        self.data_manager = data_manager
        self.cache = cache or DataCache()
        
    def get_all_symbols(self):
        """Get all symbols with caching."""
        cache_key = "all_symbols"
        
        # Try cache first
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Fetch from data manager and cache
        symbols = self.data_manager.get_all_symbols()
        self.cache.set(cache_key, symbols)
        
        return symbols
    
    def get_trading_data(self, symbol, days):
        """Get trading data with caching."""
        cache_key = f"trading_data_{symbol.code}_{days}"
        
        # Try cache first
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Fetch from data manager and cache
        trading_data = self.data_manager.get_trading_data(symbol, days)
        self.cache.set(cache_key, trading_data)
        
        return trading_data
    
    def get_financial_data(self, symbol, quarters=4):
        """Get financial data with caching."""
        cache_key = f"financial_data_{symbol.code}_{quarters}"
        
        # Try cache first
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Fetch from data manager and cache
        financial_data = self.data_manager.get_financial_data(symbol, quarters)
        self.cache.set(cache_key, financial_data)
        
        return financial_data
    
    def get_availability_status(self):
        """Get availability status (not cached as it's lightweight)."""
        return self.data_manager.get_availability_status()
    
    def clear_cache(self):
        """Clear all cached data."""
        return self.cache.clear()
    
    def get_cache_info(self):
        """Get cache information."""
        return self.cache.get_cache_info()