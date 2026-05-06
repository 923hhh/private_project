"""Supervisor 节点 - 任务路由与意图识别

Supervisor 是多智能体工作流的入口和中央调度器：
1. 解析用户请求，判断是否需要查询数据
2. 根据当前状态决定下一个执行的节点
3. 维护工作流状态直到输出最终报告

【修复记录】
- Bug 3: build_supervisor_prompt 补充中文输出强制要求
"""
from app.agents.state import DiagnosisState


def supervisor_node(state: DiagnosisState) -> DiagnosisState:
    """Supervisor 路由决策节点

    基于当前状态决定下一个执行的节点：
    - 若尚未获取传感器数据 → 路由至 data_analyst
    - 若已有传感器数据 → 路由至 diagnosis_expert
    - 若已有诊断报告 → 结束

    Args:
        state: 共享的诊断状态字典

    Returns:
        更新后的状态，包含 next_node 路由指令
    """
    # 首次进入：用户刚提交诊断请求
    if state.get("sensor_stats") is None and state.get("diagnosis_report") is None:
        return {"next_node": "data_analyst"}

    # Data Analyst 已完成数据查询，路由至 Diagnosis Expert
    if state.get("sensor_stats") is not None and state.get("diagnosis_report") is None:
        return {"next_node": "diagnosis_expert"}

    # Diagnosis Expert 已完成，流程结束
    return {"next_node": "__end__"}


def build_supervisor_prompt(state: DiagnosisState) -> str:
    """构建 Supervisor 的分析提示词

    当需要调用 LLM 进行复杂路由判断时使用（当前版本使用确定性路由）。

    Args:
        state: 当前诊断状态

    Returns:
        Supervisor 分析提示词（全部中文）
    """
    start = state.get("start_time", "未知")
    end = state.get("end_time", "未知")
    symptom = state.get("symptom_description") or "未提供"
    has_data = state.get("sensor_stats") is not None

    return f"""你是一名工业故障诊断任务调度专家。请使用中文进行所有分析和输出。

当前诊断请求：
- 时间范围：{start} 至 {end}
- 用户症状描述：{symptom}
- 传感器数据状态：{"已获取" if has_data else "待获取"}
- 诊断报告状态：{"已生成" if state.get("diagnosis_report") else "待生成"}

请决定下一步操作（请直接输出节点名称，全部使用中文）：
1. 若传感器数据尚未获取，输出：数据分析师
2. 若数据已获取但诊断报告未生成，输出：诊断专家
3. 若诊断报告已生成，输出：结束

只输出节点名称，不需要其他解释。所有输出必须100%使用中文。"""
