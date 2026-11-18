"""fetch_with_retries must always hand httpx a finite timeout."""

import httpx
import pytest

from utils.http_client import fetch_with_retries


class _RecordingClient:
    def __init__(self):
        self.timeouts = []

    async def get(self, url, timeout=None, headers=None):
        self.timeouts.append(timeout)
        return httpx.Response(200, content=b"x" * 5000)


@pytest.mark.anyio
async def test_default_call_sets_a_finite_timeout():
    """2026-11-09: default `timeout=None` reached client.get, which in httpx
    means no timeout, so a stalled vlr.gg socket hung /v2/player matches and
    live_score forever. Breaking edit: `timeout=DEFAULT_TIMEOUT` -> `timeout=None`."""
    client = _RecordingClient()
    await fetch_with_retries("https://www.vlr.gg/player/matches/9/", client=client)
    assert client.timeouts[0] is not None


def test_upstream_rate_limit_reads_env(monkeypatch):
    # Breaks if the limit goes back to a hard-coded number: the Render deploy tunes it with UPSTREAM_RATE_LIMIT.
    import importlib

    import utils.constants as constants
    monkeypatch.setenv("UPSTREAM_RATE_LIMIT", "7")
    assert importlib.reload(constants).UPSTREAM_RATE_LIMIT == 7
    monkeypatch.delenv("UPSTREAM_RATE_LIMIT")
    assert importlib.reload(constants).UPSTREAM_RATE_LIMIT == 25


class _Flaky503Client:
    async def get(self, url, timeout=None, headers=None):
        return httpx.Response(503)


@pytest.mark.anyio
async def test_every_retry_waits_for_the_vlr_rate_limit(monkeypatch):
    # Breaks if the limiter wait sits outside the retry loop: retries would hit vlr.gg past the quota.
    import utils.http_client as hc
    waits = []

    async def counting_wait():
        waits.append(1)

    async def no_sleep(_):
        return None

    monkeypatch.setattr(hc.upstream_rate_limiter, "wait_if_needed", counting_wait)
    monkeypatch.setattr(hc.asyncio, "sleep", no_sleep)
    hc.circuit_breaker.reset()
    try:
        await fetch_with_retries("https://www.vlr.gg/matches", client=_Flaky503Client(), max_retries=3)
    except Exception:
        pass
    hc.circuit_breaker.reset()
    assert len(waits) == 3


@pytest.mark.anyio
async def test_pagination_waits_for_the_vlr_rate_limit(monkeypatch):
    # Breaks if paginated scrapes call vlr.gg without going through the shared limiter.
    import utils.http_client as hc
    import utils.pagination as pg
    waits = []

    async def counting_wait():
        waits.append(1)

    async def no_sleep(_):
        return None

    class _OkClient:
        async def get(self, url, timeout=None):
            return httpx.Response(200, text="<html></html>")

    monkeypatch.setattr(hc.upstream_rate_limiter, "wait_if_needed", counting_wait)
    monkeypatch.setattr(pg.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(pg, "get_http_client", lambda: _OkClient())
    config = pg.PaginationConfig(num_pages=3)
    await pg.scrape_multiple_pages("https://www.vlr.gg/matches/results", lambda html, page: [], config)
    assert len(waits) == 3
