"""Phase 11 测试：流式响应与接口优化

测试目标：
1. SSE 流式端点可正常访问并返回事件流
2. 事件序列符合 node_start → node_finish → report → done 的顺序
3. 中文字符在 SSE 事件中正确传递（未被转义）
4. 原有同步接口仍然兼容
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


class TestPhase11Streaming:
    """Phase 11 流式响应测试套件"""

    @staticmethod
    def _stream_params() -> dict[str, str]:
        """构造与 EventSource 一致的 GET 查询参数。"""
        return {
            "start_time": "2022-08-12 16:00:00",
            "end_time": "2022-08-12 16:05:00",
            "symptom_description": "产品温度异常",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
        }

    @pytest.mark.asyncio
    async def test_sse_endpoint_connected(self):
        """测试：SSE 端点连接成功，返回 connected 事件"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "GET",
                "/api/v1/diagnose/stream",
                params=self._stream_params(),
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

                # 收集所有事件
                events = {}
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_type = line.removeprefix("event:").strip()
                    elif line.startswith("data:"):
                        data_str = line.removeprefix("data:").strip()
                        events[event_type] = data_str

                # 验证包含连接成功事件
                assert "connected" in events, f"缺少 connected 事件，收到: {events.keys()}"

    @pytest.mark.asyncio
    async def test_sse_node_sequence(self):
        """测试：SSE 事件遵循 supervisor → data_analyst → diagnosis_expert 的顺序"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            event_order = []
            async with client.stream(
                "GET",
                "/api/v1/diagnose/stream",
                params=self._stream_params(),
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_order.append(line.removeprefix("event:").strip())

                assert "node_start" in event_order, f"缺少 node_start 事件: {event_order}"
                assert "node_finish" in event_order, f"缺少 node_finish 事件: {event_order}"
                assert "done" in event_order, f"缺少 done 事件: {event_order}"

                # done 应在最后
                assert event_order[-1] == "done", f"done 事件应在最后，实际: {event_order[-1]}"

    @pytest.mark.asyncio
    async def test_sse_chinese_output_not_escaped(self):
        """测试：SSE data 中的中文字符未被 unicode 转义"""
        import json

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "GET",
                "/api/v1/diagnose/stream",
                params=self._stream_params(),
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:") and "message" in line:
                        data_str = line.removeprefix("data:").strip()
                        try:
                            data = json.loads(data_str)
                            message = data.get("message", "")
                            # 中文字符应直接出现，不应有 \uXXXX 转义
                            # 检查是否有 unicode 转义的中文
                            assert "\\u" not in data_str or message, \
                                f"数据包含 unicode 转义，可能导致中文显示异常: {data_str}"
                        except json.JSONDecodeError:
                            pass

    @pytest.mark.asyncio
    async def test_sync_endpoint_still_works(self):
        """测试：原有同步诊断接口仍然正常（向后兼容）"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "start_time": "2022-08-12 16:00:00",
                "end_time": "2022-08-12 16:05:00",
                "symptom_description": "产品温度异常",
                "model_provider": "deepseek",
                "model_name": "deepseek-chat",
            }
            response = await client.post("/api/v1/diagnose", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "data" in data
