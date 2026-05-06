"""多智能体共享状态类型定义

避免循环导入：将 DiagnosisState 独立定义，
供 graph.py 和 nodes/ 下的所有节点文件导入使用。
"""
from typing import Literal, TypedDict


class DiagnosisState(TypedDict):
    """多智能体共享诊断状态

    所有节点读写同一份状态字典，实现无间协作。

    Attributes:
        start_time: 异常时间窗口起始
        end_time: 异常时间窗口结束
        symptom_description: 用户描述的症状（可选）
        model_provider: LLM 提供商
        model_name: LLM 模型名称
        sensor_stats: Data Analyst 查询到的统计摘要
        diagnosis_report: Diagnosis Expert 生成的最终报告
        next_node: Supervisor 决定的下一个节点
        messages: 对话消息历史
    """

    start_time: str
    end_time: str
    symptom_description: str | None
    model_provider: str
    model_name: str | None
    sensor_stats: str | None
    diagnosis_report: str | None
    next_node: Literal["supervisor", "data_analyst", "diagnosis_expert", "__end__"]
    messages: list
