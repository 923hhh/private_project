"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, ShieldAlert, XCircle } from "lucide-react";
import { toast } from "sonner";

import { useMaintenanceAuth } from "@/features/auth/maintenance-auth";
import { canResolveApproval } from "@/features/auth/permissions";
import { getMaintenanceToken } from "@/features/auth/lib/token-store";
import { Header } from "@/shared/components/brand/app-header";
import { isMaintenanceAuthExpiredError, listApprovalTasks, resolveApprovalTask, type ApprovalTaskItem } from "@/features/tickets/api";

export default function ApprovalTasksPage() {
  const { user } = useMaintenanceAuth();
  const [items, setItems] = useState<ApprovalTaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submittingId, setSubmittingId] = useState<number | null>(null);

  const loadTasks = async () => {
    const token = getMaintenanceToken();
    if (!token) {
      setError("当前未检测到检修域登录状态。");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await listApprovalTasks(token);
      setItems(payload.items);
    } catch (e) {
      setError(
        isMaintenanceAuthExpiredError(e)
          ? "登录已失效，请重新登录。"
          : e instanceof Error
            ? e.message
            : "加载审批任务失败",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTasks();
  }, []);

  const handleResolve = async (item: ApprovalTaskItem, status: "approved" | "rejected") => {
    const token = getMaintenanceToken();
    if (!token) return;
    setSubmittingId(item.id);
    try {
      await resolveApprovalTask(token, item.id, { status });
      toast.success(status === "approved" ? "审批已通过" : "审批已驳回");
      await loadTasks();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "审批操作失败");
    } finally {
      setSubmittingId(null);
    }
  };

  if (!canResolveApproval(user)) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="app-main app-main-wide">
          <div className="app-card p-6">
            <h1 className="text-xl font-semibold text-foreground">审批任务</h1>
            <div className="mt-4 rounded-lg border border-border bg-muted/20 p-5 text-sm text-muted-foreground">
              当前页面仅限审批员或管理员访问。
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="app-main app-main-wide space-y-6">
        <section className="app-page-head">
          <h1 className="text-xl font-semibold text-foreground">审批任务</h1>
          <p className="mt-1 text-sm text-muted-foreground">集中处理待审批的高危工步，审批后工单会自动推进。</p>
        </section>

        <div className="app-card p-5">
          {loading ? (
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在加载审批任务...
            </div>
          ) : error ? (
            <div className="rounded-lg border border-border bg-muted/20 p-4 text-sm text-muted-foreground">
              {error}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-lg border border-border bg-muted/20 p-4 text-sm text-muted-foreground">
              当前没有待处理的审批任务。
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <div key={item.id} className="rounded-lg border border-border bg-muted/20 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <ShieldAlert className="h-4 w-4 text-amber-500" />
                        审批任务 #{item.id}
                      </div>
                      <div className="mt-2 text-sm text-muted-foreground">
                        工单 <Link href={`/tickets/${item.work_order_id}`} className="text-foreground underline underline-offset-4">#{item.work_order_id}</Link>
                        {" · "}
                        工步 {item.step_no}
                        {" · "}
                        创建时间 {item.created_at}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="app-btn-secondary"
                        onClick={() => void handleResolve(item, "approved")}
                        disabled={submittingId === item.id}
                      >
                        {submittingId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                        通过
                      </button>
                      <button
                        type="button"
                        className="app-btn-secondary"
                        onClick={() => void handleResolve(item, "rejected")}
                        disabled={submittingId === item.id}
                      >
                        <XCircle className="h-4 w-4" />
                        驳回
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

