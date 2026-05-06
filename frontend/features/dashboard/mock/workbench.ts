import type {
  WorkbenchOverview,
  MaintenanceTaskHistoryResponse,
  MaintenanceTaskDetail,
  MaintenanceCaseListResponse,
  MaintenanceCaseDetail,
} from "@/features/dashboard/api"

function isoMinutesAgo(minutes: number) {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

export function demoHealth() {
  return { status: "healthy", database: "connected" }
}

export function demoSystemMetrics() {
  const now = new Date().toISOString()
  return {
    generated_at: now,
    counters: [
      { name: "http_requests_total", labels: { path: "/health", status_code: "200" }, value: 1280 },
      { name: "http_requests_total", labels: { path: "/api/v1/workbench/overview", status_code: "200" }, value: 356 },
      { name: "http_requests_total", labels: { path: "/api/v1/history", status_code: "200" }, value: 241 },
      { name: "http_requests_total", labels: { path: "/api/v1/cases", status_code: "200" }, value: 188 },
    ],
    durations: [
      { name: "http_request_duration_ms", count: 1280, avg_ms: 18.4 },
      { name: "db_query_duration_ms", count: 760, avg_ms: 12.1 },
    ],
  }
}

export function demoWorkbenchOverview(): WorkbenchOverview {
  const generated_at = new Date().toISOString()
  return {
    generated_at,
    stats: [
      { key: "device_total", label: "设备总数", value: 128, accent: "neutral" },
      { key: "device_online", label: "在线设备", value: 121, accent: "success" },
      { key: "alerts_open", label: "故障告警", value: 7, accent: "warning" },
      { key: "handled_today", label: "今日已处理", value: 15, accent: "success" },
    ],
    featured_queries: [
      "空压机 ERR-102 报错，伴随异常振动",
      "CNC 主轴温升异常，疑似润滑不足",
      "泵组压力波动，阀门有异响",
    ],
    agent_capabilities: ["故障诊断", "SOP 推荐", "知识检索", "工单生成", "案例沉淀"],
    recent_tasks: [
      {
        id: 1024,
        title: "CMP-102 空压机 ERR-102 频繁告警",
        work_order_id: "WO-20260424-001",
        asset_code: "CMP-102",
        equipment_type: "压缩机",
        equipment_model: "DM-AC200",
        maintenance_level: "emergency",
        status: "in_progress",
        total_steps: 5,
        completed_steps: 3,
        created_at: isoMinutesAgo(120),
        updated_at: isoMinutesAgo(8),
      },
      {
        id: 1021,
        title: "PUMP-07 压力波动与噪声异常",
        work_order_id: "WO-20260424-002",
        asset_code: "PUMP-07",
        equipment_type: "泵组",
        equipment_model: "DM-P300",
        maintenance_level: "standard",
        status: "pending",
        total_steps: 5,
        completed_steps: 1,
        created_at: isoMinutesAgo(260),
        updated_at: isoMinutesAgo(64),
      },
      {
        id: 1008,
        title: "CNC-21 主轴温升异常复核",
        work_order_id: null,
        asset_code: "CNC-21",
        equipment_type: "数控机床",
        equipment_model: "DM-CNCX",
        maintenance_level: "routine",
        status: "completed",
        total_steps: 5,
        completed_steps: 5,
        created_at: isoMinutesAgo(1440),
        updated_at: isoMinutesAgo(1380),
      },
    ],
    recent_cases: [
      {
        id: 18,
        title: "ERR-102 传感器供电异常导致振动误报",
        status: "approved",
        equipment_type: "压缩机",
        updated_at: isoMinutesAgo(600),
      },
      {
        id: 21,
        title: "泵组压力波动：旁通阀卡滞处理案例",
        status: "approved",
        equipment_type: "泵组",
        updated_at: isoMinutesAgo(820),
      },
      {
        id: 33,
        title: "CNC 主轴温升：润滑系统堵塞排查",
        status: "pending",
        equipment_type: "数控机床",
        updated_at: isoMinutesAgo(980),
      },
    ],
  }
}

export function demoMaintenanceHistory(): MaintenanceTaskHistoryResponse {
  return {
    total: 23,
    tasks: [
      {
        id: 1024,
        title: "CMP-102 空压机 ERR-102 频繁告警",
        equipment_type: "压缩机",
        equipment_model: "DM-AC200",
        status: "in_progress",
        maintenance_level: "emergency",
        total_steps: 5,
        completed_steps: 3,
        created_at: isoMinutesAgo(120),
        updated_at: isoMinutesAgo(8),
      },
      {
        id: 1021,
        title: "PUMP-07 压力波动与噪声异常",
        equipment_type: "泵组",
        equipment_model: "DM-P300",
        status: "pending",
        maintenance_level: "standard",
        total_steps: 5,
        completed_steps: 1,
        created_at: isoMinutesAgo(260),
        updated_at: isoMinutesAgo(64),
      },
      {
        id: 1008,
        title: "CNC-21 主轴温升异常复核",
        equipment_type: "数控机床",
        equipment_model: "DM-CNCX",
        status: "completed",
        maintenance_level: "routine",
        total_steps: 5,
        completed_steps: 5,
        created_at: isoMinutesAgo(1440),
        updated_at: isoMinutesAgo(1380),
      },
      {
        id: 1003,
        title: "VFD-05 过载保护触发排查",
        equipment_type: "变频器",
        equipment_model: "DM-V900",
        status: "completed",
        maintenance_level: "standard",
        total_steps: 5,
        completed_steps: 5,
        created_at: isoMinutesAgo(2400),
        updated_at: isoMinutesAgo(2320),
      },
    ],
  }
}

export function demoTaskDetail(taskId: number): MaintenanceTaskDetail {
  const base: MaintenanceTaskDetail = {
    id: taskId,
    title: `检修任务 #${taskId}`,
    work_order_id: `WO-20260424-${String(taskId).slice(-3).padStart(3, "0")}`,
    asset_code: "CMP-102",
    report_source: "demo",
    priority: "high",
    equipment_type: "压缩机",
    equipment_model: "DM-AC200",
    maintenance_level: "emergency",
    fault_type: "ERR-102",
    symptom_description: "压缩机 ERR-102 报错，伴随异常振动与温升，告警频率上升。",
    status: "in_progress",
    total_steps: 5,
    completed_steps: 3,
    advice_card:
      "建议优先检查传感器供电与端子紧固，其次核对振动采样线屏蔽与接地；对比历史案例 ERR-102 供电端子松动导致误报。",
    created_at: isoMinutesAgo(120),
    updated_at: isoMinutesAgo(8),
    steps: [
      { id: 1, title: "读取传感器统计摘要", status: "done" },
      { id: 2, title: "检索相关知识条目", status: "done" },
      { id: 3, title: "生成疑似原因与处理建议", status: "in_progress" },
      { id: 4, title: "生成可执行 SOP", status: "pending" },
      { id: 5, title: "输出诊断结论并推荐工单", status: "pending" },
    ],
    execution_timeline: [
      {
        id: "evt-1",
        type: "fault",
        title: "检测到 ERR-102 告警频率升高",
        description: "振动均值上升 18%，温升速率高于基线",
        time: isoMinutesAgo(18),
      },
      {
        id: "evt-2",
        type: "analysis",
        title: "命中知识条目：ERR-102 供电端子松动",
        description: "相似案例引用 23 次，推荐检查端子与供电稳定性",
        time: isoMinutesAgo(14),
      },
      {
        id: "evt-3",
        type: "recommendation",
        title: "生成处理建议与备件清单",
        description: "紧固端子、检查屏蔽线、必要时更换传感器模块",
        time: isoMinutesAgo(9),
      },
    ],
  }
  return base
}

export function demoCasesList(): MaintenanceCaseListResponse {
  return {
    total: 356,
    cases: [
      {
        id: 18,
        title: "ERR-102 传感器供电异常处理案例",
        equipment_type: "压缩机",
        status: "approved",
        symptom_description: "报警频繁，振动波动明显",
        updated_at: isoMinutesAgo(600),
      },
      {
        id: 21,
        title: "泵组压力波动：旁通阀卡滞处理案例",
        equipment_type: "泵组",
        status: "approved",
        symptom_description: "压力曲线锯齿状波动，伴随异响",
        updated_at: isoMinutesAgo(820),
      },
      {
        id: 33,
        title: "CNC 主轴温升：润滑系统堵塞排查",
        equipment_type: "数控机床",
        status: "pending",
        symptom_description: "温升过快，负载波动",
        updated_at: isoMinutesAgo(980),
      },
    ],
  }
}

export function demoCaseDetail(caseId: number): MaintenanceCaseDetail {
  return {
    id: caseId,
    title: "ERR-102 传感器供电异常处理案例",
    equipment_type: "压缩机",
    equipment_model: "DM-AC200",
    symptom_description: "报警频繁，振动数据波动明显，偶发温升告警。",
    processing_steps: [
      "检查传感器供电电压是否稳定（波动范围 ≤ ±5%）",
      "检查端子与接线是否松动，重新压接并固定",
      "核对屏蔽线接地与走线，避免强电干扰",
      "复测振动基线并进行校准",
    ],
    resolution_summary: "供电端子松动导致瞬时掉电，恢复紧固并校准后告警消失。",
    status: "approved",
    knowledge_refs: [
      { type: "manual", title: "ERR-102 故障处理手册", id: "KB-M-102" },
      { type: "case", title: "CMP-102 传感器异常（历史案例）", id: "CASE-018" },
      { type: "sop", title: "振动传感器校准 SOP", id: "SOP-VC-01" },
    ],
  }
}

