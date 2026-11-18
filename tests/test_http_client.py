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
