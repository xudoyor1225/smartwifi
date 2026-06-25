"""Rate limiting and brute-force protection service.

In-memory implementation using Token Bucket / Sliding Window logic.
Tracks per-IP failed login attempts and enforces limits without needing Redis.
"""

import time
from typing import Dict
from fastapi import HTTPException, status

class RateLimiter:
    """In-memory sliding window rate limiter for login attempts."""

    def __init__(self, capacity: int = 5, window_seconds: int = 600) -> None:
        self.capacity = capacity
        self.window_seconds = window_seconds
        # dict mapping IP to list of timestamps
        self._history: Dict[str, list[float]] = {}
        
        # IP ban tracking: mapping IP to ban_expiry_timestamp
        self._banned_ips: Dict[str, float] = {}

    def _cleanup_old_entries(self, ip_address: str, now: float) -> list[float]:
        """Remove timestamps older than the window."""
        if ip_address not in self._history:
            return []
            
        valid_timestamps = [t for t in self._history[ip_address] if now - t <= self.window_seconds]
        if valid_timestamps:
            self._history[ip_address] = valid_timestamps
        else:
            self._history.pop(ip_address, None)
            
        return valid_timestamps

    async def check_rate_limit(self, ip_address: str) -> None:
        """Check if the IP has exceeded the rate limit.

        Args:
            ip_address: The client IP address to check.

        Raises:
            HTTPException: 429 if the IP has exceeded the rate limit.
        """
        now = time.time()
        valid_timestamps = self._cleanup_old_entries(ip_address, now)

        if len(valid_timestamps) >= self.capacity:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later.",
            )

    async def check_brute_force(self, ip_address: str) -> None:
        """Check if the IP is currently banned due to suspicious activity.

        Raises:
            HTTPException: 429 if the IP is currently banned.
        """
        now = time.time()
        ban_expiry = self._banned_ips.get(ip_address)
        
        if ban_expiry:
            if now < ban_expiry:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="IP address temporarily blocked due to suspicious activity. Please try again later.",
                )
            else:
                # Ban expired
                self._banned_ips.pop(ip_address, None)

    async def record_failed_attempt(self, ip_address: str) -> None:
        """Record a failed login attempt."""
        now = time.time()
        valid_timestamps = self._cleanup_old_entries(ip_address, now)
        valid_timestamps.append(now)
        self._history[ip_address] = valid_timestamps
        
        # Check if we should ban (brute force - 20 attempts)
        # We reuse the same history but just check if it exceeded 20 in the same window
        if len(valid_timestamps) >= 20:
            # Ban for 30 minutes (1800 seconds)
            self._banned_ips[ip_address] = now + 1800
            
    async def record_success(self, ip_address: str) -> None:
        """Reset counters on successful login."""
        self._history.pop(ip_address, None)

# Global singleton instance
_limiter_instance = RateLimiter(capacity=5, window_seconds=600)

def get_limiter() -> RateLimiter:
    return _limiter_instance
