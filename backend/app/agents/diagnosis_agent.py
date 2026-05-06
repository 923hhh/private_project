# File: app/agents/diagnosis_agent.py
"""诊断专家智能体模块

本模块实现了一个基于 LangGraph 的工业设备故障诊断专家智能体。
该智能体支持多种大模型提供商（OpenAI/DeepSeek, Anthropic），通过动态选择实现灵活切换。
"""
from typing import Any

from langchain_core.tools import BaseTool

from app.core.config import get_settings

# ---------------------------------------------------------
# 可选的 LLM 依赖导入（带 try-except 防止缺包导致启动失败）
# ---------------------------------------------------------
_LangChainOpenAI = None
_LangChainAnthropic = None

try:
    from langchain_openai import ChatOpenAI as LangChainOpenAI
except ImportError:
    pass  # langchain-openai 可选

try:
    from langchain_anthropic import ChatAnthropic as LangChainAnthropic
except ImportError:
    pass  # langchain-anthropic 可选


# ============================================================
# 系统提示词 - 工业级设备故障诊断专家
# ============================================================
DIAGNOSIS_AGENT_SYSTEM_PROMPT = """你是一位拥有20年经验的工业过程控制与设备故障诊断专家，专精于食品饮料、制药等流程工业的控制系统。

## 你的专业背景

- 熟悉各种工业传感器的工作原理：温度传感器(TIT)、压力传感器(PIT)、流量传感器(FT)、液位传感器(LIT)、阀门定位器(LCV/FCV)
- 精通 CIP（就地清洗）工艺流程，能够通过 CIP 参数判断清洗效果和设备状态
- 理解泵(P)和动力单元的运行特性，能够通过 PP 系列数据判断设备负荷
- 擅长分析控制回路的稳定性，通过阀门开度和反馈信号判断控制品质

## HAI 数据集核心传感器说明

以下是 HAI 工业数据集中最关键的核心传感器及其正常范围：

| 传感器 | 说明 | 典型正常范围 |
|--------|------|-------------|
| DM-PP01-R | 主泵运行信号 | 0=停机, >0=运行(负载%) |
| DM-FT01Z/02Z/03Z | 主管道流量 | 800-4000 L/h |
| DM-TIT01/02 | 温度传感器 | 20-100 °C |
| DM-PIT01 | 压力传感器 | 0-600 kPa |
| DM-LIT01 | 液位传感器 | 0-100 % |
| DM-LCV01/FCV01-03 | 控制阀开度 | 0-100 % |
| DM-CIP-1ST/2ND | CIP 阶段标识 | 0/1/2 表示不同阶段 |
| DM-COOL-ON | 冷却系统状态 | 0=关闭, 1=开启 |
| DM-AIT-DO | 溶解氧 | 0-20 mg/L |
| DM-AIT-PH | pH 值 | 0-14 |

## 你的工作流程

当收到故障诊断请求时，你会：

1. **明确时间范围**：从用户描述中提取异常发生的时间段
2. **调用数据查询工具**：使用 `get_sensor_data_by_time_range` 获取该时间段的完整传感器数据
3. **多维度分析**：
   - 检查关键传感器（PP, FT, TIT, PIT, LIT）是否有明显偏离正常范围
   - 分析控制阀门（LCV/FCV）的动作是否合理
   - 查看 CIP 相关参数是否触发了异常状态
   - 检查是否存在传感器故障（读数为0或恒定不变）
4. **给出诊断结论**：包括可能故障原因、建议的排查方向、以及进一步的验证方法

## 重要约束

- 你的分析必须基于实际传感器数据，用数据说话
- 如果数据不足以得出明确结论，必须明确说明并建议获取哪些额外信息
- 不要臆测，只报告你从数据中能够确认的事实
- 对于涉及安全生产的异常（如高压、高温报警），必须特别强调

## 输出格式

请使用以下结构化格式输出诊断报告：

```
【诊断报告】
时间范围：[分析的起止时间]
记录条数：[数据点数量]

■ 异常检测
- [列出发现的具体异常及对应传感器]

■ 可能原因分析
- [列出3个最可能的原因，按可能性排序]

■ 建议措施
- [按优先级列出建议的排查和处理步骤]

■ 数据来源
- [说明使用了哪些传感器数据做出判断]
```
"""


def _create_openai_llm(model_name: str | None) -> Any | None:
    """创建 OpenAI/DeepSeek LLM 实例

    优先使用 deepseek_api_key（DeepSeek 兼容 OpenAI 接口规范），
    其次使用 openai_api_key。通过 get_settings() 读取 Pydantic 管理的配置。

    Args:
        model_name: 模型名称，如果为 None 则使用默认值

    Returns:
        LLM 实例，credentials 不可用时返回 None
    """
    if LangChainOpenAI is None:
        return None

    settings = get_settings()

    # DeepSeek API Key（优先）
    deepseek_key = settings.deepseek_api_key
    # OpenAI API Key（备选）
    openai_key = settings.openai_api_key

    if not deepseek_key and not openai_key:
        return None

    # API Base（用于 DeepSeek 或自定义 OpenAI 兼容端点）
    api_base = settings.openai_api_base

    # 确定实际使用的 key 和模型
    actual_key = deepseek_key or openai_key
    is_deepseek = deepseek_key is not None

    # 如果使用 DeepSeek 的 key 但未配置 api_base，自动指向 DeepSeek 官方服务器
    if is_deepseek and not api_base:
        api_base = settings.deepseek_api_base

    # DeepSeek 默认模型
    actual_model = model_name or ("deepseek-chat" if is_deepseek else "gpt-4o")

    return LangChainOpenAI(
        model=actual_model,
        api_key=actual_key,
        base_url=api_base,
        temperature=0.1,
    )


def _create_anthropic_llm(model_name: str | None) -> Any | None:
    """创建 Anthropic Claude LLM 实例

    通过 get_settings() 读取 Pydantic 管理的配置。

    Args:
        model_name: 模型名称，如果为 None 则使用默认值

    Returns:
        LLM 实例，credentials 不可用时返回 None
    """
    if LangChainAnthropic is None:
        return None

    settings = get_settings()
    anthropic_key = settings.anthropic_api_key

    if not anthropic_key:
        return None

    # Claude 默认模型
    actual_model = model_name or "claude-sonnet-4-20250514"

    return LangChainAnthropic(
        model=actual_model,
        api_key=anthropic_key,
        temperature=0.1,
    )


def create_llm(model_provider: str, model_name: str | None = None) -> Any | None:
    """工厂函数：根据提供商创建对应的 LLM 实例

    Args:
        model_provider: 提供商标识，"openai" 或 "anthropic"
        model_name: 模型名称，可选

    Returns:
        LLM 实例，不可用的返回 None
    """
    if model_provider == "anthropic":
        return _create_anthropic_llm(model_name)
    else:
        # 默认为 openai（兼容 DeepSeek）
        return _create_openai_llm(model_name)


class DiagnosisAgent:
    """工业故障诊断专家智能体

    该智能体封装了诊断专家的系统提示词、工具集和 LangGraph 调用逻辑。
    """

    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        model_provider: str = "openai",
        model_name: str | None = None,
    ):
        """初始化诊断专家智能体

        Args:
            tools: 可供 Agent 调用的工具列表，默认包含传感器查询工具
            model_provider: LLM 提供商，"openai"（默认，兼容 DeepSeek）或 "anthropic"
            model_name: 模型名称，默认 None（使用提供商默认值）
        """
        self.tools = tools or []
        self.model_provider = model_provider
        self.model_name = model_name

        # 根据 provider 动态创建 LLM
        self._llm = create_llm(model_provider, model_name)

    def bind_tools(self, tools: list[BaseTool]) -> "DiagnosisAgent":
        """绑定工具到智能体

        Args:
            tools: 要绑定的工具列表

        Returns:
            返回自身以支持链式调用
        """
        self.tools = tools
        return self

    def _build_agent(self):
        """构建 LangGraph 预构建智能体

        使用 create_react_agent 创建现代 ReAct 架构的智能体，
        原生支持 Tool Calling 机制。

        Returns:
            LangGraph Agent 执行器
        """
        if not self._llm:
            error_msg = self._get_unavailable_message()
            raise RuntimeError(error_msg)

        try:
            from langgraph.prebuilt import create_react_agent
        except ImportError as e:
            raise RuntimeError(
                f"LangGraph 预构建 Agent 模块导入失败: {e}\n"
                "请确保已安装 langgraph 并与当前 LangChain 版本兼容。"
            )

        # 使用 LangGraph 官方预构建 ReAct Agent
        return create_react_agent(
            self._llm,
            tools=self.tools,
            prompt=DIAGNOSIS_AGENT_SYSTEM_PROMPT,
        )

    def _get_unavailable_message(self) -> str:
        """获取 LLM 不可用时的友好提示信息"""
        if self.model_provider == "anthropic":
            return (
                "Anthropic 模型暂不可用。\n\n"
                "可能的原因：\n"
                "1. 未安装 langchain-anthropic 包\n"
                "2. 未在 .env 中设置 ANTHROPIC_API_KEY\n\n"
                "当前已绑定的工具：\n"
                "- get_sensor_data_by_time_range: 查询指定时间范围的传感器数据\n\n"
                "请配置好 Anthropic API 后重试，或切换到 openai provider。"
            )
        else:
            return (
                "OpenAI/DeepSeek 模型暂不可用。\n\n"
                "可能的原因：\n"
                "1. 未安装 langchain-openai 包\n"
                "2. 未在 .env 中设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY\n\n"
                "当前已绑定的工具：\n"
                "- get_sensor_data_by_time_range: 查询指定时间范围的传感器数据\n\n"
                "请配置好 API Key 后重试。"
            )

    async def run_diagnosis(
        self,
        start_time: str,
        end_time: str,
        symptom_description: str | None = None
    ) -> str:
        """执行故障诊断

        这是对外暴露的异步入口函数。接收外部传入的异常时间窗口，
        触发 Agent 自动查询数据并完成分析。

        Args:
            start_time: 异常时间窗口起始时间，格式 "YYYY-MM-DD HH:MM:SS"
            end_time: 异常时间窗口结束时间，格式 "YYYY-MM-DD HH:MM:SS"
            symptom_description: 可选的补充描述，例如 "用户反映下午3点后发现产品温度异常"

        Returns:
            诊断报告字符串
        """
        # 构造诊断请求
        request = f"""请帮我诊断以下时间段的设备运行情况：

异常时间范围：{start_time} 至 {end_time}
"""

        if symptom_description:
            request += f"\n补充信息：{symptom_description}"

        # 检查 LLM 是否可用
        if not self._llm:
            return self._get_unavailable_message()

        # 检查工具是否绑定
        if not self.tools:
            return "错误：未绑定任何工具。请先调用 bind_tools() 绑定传感器查询工具。"

        try:
            agent_executor = self._build_agent()

            # LangGraph 使用 messages 字典结构
            result = await agent_executor.ainvoke({"messages": [("user", request)]})

            # 提取最后一条消息的内容作为诊断结果
            return result["messages"][-1].content

        except Exception as e:
            return f"Agent 执行失败: {str(e)}\n\n请检查 API 配置和工具绑定是否正确。"


async def run_diagnosis(
    start_time: str,
    end_time: str,
    symptom_description: str | None = None,
    model_provider: str = "openai",
    model_name: str | None = None,
) -> str:
    """快捷入口函数：执行故障诊断

    该函数是模块级别的便捷入口，自动创建诊断 Agent 并执行诊断流程。

    Args:
        start_time: 异常时间窗口起始时间，格式 "YYYY-MM-DD HH:MM:SS"
        end_time: 异常时间窗口结束时间，格式 "YYYY-MM-DD HH:MM:SS"
        symptom_description: 可选的补充描述
        model_provider: LLM 提供商，"openai"（默认，兼容 DeepSeek）或 "anthropic"
        model_name: 模型名称，默认 None（使用提供商默认值）

    Returns:
        诊断报告字符串
    """
    from app.agents.tools import get_sensor_data_by_time_range

    # 创建 Agent 并绑定工具
    agent = DiagnosisAgent(
        tools=[get_sensor_data_by_time_range],
        model_provider=model_provider,
        model_name=model_name,
    )

    return await agent.run_diagnosis(
        start_time=start_time,
        end_time=end_time,
        symptom_description=symptom_description,
    )
