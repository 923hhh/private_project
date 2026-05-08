"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useMaintenanceAuth } from "@/features/auth/maintenance-auth";
import {
  canDeleteWorkOrder,
} from "@/features/auth/permissions";
import {
  deleteWorkOrder,
  isMaintenanceAuthExpiredError,
  listWorkOrders,
  fetchMaintenanceHealth,
  listMaintenanceDevices,
  type MaintenanceDeviceItem,
  type MaintenanceUser,
} from "@/features/tickets/api";
import { DEMO_MODE_CHANGED_EVENT, isDemoMode } from "@/shared/lib/demo-mode";
import { getMaintenanceToken } from "@/features/auth/lib/token-store";
import {
  Search,
  Filter,
  Plus,
  ChevronDown,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  MoreHorizontal,
  User,
  Calendar,
  Tag,
  ArrowLeft,
  RefreshCw,
  SortAsc,
  SortDesc,
  Trash2,
} from "lucide-react";
import { Header } from "@/shared/components/brand/app-header";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";

// 工单数据类型
interface Ticket {
  id: string;
  title: string;
  description: string;
  priority: "emergency" | "standard" | "routine" | "unknown";
  status:
    | "S1"
    | "S2"
    | "S3"
    | "S4"
    | "S5"
    | "S6"
    | "S7"
    | "S8"
    | "S9"
    | "S10"
    | "SX";
  assignee: string;
  currentOwner: MaintenanceUser | null;
  assignees: {
    worker: MaintenanceUser | null;
    expert: MaintenanceUser | null;
    safety: MaintenanceUser | null;
  };
  reporter: string;
  createdAt: string;
  updatedAt: string;
  slaDeadline: string;
  isOverdue?: boolean;
  tags: string[];
  relatedAlerts: number;
  sourceTaskId?: number;
  sourceLabel?: string;
  rawStatus?: string;
}

type TicketStatusFilter = "all" | "todo" | "active" | "done" | "overdue";
type AssignmentRoleFilter = "all" | "worker" | "expert" | "safety";
type AssignmentStateFilter = "all" | "assigned" | "unassigned" | "mine";

const demoTickets: Ticket[] = [
  {
    id: "WO-20260424-001",
    title: "CMP-102 空压机 ERR-102 频繁告警",
    description: "振动均值上升，温升告警伴随出现；建议优先检查传感器供电与端子紧固。",
    priority: "emergency",
    status: "S7",
    assignee: "张工",
    currentOwner: null,
    assignees: { worker: null, expert: null, safety: null },
    reporter: "系统",
    createdAt: "2026-04-24 19:40",
    updatedAt: "2026-04-24 20:12",
    slaDeadline: "2026-04-24 21:00",
    tags: ["ERR-102", "压缩机", "振动"],
    relatedAlerts: 3,
    sourceTaskId: 1024,
    sourceLabel: "AI诊断任务 #1024",
    rawStatus: "S7",
  },
  {
    id: "WO-20260424-002",
    title: "PUMP-07 压力波动与噪声异常",
    description: "压力曲线呈锯齿波动，疑似旁通阀卡滞；建议复核阀位与压差。",
    priority: "standard",
    status: "S1",
    assignee: "未分配",
    currentOwner: null,
    assignees: { worker: null, expert: null, safety: null },
    reporter: "李工",
    createdAt: "2026-04-24 18:20",
    updatedAt: "2026-04-24 19:05",
    slaDeadline: "2026-04-25 10:00",
    tags: ["泵组", "压力", "阀门"],
    relatedAlerts: 1,
    sourceTaskId: 1021,
    sourceLabel: "设备告警",
    rawStatus: "S1",
  },
  {
    id: "WO-20260423-019",
    title: "CNC-21 数控机床主轴温升异常",
    description: "温升速率偏高，建议检查润滑系统与冷却回路；参考历史案例 CASE-033。",
    priority: "routine",
    status: "S3",
    assignee: "李工",
    currentOwner: null,
    assignees: { worker: null, expert: null, safety: null },
    reporter: "人工创建",
    createdAt: "2026-04-24 16:10",
    updatedAt: "2026-04-24 18:42",
    slaDeadline: "2026-04-25 12:00",
    tags: ["机床", "温升", "润滑"],
    relatedAlerts: 0,
    sourceTaskId: 1008,
    sourceLabel: "人工创建",
    rawStatus: "S3",
  },
];

function isTicketOverdue(ticket: Ticket): boolean {
  if (typeof ticket.isOverdue === "boolean") {
    return ticket.isOverdue;
  }
  return (
    new Date(ticket.slaDeadline) < new Date() &&
    !["S10", "SX"].includes(ticket.status)
  );
}

function isTodoTicket(ticket: Ticket): boolean {
  return ["S1", "S3", "S5"].includes(ticket.status) && !isTicketOverdue(ticket);
}

function isActiveTicket(ticket: Ticket): boolean {
  return ["S2", "S4", "S6", "S7", "S8", "S9"].includes(ticket.status) && !isTicketOverdue(ticket);
}

function matchesStatusFilter(ticket: Ticket, filter: TicketStatusFilter): boolean {
  if (filter === "all") return true;
  if (filter === "overdue") return isTicketOverdue(ticket);
  if (filter === "todo") return isTodoTicket(ticket);
  if (filter === "active") return isActiveTicket(ticket);
  return ticket.status === "S10";
}

function mapWorkOrderStatus(status: string): Ticket["status"] {
  const s = String(status || "").toUpperCase();
  if (
    s === "S1" ||
    s === "S2" ||
    s === "S3" ||
    s === "S4" ||
    s === "S5" ||
    s === "S6" ||
    s === "S7" ||
    s === "S8" ||
    s === "S9" ||
    s === "S10" ||
    s === "SX"
  ) {
    return s;
  }
  return "S1";
}

function mapMaintenanceLevel(level: unknown): Ticket["priority"] {
  const l = String(level || "").toLowerCase();
  if (l.includes("emergency") || l.includes("紧急")) return "emergency";
  if (l.includes("standard") || l.includes("标准")) return "standard";
  if (l.includes("routine") || l.includes("日常") || l.includes("例行")) return "routine";
  return "unknown";
}

function buildTemporarySlaDeadline(
  createdAt: string | null | undefined,
  priority: Ticket["priority"],
): string {
  const hoursByPriority: Record<Ticket["priority"], number> = {
    emergency: 2,
    standard: 8,
    routine: 24,
    unknown: 72,
  };
  const base = new Date(String(createdAt || ""));
  if (Number.isNaN(base.getTime())) return String(createdAt || "");
  const deadline = new Date(base.getTime() + hoursByPriority[priority] * 60 * 60 * 1000);
  return deadline.toISOString();
}

function formatTicketUpdatedAtParts(value: string) {
  const normalized = String(value || "").trim().replace(" ", "T");
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return {
      dateLine: "----:--:--",
      timeLine: "--:--:--",
    };
  }
  const yyyy = String(date.getFullYear());
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  const sec = String(date.getSeconds()).padStart(2, "0");
  return {
    dateLine: `${yyyy}-${mm}-${dd}`,
    timeLine: `${hh}:${min}:${sec}`,
  };
}

function formatWorkOrderCode(id: number | string) {
  const digits = String(id).match(/\d+/)?.[0];
  if (!digits) return String(id);
  return `WO-${String(Number(digits)).padStart(6, "0")}`;
}

// 优先级配置
const priorityConfig = {
  emergency: {
    label: "紧急检修",
    badgeClass: "app-badge app-badge-priority-p1",
    dot: "bg-red-500",
  },
  standard: {
    label: "标准检修",
    badgeClass: "app-badge app-badge-priority-p2",
    dot: "bg-orange-500",
  },
  routine: {
    label: "例行检修",
    badgeClass: "app-badge app-badge-priority-p3",
    dot: "bg-yellow-500",
  },
  unknown: {
    label: "未分级",
    badgeClass: "app-badge app-badge-status-failed",
    dot: "bg-slate-500",
  },
};

// 状态配置
const statusConfig = {
  S1: {
    label: "待处理",
    badgeClass: "app-badge app-badge-status-running",
    icon: Clock,
  },
  S2: {
    label: "处理中",
    badgeClass: "app-badge border-indigo-500/30 bg-indigo-500/10 text-indigo-400",
    icon: RefreshCw,
  },
  S3: {
    label: "待处理",
    badgeClass: "app-badge app-badge-status-running",
    icon: Clock,
  },
  S4: {
    label: "处理中",
    badgeClass: "app-badge border-indigo-500/30 bg-indigo-500/10 text-indigo-400",
    icon: RefreshCw,
  },
  S5: {
    label: "待处理",
    badgeClass: "app-badge app-badge-status-running",
    icon: Clock,
  },
  S6: {
    label: "处理中",
    badgeClass: "app-badge border-indigo-500/30 bg-indigo-500/10 text-indigo-400",
    icon: RefreshCw,
  },
  S7: {
    label: "处理中",
    badgeClass: "app-badge border-indigo-500/30 bg-indigo-500/10 text-indigo-400",
    icon: RefreshCw,
  },
  S8: {
    label: "处理中",
    badgeClass: "app-badge border-indigo-500/30 bg-indigo-500/10 text-indigo-400",
    icon: RefreshCw,
  },
  S9: {
    label: "处理中",
    badgeClass: "app-badge border-indigo-500/30 bg-indigo-500/10 text-indigo-400",
    icon: RefreshCw,
  },
  S10: {
    label: "已完成",
    badgeClass: "app-badge app-badge-status-completed",
    icon: CheckCircle2,
  },
  SX: {
    label: "已终止",
    badgeClass: "app-badge app-badge-status-failed",
    icon: XCircle,
  },
};

const overdueStatusMeta = {
  label: "已超时",
  badgeClass: "app-badge border-red-500/30 bg-red-500/10 text-red-400",
  icon: AlertTriangle,
};

// 统计卡片组件
function StatCard({
  label,
  value,
  icon: Icon,
  color,
  active,
  onClick,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  color: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        app-kpi-card flex items-center gap-3 px-4 py-3 transition-all duration-200
        ${active
          ? "border-[#5e6ad2]/35 bg-[#5e6ad2]/8"
          : "hover:bg-muted/75"
        }
      `}
    >
      <div className={`p-2 rounded-md ${color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="text-left">
        <div className="text-xl font-semibold text-foreground">{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </div>
    </button>
  );
}

function TicketRowActions({
  ticket,
  user,
  onRefresh,
  onDelete,
}: {
  ticket: Ticket;
  user: MaintenanceUser | null;
  onRefresh: () => Promise<void>;
  onDelete: (ticket: Ticket) => void;
}) {
  const canDelete = canDeleteWorkOrder(user);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(formatWorkOrderCode(ticket.id));
      toast.success("工单编号已复制");
    } catch {
      toast.error("复制失败，请检查浏览器权限");
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="app-btn-ghost p-1.5"
          onClick={(e) => e.preventDefault()}
          aria-label="更多操作"
        >
          <MoreHorizontal className="w-4 h-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44 border-border bg-popover text-popover-foreground">
        <DropdownMenuItem asChild>
          <Link href={`/tickets/${ticket.id}`} onClick={(e) => e.stopPropagation()}>
            查看详情
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={(e) => {
            e.preventDefault();
            void handleCopy();
          }}
        >
          复制工单号
        </DropdownMenuItem>
        {canDelete ? <DropdownMenuSeparator className="bg-border" /> : null}
        {canDelete ? (
          <DropdownMenuItem
            variant="destructive"
            onClick={(e) => {
              e.preventDefault();
              onDelete(ticket);
            }}
          >
            <Trash2 className="w-4 h-4" />
            删除工单
          </DropdownMenuItem>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// 工单行组件
function TicketRow({
  ticket,
  user,
  onRefresh,
  onDelete,
}: {
  ticket: Ticket;
  user: MaintenanceUser | null;
  onRefresh: () => Promise<void>;
  onDelete: (ticket: Ticket) => void;
}) {
  const priority = priorityConfig[ticket.priority];
  const isOverdue = isTicketOverdue(ticket);
  const status = isOverdue ? overdueStatusMeta : statusConfig[ticket.status];
  const StatusIcon = status.icon;
  const updatedAtParts = formatTicketUpdatedAtParts(ticket.updatedAt);

  return (
    <Link href={`/tickets/${ticket.id}`}>
      <div
        className={`
        group app-table-row px-4 py-4 duration-200
        ${isOverdue ? "bg-red-500/5 hover:bg-red-500/8" : ""}
      `}
      >
        {/* 桌面端布局 */}
        <div className="hidden lg:grid lg:grid-cols-12 lg:gap-4 lg:items-center">
          {/* 工单信息 */}
          <div className="col-span-5 flex items-start gap-3">
            <div
              className={`w-1 h-12 rounded-full ${priority.dot} flex-shrink-0`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-muted-foreground">
                  {ticket.id}
                </span>
                <span className={`${priority.badgeClass} px-1.5 py-0.5 text-[10px]`}>
                  {priority.label}
                </span>
              </div>
              <h3 className="mt-1 truncate text-sm font-medium text-foreground transition-colors group-hover:text-[#5e6ad2]">
                {ticket.title}
              </h3>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                来源：
                {ticket.sourceLabel
                  ? ticket.sourceLabel
                  : ticket.sourceTaskId
                    ? `AI诊断任务 #${ticket.sourceTaskId}`
                    : "系统"}
                {" · "}
                {ticket.description}
              </p>
            </div>
          </div>

          {/* 状态 */}
          <div className="col-span-2">
            <span className={`${status.badgeClass} px-2 py-1`}>
              <StatusIcon className="w-3 h-3" />
              {status.label}
            </span>
          </div>

          {/* 处理人 */}
          <div className="col-span-2">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted">
                <User className="w-3 h-3 text-muted-foreground" />
              </div>
              <span
                className={`text-sm ${ticket.assignee === "未分配" ? "italic text-muted-foreground" : "text-foreground"}`}
              >
                {ticket.assignee}
              </span>
            </div>
          </div>

          {/* 时间和告警 */}
          <div className="col-span-2">
            <div className="text-xs text-muted-foreground">
              <div>{updatedAtParts.dateLine}</div>
              <div>{updatedAtParts.timeLine}</div>
            </div>
            {ticket.relatedAlerts > 0 && (
              <div className="text-xs text-orange-400 mt-1">
                {ticket.relatedAlerts} 个关联告警
              </div>
            )}
          </div>

          {/* 操作 */}
          <div className="col-span-1 flex justify-end">
            <TicketRowActions ticket={ticket} user={user} onRefresh={onRefresh} onDelete={onDelete} />
          </div>
        </div>

        {/* 移动端布局 */}
        <div className="lg:hidden space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <div
                className={`w-1.5 h-1.5 rounded-full ${priority.dot} flex-shrink-0`}
              />
              <span className="text-xs font-mono text-muted-foreground">
                {ticket.id}
              </span>
              <span className={`${priority.badgeClass} px-1.5 py-0.5 text-[10px]`}>
                {priority.label}
              </span>
            </div>
            <span className={`${status.badgeClass} px-2 py-0.5`}>
              <StatusIcon className="w-3 h-3" />
              {status.label}
            </span>
          </div>

          <h3 className="text-sm font-medium text-foreground">{ticket.title}</h3>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <User className="w-3 h-3" />
                {ticket.assignee}
              </span>
              <span className="leading-5">
                <span className="block">{updatedAtParts.dateLine}</span>
                <span className="block">{updatedAtParts.timeLine}</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
}

// 骨架行组件
function SkeletonRow() {
  return (
    <div className="app-table-row px-4 py-4">
      <div className="hidden lg:grid lg:grid-cols-12 lg:gap-4 lg:items-center">
        <div className="col-span-5 flex items-start gap-3">
          <div className="app-skeleton h-12 w-1 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="app-skeleton h-4 w-32" />
            <div className="app-skeleton h-5 w-48" />
            <div className="app-skeleton h-3 w-64" />
          </div>
        </div>
        <div className="col-span-2">
          <div className="app-skeleton h-6 w-20 rounded-full" />
        </div>
        <div className="col-span-2">
          <div className="app-skeleton h-6 w-24" />
        </div>
        <div className="col-span-2">
          <div className="app-skeleton h-4 w-28" />
        </div>
        <div className="col-span-1" />
      </div>
      <div className="lg:hidden space-y-3">
        <div className="flex justify-between">
          <div className="app-skeleton h-4 w-32" />
          <div className="app-skeleton h-5 w-16 rounded-full" />
        </div>
        <div className="app-skeleton h-5 w-48" />
        <div className="app-skeleton h-4 w-40" />
      </div>
    </div>
  );
}

// 空状态组件
function EmptyState({
  onCreate,
  filtered = false,
}: {
  onCreate?: () => void;
  filtered?: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-14">
      <div className="app-empty-icon mb-4 h-16 w-16">
        <Tag className="w-8 h-8" />
      </div>
      <h3 className="mb-2 text-lg font-medium text-foreground">
        {filtered ? "暂无匹配工单" : "暂无工单"}
      </h3>
      <p className="mb-6 max-w-sm text-center text-sm text-muted-foreground">
        {filtered
          ? "当前筛选条件下没有找到工单，请尝试调整筛选条件或切换查看范围。"
          : "当前还没有工单，先从已完成的智能诊断任务进入并创建检修工单。"}
      </p>
      {!filtered && onCreate ? (
        <button
          type="button"
          className="app-btn-primary"
          onClick={onCreate}
        >
          <Plus className="w-4 h-4" />
          创建工单
        </button>
      ) : null}
    </div>
  );
}

function AuthExpiredState() {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-14">
      <div className="app-empty-icon mb-4 h-16 w-16">
        <Tag className="w-8 h-8" />
      </div>
      <h3 className="mb-2 text-lg font-medium text-foreground">登录已失效</h3>
      <p className="mb-6 max-w-sm text-center text-sm text-muted-foreground">
        当前检修域登录状态已过期，请重新登录后继续查看工单与设备数据。
      </p>
      <button
        type="button"
        className="app-btn-primary"
        onClick={() => {
          window.location.href = "/login";
        }}
      >
        前往登录
      </button>
    </div>
  );
}

// 错误状态组件
function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-14">
      <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
        <XCircle className="w-8 h-8 text-red-400" />
      </div>
      <h3 className="mb-2 text-lg font-medium text-foreground">加载失败</h3>
      <p className="mb-6 max-w-sm text-center text-sm text-muted-foreground">
        无法加载工单列表，请检查网络连接后重试
      </p>
      <button type="button" onClick={onRetry} className="app-btn-secondary">
        <RefreshCw className="w-4 h-4" />
        重新加载
      </button>
    </div>
  );
}

export default function TicketsPage() {
  const { user } = useMaintenanceAuth();
  const [demoEnabled, setDemoEnabled] = useState(false);
  const [realTickets, setRealTickets] = useState<Ticket[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<Ticket | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const modeTickets = useMemo(() => (demoEnabled ? demoTickets : realTickets), [demoEnabled, realTickets]);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<TicketStatusFilter>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [assignmentRoleFilter, setAssignmentRoleFilter] = useState<AssignmentRoleFilter>("all");
  const [assignmentStateFilter, setAssignmentStateFilter] = useState<AssignmentStateFilter>("all");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [pageState, setPageState] = useState<
    "normal" | "loading" | "empty" | "error" | "auth"
  >("normal");
  const [currentPage, setCurrentPage] = useState(1);
  const PAGE_SIZE = 10;

  const syncWorkOrdersApi = useCallback(async () => {
    const tok = getMaintenanceToken();
    try {
      if (!tok) {
        await fetchMaintenanceHealth();
        setRealTickets([]);
        setPageState("empty");
        return;
      }
      setPageState("loading");
      const [orders, ds] = await Promise.all([
        listWorkOrders(tok, 1, undefined, {
          assignmentRole: assignmentRoleFilter === "all" ? undefined : assignmentRoleFilter,
          assignmentState: assignmentStateFilter === "all" ? undefined : assignmentStateFilter,
        }),
        listMaintenanceDevices(tok, 1),
      ]);
      const byId = new Map<number, MaintenanceDeviceItem>(ds.items.map((d) => [d.id, d]));
      const mapped = orders.items.map((wo) => {
        const device = byId.get(Number(wo.device_id));
        const id = String(wo.id);
        const priority = mapMaintenanceLevel(wo.maintenance_level);
        return {
          id,
          title: device ? `${device.asset_code || "设备"} 检修工单` : `工单 #${id}`,
          description: device
            ? `${device.device_type} ${device.model || ""}`.trim()
            : `设备ID ${wo.device_id}`,
          priority,
          status: mapWorkOrderStatus(String(wo.status || "")),
          assignee: wo.current_owner?.display_name || "未分配",
          currentOwner: wo.current_owner ?? null,
          assignees: {
            worker: wo.assignees?.worker ?? null,
            expert: wo.assignees?.expert ?? null,
            safety: wo.assignees?.safety ?? null,
          },
          reporter: "系统",
          createdAt: String(wo.created_at || ""),
          updatedAt: String(wo.updated_at || ""),
          slaDeadline: String(wo.sla_deadline || buildTemporarySlaDeadline(wo.created_at, priority)),
          isOverdue: Boolean(wo.is_overdue),
          tags: device
            ? [device.device_type, device.model, device.asset_code].filter(Boolean)
            : ["检修工单"],
          relatedAlerts: 0,
          sourceTaskId: typeof wo.source_task_id === "number" ? wo.source_task_id : undefined,
          sourceLabel:
            typeof wo.source_task_id === "number"
              ? `AI诊断任务 #${wo.source_task_id}`
              : "检修域接口",
          rawStatus: String(wo.status || ""),
        } as Ticket;
      });
      setRealTickets(mapped);
      setPageState(mapped.length ? "normal" : "empty");
    } catch (e) {
      if (isMaintenanceAuthExpiredError(e)) {
        setRealTickets([]);
        setPageState("auth");
        return;
      }
      setPageState("error");
    }
  }, [assignmentRoleFilter, assignmentStateFilter]);

  const handleDeleteRequest = useCallback((ticket: Ticket) => {
    setDeleteTarget(ticket);
    setDeleteError(null);
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    const token = getMaintenanceToken();
    const numericId = Number(deleteTarget.id);
    if (!token) {
      setDeleteError("当前未检测到检修域登录状态");
      return;
    }
    if (!Number.isFinite(numericId)) {
      setDeleteError("工单编号无效");
      return;
    }
    setDeleteSubmitting(true);
    setDeleteError(null);
    try {
      await deleteWorkOrder(token, numericId);
      toast.success("工单已删除");
      setDeleteTarget(null);
      await syncWorkOrdersApi();
    } catch (e) {
      const message = e instanceof Error ? e.message : "删除工单失败";
      setDeleteError(message);
      if (isMaintenanceAuthExpiredError(e)) {
        setPageState("auth");
      }
    } finally {
      setDeleteSubmitting(false);
    }
  }, [deleteTarget, syncWorkOrdersApi]);

  useEffect(() => {
    const syncMode = () => {
      const demo = isDemoMode();
      setDemoEnabled(demo);
      if (demo) {
        setPageState(demoTickets.length ? "normal" : "empty");
        return;
      }
      void syncWorkOrdersApi();
    };
    syncMode();
    window.addEventListener(DEMO_MODE_CHANGED_EVENT, syncMode as EventListener);
    return () => {
      window.removeEventListener(DEMO_MODE_CHANGED_EVENT, syncMode as EventListener);
    };
  }, [syncWorkOrdersApi]);

  useEffect(() => {
    if (demoEnabled) return;
    void syncWorkOrdersApi();
  }, [assignmentRoleFilter, assignmentStateFilter, demoEnabled, syncWorkOrdersApi]);

  // 筛选 + 排序（最新优先 / 最早优先）
  const filteredTickets = useMemo(() => {
    const parseTicketTime = (value: string) => {
      const normalized = value.trim().replace(" ", "T");
      const timestamp = Date.parse(normalized);
      return Number.isNaN(timestamp) ? 0 : timestamp;
    };

    const next = modeTickets.filter((ticket) => {
      if (!matchesStatusFilter(ticket, statusFilter)) {
        return false;
      }
      if (priorityFilter !== "all" && ticket.priority !== priorityFilter) return false;
      if (
        searchQuery &&
        !ticket.title.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !ticket.id.toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        return false;
      }
      return true;
    });

    next.sort((a, b) => {
      const ta = parseTicketTime(a.updatedAt);
      const tb = parseTicketTime(b.updatedAt);
      return sortOrder === "desc" ? tb - ta : ta - tb;
    });
    return next;
  }, [modeTickets, statusFilter, priorityFilter, searchQuery, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(filteredTickets.length / PAGE_SIZE));
  const pagedTickets = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredTickets.slice(start, start + PAGE_SIZE);
  }, [filteredTickets, currentPage]);

  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter, priorityFilter, assignmentRoleFilter, assignmentStateFilter, searchQuery, sortOrder]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const stats = useMemo(() => {
    const src = modeTickets;
    return {
      total: src.length,
      todo: src.filter((t) => matchesStatusFilter(t, "todo")).length,
      active: src.filter((t) => matchesStatusFilter(t, "active")).length,
      done: src.filter((t) => matchesStatusFilter(t, "done")).length,
      overdue: src.filter((t) => isTicketOverdue(t)).length,
    };
  }, [modeTickets]);

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="app-main app-main-wide">
        {/* 标题区 */}
        <section className="app-page-head mb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold text-foreground">检修工单</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                跟踪从故障诊断到现场处理的完整检修流程，工单需基于已完成的智能诊断任务生成
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                className="h-9"
                onClick={() => void syncWorkOrdersApi()}
              >
                <RefreshCw className="w-4 h-4" />
                同步
              </Button>
            </div>
          </div>
        </section>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
          <StatCard
            label="全部工单"
            value={stats.total}
            icon={Tag}
            color="bg-muted text-foreground"
            active={statusFilter === "all"}
            onClick={() => {
              setStatusFilter("all");
              void syncWorkOrdersApi();
            }}
          />
          <StatCard
            label="待处理"
            value={stats.todo}
            icon={Clock}
            color="bg-blue-500/20 text-blue-400"
            active={statusFilter === "todo"}
            onClick={() => {
              setStatusFilter("todo");
              void syncWorkOrdersApi();
            }}
          />
          <StatCard
            label="处理中"
            value={stats.active}
            icon={RefreshCw}
            color="bg-indigo-500/20 text-indigo-400"
            active={statusFilter === "active"}
            onClick={() => {
              setStatusFilter("active");
              void syncWorkOrdersApi();
            }}
          />
          <StatCard
            label="已完成"
            value={stats.done}
            icon={CheckCircle2}
            color="bg-green-500/20 text-green-400"
            active={statusFilter === "done"}
            onClick={() => {
              setStatusFilter("done");
              void syncWorkOrdersApi();
            }}
          />
          <StatCard
            label="已超时"
            value={stats.overdue}
            icon={AlertTriangle}
            color="bg-red-500/20 text-red-400"
            active={statusFilter === "overdue"}
            onClick={() => {
              setStatusFilter("overdue");
              void syncWorkOrdersApi();
            }}
          />
        </div>

        {/* 筛选工具栏 */}
        <div className="app-card mb-6">
          <div className="p-4 flex flex-col sm:flex-row gap-3">
            {/* 搜索框 */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="搜索工单编号或标题..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="app-input app-input-with-icon pr-4"
              />
            </div>

            {/* 检修等级筛选 */}
            <div className="relative">
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="app-select cursor-pointer appearance-none pl-3 pr-8"
              >
                <option value="all">所有检修等级</option>
                <option value="emergency">紧急检修</option>
                <option value="standard">标准检修</option>
                <option value="routine">例行检修</option>
                <option value="unknown">未分级</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            </div>

            <div className="relative">
              <select
                value={assignmentRoleFilter}
                onChange={(e) => setAssignmentRoleFilter(e.target.value as AssignmentRoleFilter)}
                className="app-select cursor-pointer appearance-none pl-3 pr-8"
              >
                <option value="all">全部角色</option>
                <option value="worker">检修员</option>
                <option value="expert">专家</option>
                <option value="safety">安全员</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            </div>

            <div className="relative">
              <select
                value={assignmentStateFilter}
                onChange={(e) => setAssignmentStateFilter(e.target.value as AssignmentStateFilter)}
                className="app-select cursor-pointer appearance-none pl-3 pr-8"
              >
                <option value="all">全部分配状态</option>
                <option value="assigned">已分配</option>
                <option value="unassigned">未分配</option>
                <option value="mine">分配给我</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            </div>

            {/* 排序 */}
            <button
              type="button"
              onClick={() => {
                setSortOrder(sortOrder === "desc" ? "asc" : "desc");
                void syncWorkOrdersApi();
              }}
              className="app-btn-secondary h-10 px-3"
            >
              {sortOrder === "desc" ? (
                <SortDesc className="w-4 h-4" />
              ) : (
                <SortAsc className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">
                {sortOrder === "desc" ? "最新优先" : "最早优先"}
              </span>
            </button>
          </div>

          {/* 表头（桌面端） */}
          <div className="app-table-head hidden border-t border-border px-4 py-3 text-xs font-medium lg:grid lg:grid-cols-12 lg:gap-4">
            <div className="col-span-5">工单信息</div>
            <div className="col-span-2">状态</div>
            <div className="col-span-2">处理人</div>
            <div className="col-span-2">更新时间</div>
            <div className="col-span-1"></div>
          </div>

          {/* 工单列表 */}
          <div className="border-t border-border">
            {pageState === "loading" ? (
              <>
                {[...Array(5)].map((_, i) => (
                  <SkeletonRow key={i} />
                ))}
              </>
            ) : pageState === "empty" ? (
              <EmptyState
                onCreate={() => {
                  window.location.href = "/tasks";
                }}
              />
            ) : pageState === "error" ? (
              <ErrorState onRetry={() => void syncWorkOrdersApi()} />
            ) : pageState === "auth" ? (
              <AuthExpiredState />
            ) : filteredTickets.length === 0 ? (
              <EmptyState filtered />
            ) : (
              pagedTickets.map((ticket) => (
                <TicketRow
                  key={ticket.id}
                  ticket={ticket}
                  user={user}
                  onRefresh={syncWorkOrdersApi}
                  onDelete={handleDeleteRequest}
                />
              ))
            )}
          </div>

          {/* 分页 */}
          {pageState === "normal" && filteredTickets.length > 0 && (
            <div className="flex items-center justify-between border-t border-border px-4 py-3">
              <div className="text-sm text-muted-foreground">
                共 <span className="text-foreground">{filteredTickets.length}</span>{" "}
                条工单，本页显示{" "}
                <span className="text-foreground">{pagedTickets.length}</span>{" "}
                条
              </div>

              <div className="flex items-center gap-2">
                <button
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="app-btn-secondary px-3 py-1.5"
                >
                  上一页
                </button>

                <div className="flex items-center gap-1">
                  {Array.from({ length: totalPages }).slice(0, 3).map((_, index) => {
                    const page = index + 1;
                    return (
                      <button
                        key={page}
                        onClick={() => setCurrentPage(page)}
                        className={`h-8 w-8 rounded-md text-sm transition-colors ${currentPage === page ? "app-btn-page-active" : "app-btn-ghost text-foreground"
                          }`}
                      >
                        {page}
                      </button>
                    );
                  })}
                  {totalPages > 4 ? (
                    <>
                      <span className="px-1 text-muted-foreground">...</span>
                      <button
                        onClick={() => setCurrentPage(totalPages)}
                        className={`h-8 w-8 rounded-md text-sm transition-colors ${currentPage === totalPages ? "app-btn-page-active" : "app-btn-ghost text-foreground"
                          }`}
                      >
                        {totalPages}
                      </button>
                    </>
                  ) : totalPages === 4 ? (
                    <button
                      onClick={() => setCurrentPage(4)}
                      className={`h-8 w-8 rounded-md text-sm transition-colors ${currentPage === 4 ? "app-btn-page-active" : "app-btn-ghost text-foreground"
                        }`}
                    >
                      4
                    </button>
                  ) : null}
                </div>

                <button
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="app-btn-secondary px-3 py-1.5"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>

        <Dialog
          open={Boolean(deleteTarget)}
          onOpenChange={(open) => {
            if (deleteSubmitting) return;
            if (!open) {
              setDeleteTarget(null);
              setDeleteError(null);
            }
          }}
        >
          <DialogContent className="max-w-md border-border bg-popover text-popover-foreground">
            <DialogHeader>
              <DialogTitle>确认删除工单</DialogTitle>
              <DialogDescription>
                {deleteTarget ? (
                  <>
                    你将删除工单 <span className="font-mono text-foreground">#{formatWorkOrderCode(deleteTarget.id)}</span>。
                    关联流程记录会一并移除，且不可撤销。
                  </>
                ) : (
                  "该操作会同步删除后端工单记录，且不可撤销。"
                )}
              </DialogDescription>
            </DialogHeader>

            {deleteError ? (
              <p className="text-sm text-red-400" role="alert">
                {deleteError}
              </p>
            ) : null}

            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                type="button"
                variant="outline"
                className="border-border bg-transparent text-foreground hover:bg-muted"
                onClick={() => {
                  setDeleteTarget(null);
                  setDeleteError(null);
                }}
                disabled={deleteSubmitting}
              >
                取消
              </Button>
              <Button
                type="button"
                className="bg-red-500 text-white hover:bg-red-600"
                onClick={() => void confirmDelete()}
                disabled={deleteSubmitting}
              >
                {deleteSubmitting ? "删除中…" : "确认删除"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

      </main>

    </div>
  );
}

