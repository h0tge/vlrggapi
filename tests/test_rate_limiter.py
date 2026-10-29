"""Rate limiter: who the key belongs to, and that keys are forgotten."""

import time

from starlette.datastructures import Headers

from api.utils.rate_limiter import TIERS, SlidingWindowRateLimiter


def _request(**headers: str):
    """The two attributes ``_client_ip`` reads, shaped like a real request."""

    class _Request:
        pass

    request = _Request()
    request.headers = Headers(headers)
    request.client = type("Client", (), {"host": "10.0.0.1"})()
    return request


def test_forwarded_for_is_ignored_when_the_edge_stamps_the_client():
    """2026-10-29: the first XFF entry is caller-supplied, so it reset limits."""
    request = _request(**{"CF-Connecting-IP": "198.51.100.7", "X-Forwarded-For": "203.0.113.9"})
    assert SlidingWindowRateLimiter._client_ip(request) == "198.51.100.7"


def test_forwarded_for_is_the_fallback_without_the_edge_header():
    request = _request(**{"X-Forwarded-For": "203.0.113.9, 198.51.100.7"})
    assert SlidingWindowRateLimiter._client_ip(request) == "203.0.113.9"


def test_limit_still_counts_and_rejects():
    limiter = SlidingWindowRateLimiter()
    limit, _ = TIERS["expensive"]
    assert all(limiter.check("expensive", "expensive:ip")[0] for _ in range(limit))
    allowed, remaining, retry_after = limiter.check("expensive", "expensive:ip")
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


def test_prune_forgets_keys_whose_window_expired():
    limiter = SlidingWindowRateLimiter()
    limiter.check("cheap", "cheap:a")
    limiter.check("moderate", "moderate:b")

    limiter._prune(time.time() + 3600)

    assert limiter._stores["cheap"] == {}
    assert limiter._stores["moderate"] == {}
