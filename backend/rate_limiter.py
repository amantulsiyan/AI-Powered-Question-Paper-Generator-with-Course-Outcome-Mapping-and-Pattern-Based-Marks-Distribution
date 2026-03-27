"""
Simple in-memory rate limiter
Prevents API quota exhaustion
"""
from collections import deque
from datetime import datetime, timedelta
from typing import Optional


class RateLimiter:
    """Token bucket rate limiter with per-IP tracking"""
    
    def __init__(self, requests_per_minute: int = 5, requests_per_hour: int = 100):
        self._rpm = requests_per_minute
        self._rph = requests_per_hour
        self._minute_buckets = {}  # ip -> deque of timestamps
        self._hour_buckets = {}
    
    def _clean_old_entries(self, bucket: deque, window: timedelta) -> None:
        """Remove timestamps outside the time window"""
        cutoff = datetime.now() - window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
    
    def is_allowed(self, client_ip: str) -> tuple[bool, Optional[str]]:
        """
        Check if request is allowed for this IP
        Returns: (allowed: bool, error_message: Optional[str])
        """
        now = datetime.now()
        
        # Initialize buckets for new IPs
        if client_ip not in self._minute_buckets:
            self._minute_buckets[client_ip] = deque()
            self._hour_buckets[client_ip] = deque()
        
        minute_bucket = self._minute_buckets[client_ip]
        hour_bucket = self._hour_buckets[client_ip]
        
        # Clean old entries
        self._clean_old_entries(minute_bucket, timedelta(minutes=1))
        self._clean_old_entries(hour_bucket, timedelta(hours=1))
        
        # Check limits
        if len(minute_bucket) >= self._rpm:
            return False, f"Rate limit exceeded: {self._rpm} requests per minute"
        
        if len(hour_bucket) >= self._rph:
            return False, f"Rate limit exceeded: {self._rph} requests per hour"
        
        # Add current request
        minute_bucket.append(now)
        hour_bucket.append(now)
        
        return True, None
    
    def reset(self, client_ip: str) -> None:
        """Reset rate limit for specific IP"""
        self._minute_buckets.pop(client_ip, None)
        self._hour_buckets.pop(client_ip, None)


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=5, requests_per_hour=100)
