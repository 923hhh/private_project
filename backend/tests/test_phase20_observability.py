"""Phase 20: 请求 ID、统一错误和基础指标测试."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_session
from app.core.metrics import reset_metrics
from app.main import app


@pytest.fixture(autouse=True)
def override_db_session():
    """覆盖数据库依赖，并重置进程内指标。"""

    async def _override_get_session():
        yield SimpleNamespace()

    asyncio.run(reset_metrics())
    app.dependency_overrides[get_session] = _override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)
        asyncio.run(reset_metrics())


@pytest.mark.asyncio
async def test_health_echoes_request_id_and_updates_metrics():
    """健康检查应回传请求 ID，并在指标里留下请求计数。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health_response = await client.get("/health", headers={"X-Request-ID": "req-health-001"})
        metrics_response = await client.get("/api/v1/system/metrics")

    assert health_response.status_code == 200
    assert health_response.headers["X-Request-ID"] == "req-health-001"

    payload = metrics_response.json()
    http_counters = [item for item in payload["counters"] if item["name"] == "http_requests_total"]
    assert any(
        item["labels"].get("path") == "/health" and item["labels"].get("status_code") == "200"
        for item in http_counters
    )


@pytest.mark.asyncio
async def test_missing_agent_run_returns_structured_error_payload():
    """缺失的 Agent run 应返回统一错误码和请求 ID。"""
    with patch(
        "app.routers.agents.AgentOrchestrationService.get_run",
        new=AsyncMock(return_value=None),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/agents/runs/missing-run",
                headers={"X-Request-ID": "req-agent-404"},
            )

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "req-agent-404"
    payload = response.json()
    assert payload["error_code"] == "agent_run_not_found"
    assert payload["message"] == "指定的 Agent 协作记录不存在。"
    assert payload["request_id"] == "req-agent-404"


@pytest.mark.asyncio
async def test_agent_assist_validation_error_uses_standard_shape():
    """请求校验失败时应返回统一错误结构。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agents/assist",
            json={},
            headers={"X-Request-ID": "req-validation-001"},
        )

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "req-validation-001"
    payload = response.json()
    assert payload["error_code"] == "validation_error"
    assert payload["message"] == "请求参数校验失败。"
    assert payload["request_id"] == "req-validation-001"
    assert isinstance(payload["details"], list)
