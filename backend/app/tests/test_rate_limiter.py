"""Tests for the rate limiting and brute-force protection service."""

import time
import pytest
from fastapi import HTTPException

from app.services.rate_limiter import RateLimiter


@pytest.fixture
def rate_limiter():
    """Create a new RateLimiter for each test."""
    return RateLimiter(capacity=5, window_seconds=600)


class TestCheckRateLimit:
    """Tests for the rate limit check (5 attempts per 10 minutes)."""

    async def test_allows_first_attempt(self, rate_limiter):
        """First attempt from a new IP should be allowed."""
        await rate_limiter.check_rate_limit("192.168.1.1")

    async def test_allows_up_to_4_failed_attempts(self, rate_limiter):
        """Should allow attempts when count is below the threshold."""
        ip = "192.168.1.1"
        for _ in range(4):
            await rate_limiter.record_failed_attempt(ip)
        await rate_limiter.check_rate_limit(ip)

    async def test_rejects_at_5_failed_attempts(self, rate_limiter):
        """Should reject when 5 failed attempts are recorded in the window."""
        ip = "192.168.1.1"
        for _ in range(5):
            await rate_limiter.record_failed_attempt(ip)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter.check_rate_limit(ip)
        assert exc_info.value.status_code == 429

    async def test_different_ips_are_independent(self, rate_limiter):
        """Rate limits should be tracked independently per IP."""
        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        for _ in range(5):
            await rate_limiter.record_failed_attempt(ip1)

        await rate_limiter.check_rate_limit(ip2)


class TestCheckBruteForce:
    """Tests for brute-force detection (20 attempts per hour)."""

    async def test_allows_when_no_ban(self, rate_limiter):
        """Should allow when IP is not banned."""
        await rate_limiter.check_brute_force("192.168.1.1")

    async def test_bans_ip_at_20_attempts(self, rate_limiter):
        """Should ban IP when 20 failed attempts are recorded."""
        ip = "10.0.0.1"
        for _ in range(20):
            await rate_limiter.record_failed_attempt(ip)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter.check_brute_force(ip)
        assert exc_info.value.status_code == 429
        assert "temporarily blocked" in exc_info.value.detail


class TestRecordSuccess:
    """Tests for recording successful login."""

    async def test_clears_rate_limit_window(self, rate_limiter):
        """Successful login should clear the rate-limit counter."""
        ip = "192.168.1.1"

        for _ in range(3):
            await rate_limiter.record_failed_attempt(ip)

        await rate_limiter.record_success(ip)

        # Rate limit key should be cleared
        assert ip not in rate_limiter._history
