"""LangChain 工具封装模块

本模块将业务服务层封装为可供大模型调用的 LangChain Tool。
每个工具都附带详细的中文文档字符串，供 Agent 理解何时以及如何调用。

【修复记录】
- Bug 1: _aggregate_sensor_stats 使用 pop("sum", None) 避免 KeyError
- Bug 2: 改为原生异步工具 @tool async def，避免 asyncio.run() 事件循环冲突
"""
from datetime import datetime

from langchain_core.tools import tool

from app.db.session import get_session_context
from app.services.sensor_service import SensorService


# 核心传感器字段列表（需要计算统计量的关键字段）
CORE_SENSOR_FIELDS = [
    "dm_pp01_r", "dm_pp01a_d", "dm_pp01a_r", "dm_pp01b_d", "dm_pp01b_r",
    "dm_pp02_d", "dm_pp02_r", "dm_pp04_d", "dm_pp04_ao",
    "dm_ft01", "dm_ft01z", "dm_ft02", "dm_ft02z", "dm_ft03", "dm_ft03z",
    "dm_tit01", "dm_tit02",
    "dm_pit01", "dm_pit01_hh", "dm_pit02",
    "dm_lit01",
    "dm_lcv01_d", "dm_lcv01_z",
    "dm_fcv01_d", "dm_fcv01_z", "dm_fcv02_d", "dm_fcv02_z", "dm_fcv03_d", "dm_fcv03_z",
    "dm_pcv01_d", "dm_pcv01_z", "dm_pcv01_dev", "dm_pcv02_d", "dm_pcv02_z",
    "dm_ait_do", "dm_ait_ph",
    "dm_cool_on", "dm_cool_r",
]


def _aggregate_sensor_stats(records: list) -> dict[str, dict[str, float | None]]:
    """计算核心传感器的统计摘要

    对传入的传感器记录列表，计算各核心字段的统计特征。
    使用原地聚合策略，避免 pandas 依赖，兼容性强。

    Args:
        records: SensorData ORM 对象列表

    Returns:
        以字段名为 key 的统计字典，格式：
        {
            "dm_tit01": {"mean": 45.2, "min": 44.1, "max": 48.9, "count": 300},
            ...
        }
    """
    if not records:
        return {}

    # 初始化聚合结果
    stats: dict[str, dict[str, float | None]] = {
        field: {"mean": None, "min": None, "max": None, "count": 0}
        for field in CORE_SENSOR_FIELDS
    }

    # 遍历每条记录进行聚合
    for record in records:
        for field in CORE_SENSOR_FIELDS:
            value = getattr(record, field, None) if hasattr(record, field) else None

            if value is not None:
                if stats[field]["count"] == 0:
                    # 首次写入
                    stats[field]["min"] = value
                    stats[field]["max"] = value
                    stats[field]["sum"] = value
                    stats[field]["count"] = 1
                else:
                    # 增量更新
                    stats[field]["sum"] = stats[field]["sum"] + value  # type: ignore
                    stats[field]["min"] = min(stats[field]["min"], value)  # type: ignore
                    stats[field]["max"] = max(stats[field]["max"], value)  # type: ignore
                    stats[field]["count"] = stats[field]["count"] + 1  # type: ignore

    # 计算平均值并清理临时字段（使用 pop 避免 KeyError）
    for field in CORE_SENSOR_FIELDS:
        if stats[field]["count"] > 0:
            stats[field]["mean"] = round(stats[field]["sum"] / stats[field]["count"], 4)  # type: ignore
        # Bug 1 fix: pop 不存在的键不会抛 KeyError
        stats[field].pop("sum", None)

    return stats


def _format_stats_as_text(
    stats: dict[str, dict[str, float | None]],
    time_range: str,
    record_count: int
) -> str:
    """将统计字典格式化为易读的文本摘要"""
    if not stats or all(s["count"] == 0 for s in stats.values()):
        return f"时间范围内无有效传感器数据记录。\n时间范围: {time_range}"

    lines = [
        "【传感器统计摘要】",
        f"时间范围: {time_range}",
        f"原始记录条数: {record_count}",
        "",
    ]

    field_descriptions = {
        "dm_pp01_r": "主泵运行状态",
        "dm_pp01a_d": "主泵A开度", "dm_pp01a_r": "主泵A转速",
        "dm_pp01b_d": "主泵B开度", "dm_pp01b_r": "主泵B转速",
        "dm_pp02_d": "泵2开度", "dm_pp02_r": "泵2转速",
        "dm_pp04_d": "泵4开度", "dm_pp04_ao": "泵4输出",
        "dm_ft01": "流量计1", "dm_ft01z": "流量计1(mA)",
        "dm_ft02": "流量计2", "dm_ft02z": "流量计2(mA)",
        "dm_ft03": "流量计3", "dm_ft03z": "流量计3(mA)",
        "dm_tit01": "温度传感器1", "dm_tit02": "温度传感器2",
        "dm_pit01": "压力传感器1", "dm_pit01_hh": "压力高报", "dm_pit02": "压力传感器2",
        "dm_lit01": "液位传感器1",
        "dm_lcv01_d": "阀LCV01开度", "dm_lcv01_z": "阀LCV01位置",
        "dm_fcv01_d": "阀FCV01开度", "dm_fcv01_z": "阀FCV01位置",
        "dm_fcv02_d": "阀FCV02开度", "dm_fcv02_z": "阀FCV02位置",
        "dm_fcv03_d": "阀FCV03开度", "dm_fcv03_z": "阀FCV03位置",
        "dm_pcv01_d": "PCV01开度", "dm_pcv01_z": "PCV01位置",
        "dm_pcv01_dev": "PCV01偏差", "dm_pcv02_d": "PCV02开度", "dm_pcv02_z": "PCV02位置",
        "dm_ait_do": "溶解氧", "dm_ait_ph": "pH值",
        "dm_cool_on": "冷却系统", "dm_cool_r": "冷却回流",
    }

    field_units = {
        "dm_tit01": "°C", "dm_tit02": "°C",
        "dm_pit01": "kPa", "dm_pit01_hh": "kPa", "dm_pit02": "kPa",
        "dm_ft01": "L/h", "dm_ft01z": "mA", "dm_ft02": "L/h", "dm_ft02z": "mA",
        "dm_ft03": "L/h", "dm_ft03z": "mA",
        "dm_lit01": "%",
        "dm_cool_on": "", "dm_cool_r": "",
        "dm_ait_do": "mg/L", "dm_ait_ph": "",
    }

    for field, desc in field_descriptions.items():
        s = stats.get(field)
        if s and s["count"] > 0:
            unit = field_units.get(field, "")
            unit_str = f" {unit}" if unit else ""
            mean_val = f"{s['mean']:.2f}" if s["mean"] is not None else "N/A"
            min_val = f"{s['min']:.2f}" if s["min"] is not None else "N/A"
            max_val = f"{s['max']:.2f}" if s["max"] is not None else "N/A"
            lines.append(
                f"  {desc}({field}): 均值={mean_val}{unit_str}, "
                f"最小={min_val}{unit_str}, 最大={max_val}{unit_str}"
            )

    if len(lines) == 3:
        lines.append("  （该时间段内有数据，但核心字段均为空）")

    return "\n".join(lines)


@tool
async def get_sensor_data_by_time_range(
    start_time: str,
    end_time: str,
    limit: int = 5000
) -> str:
    """获取指定时间范围内工业传感器的统计摘要

    本工具用于查询 HAI 工业时序数据库中特定时间段的传感器读数。
    **重要：为了适应大模型的上下文窗口限制，本工具返回的是统计摘要而非原始波形数据。**

    该工具会自动计算以下统计特征：
    - **平均值(mean)**：反映正常运行时的基准水平
    - **最小值(min)**：反映异常偏低或报警阈值
    - **最大值(max)**：反映异常偏高或报警阈值

    通过这些统计量，Agent 可以快速判断：
    - 某传感器是否偏离正常范围
    - 是否存在剧烈波动（min/max 差异大）
    - 是否持续处于报警状态（mean 接近报警值）

    **入参格式要求**：
    - `start_time`: 起始时间，格式为 "YYYY-MM-DD HH:MM:SS"（例如 "2022-08-12 16:00:00"）
    - `end_time`: 结束时间，格式为 "YYYY-MM-DD HH:MM:SS"
    - `limit`: 最大查询记录数，默认 5000 条

    **返回数据格式**：
    返回一个文本格式的统计摘要报告，包含：
    - 时间范围和原始记录条数
    - 各核心传感器字段的均值、最小值、最大值
    - 数值已标注单位（°C, kPa, L/h, %, mg/L 等）

    **典型使用场景**：
    - "分析 2022-08-12 14:00 到 15:00 的设备运行状态"
    - "检查下午时段的压力和温度是否有异常"
    - "查看某个时间段内是否存在阀门频繁动作"

    **注意事项**：
    - 返回的是统计摘要，**不是**秒级原始序列
    - 如果时间范围内数据量超过 limit，会截断后计算，可能影响统计准确性
    - extra_sensors（NNNN.OUT 系列）中的辅助字段不参与统计聚合

    Args:
        start_time: 查询起始时间，格式 "YYYY-MM-DD HH:MM:SS"
        end_time: 查询结束时间，格式 "YYYY-MM-DD HH:MM:SS"
        limit: 最大返回记录数，默认 5000

    Returns:
        格式化的文本统计摘要报告
    """
    # 解析时间字符串
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        return f"时间格式错误: {e}。请使用格式 'YYYY-MM-DD HH:MM:SS'，例如 '2022-08-12 16:00:00'"

    try:
        # Bug 2 fix: 直接使用 await 调用异步数据库查询，不再用 asyncio.run()
        async with get_session_context() as session:
            service = SensorService(session)
            records = await service.get_sensor_data_by_time_range(
                start=start_dt,
                end=end_dt,
                limit=limit
            )

            if not records:
                return _format_stats_as_text(
                    stats={},
                    time_range=f"{start_time} 至 {end_time}",
                    record_count=0
                )

            # 计算统计摘要
            stats = _aggregate_sensor_stats(records)

            return _format_stats_as_text(
                stats=stats,
                time_range=f"{start_time} 至 {end_time}",
                record_count=len(records)
            )

    except Exception as e:
        return f"查询执行失败: {str(e)}"
