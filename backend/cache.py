"""
Simple in-memory cache for MCQ generation
Reduces redundant API calls for identical content
"""
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class MCQCache:
    """Simple in-memory cache with TTL support"""
    
    def __init__(self, ttl_minutes: int = 60):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
    
    def _get_hash(self, content: str, cos: list, count: int) -> str:
        """Generate cache key from content + parameters"""
        key_str = f"{content}_{sorted(cos)}_{count}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
    
    def get(self, content: str, cos: list, count: int) -> Optional[Dict[str, Any]]:
        """Retrieve cached result if exists and not expired"""
        key = self._get_hash(content, cos, count)
        
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check expiration
        if datetime.now() - entry["timestamp"] > self._ttl:
            del self._cache[key]
            return None
        
        return entry["data"]
    
    def set(self, content: str, cos: list, count: int, data: Dict[str, Any]) -> None:
        """Store result in cache"""
        key = self._get_hash(content, cos, count)
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now()
        }
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
    
    def size(self) -> int:
        """Get number of cached entries"""
        return len(self._cache)


# Global cache instance
mcq_cache = MCQCache(ttl_minutes=60)
