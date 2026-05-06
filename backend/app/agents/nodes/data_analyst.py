"""Data Analyst 节点 - 传感器数据查询与统计分析

该节点负责:
1. 调用 get_sensor_data_by_time_range 工具获取传感器统计数据
2. 将原始统计数据存入共享状态，供后续 Diagnosis Expert 使用

【修复记录】
- Bug 2: 改为 async def，配合 @tool async def，避免 asyncio.run() 冲突
"""
from app.agents.state import DiagnosisState
from app.agents.tools import get_sensor_data_by_time_range


async def data_analyst_node(state: DiagnosisState) -> DiagnosisState:
    """Data Analyst 节点 - 查询并分析传感器统计数据

    调用 LangChain Tool 获取指定时间范围的传感器统计摘要，
    将结果存入状态后返回，由 Supervisor 决定下一步操作。

    Args:
        state: 共享诊断状态，包含 start_time, end_time

    Returns:
        更新后的状态，包含 sensor_stats
    """
    start_time = state.get("start_time", "")
    end_time = state.get("end_time", "")

    if not start_time or not end_time:
        return {
            "sensor_stats": "错误：未提供有效的时间范围参数。",
        }

    try:
        # Bug 2 fix: 使用 ainvoke() 调用异步工具
        sensor_stats = await get_sensor_data_by_time_range.ainvoke({
            "start_time": start_time,
            "end_time": end_time,
            "limit": 5000,
        })

        return {
            "sensor_stats": sensor_stats,
        }

    except Exception as e:
        return {
            "sensor_stats": f"传感器数据查询失败: {str(e)}",
        }
