"""Phase 12: 核心链路异步测试与大模型 Mock 测试

测试目标：
1. 多智能体路由逻辑：Supervisor 正确路由到 Data Analyst → Diagnosis Expert
2. LLM 降级处理：API Key 缺失时返回降级报告而非崩溃
3. 传感器查询工具：时间范围错误或空数据时的错误处理
4. 同步/流式接口：Schema 校验和错误捕获
5. 数据库层：异步 Session 的 CRUD 操作
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# ============================================================
# 测试组 1：Supervisor 路由逻辑（无依赖）
# ============================================================

class TestSupervisorRouting:
    """Supervisor 节点路由决策测试"""

    def _make_state(self, **overrides):
        from app.agents.state import DiagnosisState
        base: DiagnosisState = {
            "start_time": "2022-08-12 16:00:00",
            "end_time": "2022-08-12 16:05:00",
            "symptom_description": "产品温度异常",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
            "sensor_stats": None,
            "diagnosis_report": None,
            "next_node": "supervisor",
            "messages": [],
        }
        base.update(overrides)
        return base

    def test_first_routing_to_data_analyst(self):
        """首次进入：尚未获取数据 → 路由至 data_analyst"""
        from app.agents.nodes.supervisor import supervisor_node
        state = self._make_state()
        result = supervisor_node(state)
        assert result["next_node"] == "data_analyst"

    def test_second_routing_to_diagnosis_expert(self):
        """数据已获取但无报告 → 路由至 diagnosis_expert"""
        from app.agents.nodes.supervisor import supervisor_node
        state = self._make_state(
            sensor_stats="【传感器统计摘要】\n时间范围: ...\n原始记录条数: 300"
        )
        result = supervisor_node(state)
        assert result["next_node"] == "diagnosis_expert"

    def test_finish_when_report_exists(self):
        """报告已生成 → 结束流程"""
        from app.agents.nodes.supervisor import supervisor_node
        state = self._make_state(
            sensor_stats="【传感器统计摘要】",
            diagnosis_report="【诊断报告】\n时间范围：..."
        )
        result = supervisor_node(state)
        assert result["next_node"] == "__end__"


# ============================================================
# 测试组 2：Data Analyst 节点（Mock 传感器工具）
# ============================================================

class TestDataAnalystNode:
    """Data Analyst 节点测试 - 使用 patch() 正确 mock StructuredTool"""

    def _make_state(self):
        from app.agents.state import DiagnosisState
        state: DiagnosisState = {
            "start_time": "2022-08-12 16:00:00",
            "end_time": "2022-08-12 16:05:00",
            "symptom_description": "产品温度异常",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
            "sensor_stats": None,
            "diagnosis_report": None,
            "next_node": "supervisor",
            "messages": [],
        }
        return state

    @pytest.mark.asyncio
    async def test_query_success(self):
        """正常查询：返回传感器统计摘要"""
        from app.agents.nodes.data_analyst import data_analyst_node

        # 创建一个 mock 工具，其 ainvoke 方法返回预设字符串
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(return_value=(
            "【传感器统计摘要】\n"
            "时间范围: 2022-08-12 16:00:00 至 2022-08-12 16:05:00\n"
            "原始记录条数: 300\n"
            "  温度传感器1(dm_tit01): 均值=45.23°C"
        ))

        state = self._make_state()
        with patch(
            "app.agents.nodes.data_analyst.get_sensor_data_by_time_range",
            mock_tool
        ):
            result = await data_analyst_node(state)

        assert "sensor_stats" in result
        assert "温度传感器1" in result["sensor_stats"]
        assert "45.23" in result["sensor_stats"]

    @pytest.mark.asyncio
    async def test_empty_time_range(self):
        """空时间范围：返回提示而非崩溃"""
        from app.agents.nodes.data_analyst import data_analyst_node

        state = self._make_state()
        state["start_time"] = ""
        state["end_time"] = ""

        result = await data_analyst_node(state)

        assert "sensor_stats" in result
        assert "错误" in result["sensor_stats"] or "未提供" in result["sensor_stats"]

    @pytest.mark.asyncio
    async def test_tool_exception_returns_error_message(self):
        """工具抛出异常：捕获并返回错误消息，不向上抛出"""
        from app.agents.nodes.data_analyst import data_analyst_node

        # 模拟 ainvoke 抛出异常
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(
            side_effect=RuntimeError("模拟数据库超时")
        )

        state = self._make_state()
        with patch(
            "app.agents.nodes.data_analyst.get_sensor_data_by_time_range",
            mock_tool
        ):
            result = await data_analyst_node(state)

        assert "sensor_stats" in result
        assert "数据库超时" in result["sensor_stats"] or "查询失败" in result["sensor_stats"]


# ============================================================
# 测试组 3：LLM 降级报告（无 API Key）
# ============================================================

class TestLLMFallback:
    """验证 LLM 不可用时的降级处理"""

    def test_diagnosis_expert_fallback_without_llm(self):
        """无 API Key：返回基于统计数据的降级报告（同步函数，直接调用）"""
        from app.agents.nodes.diagnosis_expert import diagnosis_expert_node

        state: DiagnosisState = {
            "start_time": "2022-08-12 16:00:00",
            "end_time": "2022-08-12 16:05:00",
            "symptom_description": "产品温度异常",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
            "sensor_stats": "【传感器统计摘要】\n  温度传感器1(dm_tit01): 均值=45.23°C",
            "diagnosis_report": None,
            "next_node": "diagnosis_expert",
            "messages": [],
        }

        # Mock create_llm 返回 None（模拟无 API Key）
        with patch(
            "app.agents.nodes.diagnosis_expert.create_llm",
            return_value=None
        ):
            result = diagnosis_expert_node(state)

        assert "diagnosis_report" in result
        report = result["diagnosis_report"]
        # 降级报告应包含基本结构
        assert "诊断报告" in report or "初步分析" in report
        assert "传感器统计数据" in report

    def test_diagnosis_expert_llm_error_returns_fallback(self):
        """LLM 调用出错：捕获异常并返回降级报告"""
        from app.agents.nodes.diagnosis_expert import diagnosis_expert_node

        state: DiagnosisState = {
            "start_time": "2022-08-12 16:00:00",
            "end_time": "2022-08-12 16:05:00",
            "symptom_description": "产品温度异常",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
            "sensor_stats": "【传感器统计摘要】\n  温度传感器1(dm_tit01): 均值=45.23°C",
            "diagnosis_report": None,
            "next_node": "diagnosis_expert",
            "messages": [],
        }

        # Mock create_llm 返回一个会抛出异常的 LLM
        bad_llm = MagicMock()
        bad_llm.invoke = MagicMock(side_effect=RuntimeError("API 调用失败"))

        with patch(
            "app.agents.nodes.diagnosis_expert.create_llm",
            return_value=bad_llm
        ):
            result = diagnosis_expert_node(state)

        assert "diagnosis_report" in result
        report = result["diagnosis_report"]
        # 应进入降级路径
        assert "诊断报告" in report or "初步分析" in report or "失败" in report

    def test_fallback_report_contains_stats(self):
        """降级报告包含原始统计数据，供人工分析"""
        from app.agents.nodes.diagnosis_expert import _build_fallback_report

        state: DiagnosisState = {
            "start_time": "2022-08-12 16:00:00",
            "end_time": "2022-08-12 16:05:00",
            "symptom_description": "产品温度异常",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
            "sensor_stats": "【传感器统计摘要】\n  温度传感器1(dm_tit01): 均值=45.23°C",
            "diagnosis_report": None,
            "next_node": "diagnosis_expert",
            "messages": [],
        }

        report = _build_fallback_report(state)

        assert "传感器统计数据" in report
        assert "45.23" in report


# ============================================================
# 测试组 4：API 端点 Schema 校验
# ============================================================

class TestAPISchemaValidation:
    """API 请求/响应 Schema 校验测试"""

    @pytest.mark.asyncio
    async def test_diagnose_missing_required_fields(self):
        """缺少必填字段（start_time/end_time）：返回 422"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/diagnose", json={
                "symptom_description": "温度异常"
            })
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_diagnose_invalid_model_provider(self):
        """无效的 model_provider：应被接受（内部降级处理）"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", timeout=30) as client:
            response = await client.post("/api/v1/diagnose", json={
                "start_time": "2022-08-12 16:00:00",
                "end_time": "2022-08-12 16:05:00",
                "model_provider": "invalid_provider",
            })
            # 无效 provider 内部降级，不应 422
            assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_stream_endpoint_exists(self):
        """流式端点：GET + query params 可访问并返回事件流"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", timeout=30) as client:
            response = await client.get("/api/v1/diagnose/stream", params={
                "start_time": "2022-08-12 16:00:00",
                "end_time": "2022-08-12 16:05:00",
                "model_provider": "deepseek",
                "model_name": "deepseek-chat",
            })
            ct = response.headers.get("content-type", "")
            assert "text/event-stream" in ct


# ============================================================
# 测试组 5：多智能体工作流完整流转
# ============================================================

class TestMultiAgentWorkflow:
    """多智能体工作流端到端测试（Mock LLM）"""

    @pytest.mark.asyncio
    async def test_full_workflow_routes_correctly(self):
        """完整流程节点序列验证：supervisor → data_analyst → supervisor → diagnosis_expert → supervisor → END"""
        from app.agents.graph import get_diagnosis_graph

        # Mock 传感器工具
        mock_stats = (
            "【传感器统计摘要】\n"
            "时间范围: 2022-08-12 16:00:00 至 2022-08-12 16:05:00\n"
            "原始记录条数: 300\n"
            "  温度传感器1(dm_tit01): 均值=45.23°C"
        )
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(return_value=mock_stats)

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            "【诊断报告】\n"
            "时间范围：2022-08-12 16:00:00 至 2022-08-12 16:05:00\n\n"
            "■ 异常检测\n"
            "- 温度传感器1均值为45.23°C，处于正常范围\n\n"
            "■ 可能原因分析\n"
            "- 当前数据显示设备运行正常\n\n"
            "■ 建议措施\n"
            "- 持续监控温度变化"
        )
        mock_llm.invoke = MagicMock(return_value=mock_response)

        with patch(
            "app.agents.nodes.data_analyst.get_sensor_data_by_time_range",
            mock_tool
        ), patch(
            "app.agents.nodes.diagnosis_expert.create_llm",
            return_value=mock_llm
        ):
            graph = get_diagnosis_graph()

            state: DiagnosisState = {
                "start_time": "2022-08-12 16:00:00",
                "end_time": "2022-08-12 16:05:00",
                "symptom_description": "产品温度异常",
                "model_provider": "deepseek",
                "model_name": "deepseek-chat",
                "sensor_stats": None,
                "diagnosis_report": None,
                "next_node": "supervisor",
                "messages": [],
            }

            # 遍历 astream 验证节点序列
            node_sequence = []
            async for chunk in graph.astream(state):
                if not isinstance(chunk, dict):
                    continue
                for node_name in chunk.keys():
                    if not node_name.startswith("__"):
                        node_sequence.append(node_name)

            # 验证节点流转
            assert node_sequence[0] == "supervisor"
            assert "data_analyst" in node_sequence
            assert "diagnosis_expert" in node_sequence
            # supervisor 应出现至少 2 次（首节点 + 最终判断结束）
            assert node_sequence.count("supervisor") >= 2

    @pytest.mark.asyncio
    async def test_workflow_error_in_data_analyst_not_crash(self):
        """Data Analyst 查询失败：工作流不崩溃，正常完成"""
        from app.agents.graph import get_diagnosis_graph

        # Mock 传感器工具抛出异常
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(side_effect=RuntimeError("模拟数据库超时"))
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "【诊断报告】\n无法获取传感器数据。"
        mock_llm.invoke = MagicMock(return_value=mock_response)

        with patch(
            "app.agents.nodes.data_analyst.get_sensor_data_by_time_range",
            mock_tool
        ), patch(
            "app.agents.nodes.diagnosis_expert.create_llm",
            return_value=mock_llm
        ):
            graph = get_diagnosis_graph()
            state: DiagnosisState = {
                "start_time": "2022-08-12 16:00:00",
                "end_time": "2022-08-12 16:05:00",
                "symptom_description": "产品温度异常",
                "model_provider": "deepseek",
                "model_name": "deepseek-chat",
                "sensor_stats": None,
                "diagnosis_report": None,
                "next_node": "supervisor",
                "messages": [],
            }

            # 收集最终状态（工作流应正常结束）
            final_chunk = None
            async for chunk in graph.astream(state):
                if isinstance(chunk, dict):
                    final_chunk = chunk

            # 工作流应完成（不抛出异常）
            assert final_chunk is not None


# ============================================================
# 测试组 6：SensorService 异步 CRUD（aiosqlite 环境检查）
# ============================================================

def _check_aiosqlite():
    """检查 aiosqlite 是否可用"""
    try:
        import aiosqlite
        return True
    except ImportError:
        return False


aiosqlite_available = _check_aiosqlite()
needs_aiosqlite = pytest.mark.skipif(
    not aiosqlite_available,
    reason="aiosqlite not available in this environment"
)


@needs_aiosqlite
@pytest.mark.asyncio(loop_scope="class")
class TestSensorServiceCRUD:
    """SensorService 数据库操作测试（仅在 aiosqlite 可用时运行）"""

    async def test_count_returns_integer(self):
        """count() 返回整数类型"""
        from app.services.sensor_service import SensorService
        from app.core.database import get_session_context

        async with get_session_context() as session:
            service = SensorService(session)
            count = await service.count()
            assert isinstance(count, int)
            assert count >= 0

    async def test_get_latest_returns_list(self):
        """get_latest() 返回列表"""
        from app.services.sensor_service import SensorService
        from app.core.database import get_session_context

        async with get_session_context() as session:
            service = SensorService(session)
            records = await service.get_latest(limit=10)
            assert isinstance(records, list)

    async def test_get_by_id_invalid_returns_none(self):
        """get_by_id() 不存在的 ID 返回 None"""
        from app.services.sensor_service import SensorService
        from app.core.database import get_session_context

        async with get_session_context() as session:
            service = SensorService(session)
            record = await service.get_by_id(999999999)
            assert record is None

    async def test_get_by_id_valid_returns_record(self):
        """get_by_id() 存在的 ID 返回记录"""
        from app.services.sensor_service import SensorService
        from app.core.database import get_session_context

        async with get_session_context() as session:
            service = SensorService(session)
            latest = await service.get_latest(limit=1)
            if latest:
                record = await service.get_by_id(latest[0].id)
                assert record is not None
                assert record.id == latest[0].id
