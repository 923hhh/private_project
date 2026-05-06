"""LangGraph 多智能体诊断工作流

基于 LangGraph StateGraph 的多智能体协作架构:

    ┌──────────────────────────────────────┐
    │           Supervisor                  │
    │   (入口路由，判断下一步执行哪个节点)    │
    └──────┬───────────────────┬───────────┘
           │                   │
           ▼                   ▼
    ┌─────────────┐    ┌──────────────┐
    │Data Analyst │───▶│Diagnosis Expert│
    │ (查询统计)   │    │  (生成报告)    │
    └─────────────┘    └──────────────┘

状态流向:
1. Supervisor 路由至 Data Analyst
2. Data Analyst 查询传感器数据 → Supervisor
3. Supervisor 路由至 Diagnosis Expert
4. Diagnosis Expert 生成报告 → Supervisor → END
"""
from langgraph.graph import END, StateGraph

from app.agents.state import DiagnosisState
from app.agents.nodes import (
    diagnosis_expert_node,
    data_analyst_node,
    supervisor_node,
)


# ============================================================
# 构建工作流图
# ============================================================

def _build_graph() -> StateGraph:
    """构建多智能体诊断工作流图

    Returns:
        编译好的 LangGraph StateGraph
    """
    # 创建状态图，指定状态类型
    workflow = StateGraph(DiagnosisState)

    # 注册节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("data_analyst", data_analyst_node)
    workflow.add_node("diagnosis_expert", diagnosis_expert_node)

    # 设置入口点
    workflow.set_entry_point("supervisor")

    # 定义条件路由边：Supervisor → 根据 next_node 决定后续节点
    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state.get("next_node", "__end__"),
        path_map={
            "data_analyst": "data_analyst",
            "diagnosis_expert": "diagnosis_expert",
            "__end__": END,
        },
    )

    # Data Analyst 完成后回到 Supervisor
    workflow.add_edge("data_analyst", "supervisor")

    # Diagnosis Expert 完成后回到 Supervisor（再次判断是否结束）
    workflow.add_edge("diagnosis_expert", "supervisor")

    # 编译为可执行图
    return workflow.compile()


# 全局编译后的图实例（惰性初始化）
_compiled_graph = None


def get_diagnosis_graph() -> StateGraph:
    """获取编译后的多智能体诊断图

    Returns:
        编译好的 StateGraph 实例
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ============================================================
# 对外执行入口
# ============================================================

async def run_multi_agent_diagnosis(
    start_time: str,
    end_time: str,
    symptom_description: str | None = None,
    model_provider: str = "openai",
    model_name: str | None = None,
) -> str:
    """多智能体诊断入口

    创建初始状态，启动 LangGraph 工作流，返回最终诊断报告。

    Args:
        start_time: 异常时间窗口起始
        end_time: 异常时间窗口结束
        symptom_description: 用户描述的症状（可选）
        model_provider: LLM 提供商
        model_name: LLM 模型名称

    Returns:
        最终诊断报告字符串
    """
    # 构建初始状态
    initial_state: DiagnosisState = {
        "start_time": start_time,
        "end_time": end_time,
        "symptom_description": symptom_description,
        "model_provider": model_provider,
        "model_name": model_name,
        "sensor_stats": None,
        "diagnosis_report": None,
        "next_node": "supervisor",
        "messages": [],
    }

    # 获取编译后的图
    graph = get_diagnosis_graph()

    # 执行工作流（异步模式）
    final_state = await graph.ainvoke(initial_state)

    # 返回最终报告
    return final_state.get("diagnosis_report") or "诊断流程异常，未生成报告。"
