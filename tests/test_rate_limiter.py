"""Rate limiter: the Cloudflare edge header and the per-tier limit."""

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


def test_limit_still_counts_and_rejects():
    limiter = SlidingWindowRateLimiter()
    limit, _ = TIERS["expensive"]
    assert all(limiter.check("expensive", "expensive:ip")[0] for _ in range(limit))
    allowed, remaining, retry_after = limiter.check("expensive", "expensive:ip")
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0

