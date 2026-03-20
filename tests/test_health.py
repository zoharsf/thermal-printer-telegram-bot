# tests/test_health.py
import shutil
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

from catprint_bot.api.health import create_health_app


@pytest.fixture
def app():
    msg_repo = AsyncMock()
    msg_repo.pending_count = AsyncMock(return_value=5)
    scheduler = AsyncMock()
    scheduler.is_paused = False
    scheduler.consecutive_failures = 0
    return create_health_app(msg_repo=msg_repo, scheduler=scheduler)


@pytest.mark.asyncio
async def test_health_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_metrics_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_messages"] == 5
    assert "disk_usage_percent" in data
