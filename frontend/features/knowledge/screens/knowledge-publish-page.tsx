"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { BookOpen, ChevronLeft, History, Loader2, RadioTower, RefreshCw, UploadCloud } from "lucide-react";

import { getMaintenanceToken } from "@/features/auth/lib/token-store";
import { useMaintenanceAuth } from "@/features/auth/maintenance-auth";
import {
  fetchKnowledgeArticleVersions,
  fetchKnowledgePublishConsole,
  publishKnowledgeArticle,
  withdrawKnowledgeArticle,
  type KnowledgePublishConsolePayload,
  type KnowledgePublishListItem,
} from "@/features/knowledge/api";
import { Header } from "@/shared/components/brand/app-header";
import { formatDateTimeLocal } from "@/shared/lib/utils";

function getStatusMeta(status: string) {
  switch (status) {
    case "published":
      return { label: "已发布", className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" };
    case "pending_publish":
      return { label: "待发布", className: "border-amber-500/30 bg-amber-500/10 text-amber-400" };
    case "withdrawn":
      return { label: "已撤回", className: "border-slate-500/30 bg-slate-500/10 text-slate-300" };
    case "pending_review":
      return { label: "待审核", className: "border-sky-500/30 bg-sky-500/10 text-sky-400" };
    case "rejected_review":
      return { label: "审核驳回", className: "border-rose-500/30 bg-rose-500/10 text-rose-400" };
    default:
      return { label: status || "未知", className: "border-border bg-muted/40 text-muted-foreground" };
  }
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-foreground">{value}</div>
    </div>
  );
}

function ArticleCard({
  item,
  selected,
  actionLabel,
  actionBusy,
  actionDisabled,
  onSelect,
  onAction,
}: {
  item: KnowledgePublishListItem;
  selected: boolean;
  actionLabel?: string;
  actionBusy?: boolean;
  actionDisabled?: boolean;
  onSelect: () => void;
  onAction?: () => void;
}) {
  const statusMeta = getStatusMeta(item.status);
  return (
    <div
      className={`rounded-xl border p-4 transition-colors ${selected ? "border-primary bg-primary/5" : "border-border bg-card hover:bg-muted/30"}`}
    >
      <button type="button" className="w-full text-left" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-medium text-foreground">{item.title}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              系列 #{item.series_id} · V{item.version}
              {item.source_work_order_id ? ` · 工单 #${item.source_work_order_id}` : ""}
            </div>
          </div>
          <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${statusMeta.className}`}>
            {statusMeta.label}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span>审核人：{item.reviewed_by_name || "无"}</span>
          <span>更新时间：{formatDateTimeLocal(item.updated_at)}</span>
        </div>
        <div className="mt-2 text-xs text-muted-foreground">{item.retrieval_status_label}</div>
      </button>
      {onAction ? (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className="app-btn-secondary h-9 px-3 text-sm"
            onClick={onAction}
            disabled={actionDisabled || actionBusy}
          >
            {actionBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {actionLabel}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function KnowledgePublishPageScreen() {
  const { hasAnyRole, hasRole, isLoading: authLoading } = useMaintenanceAuth();
  const canRead = hasAnyRole("admin", "expert");
  const canPublish = hasRole("admin");

  const [consolePayload, setConsolePayload] = useState<KnowledgePublishConsolePayload | null>(null);
  const [versions, setVersions] = useState<KnowledgePublishListItem[]>([]);
  const [selectedArticleId, setSelectedArticleId] = useState<number | null>(null);
  const [consoleLoading, setConsoleLoading] = useState(true);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionKey, setActionKey] = useState<string | null>(null);

  const selectedArticle = useMemo(() => {
    if (!consolePayload || selectedArticleId == null) return null;
    const pool = [
      ...consolePayload.pending_publish_items,
      ...consolePayload.current_effective_items,
      ...consolePayload.recent_version_records,
    ];
    return pool.find((item) => item.id === selectedArticleId) || null;
  }, [consolePayload, selectedArticleId]);

  const loadConsole = async (preferredArticleId?: number | null) => {
    const token = getMaintenanceToken();
    if (!token) {
      setError("当前未检测到检修域登录状态。");
      setConsolePayload(null);
      setConsoleLoading(false);
      return;
    }
    setConsoleLoading(true);
    setError(null);
    try {
      const payload = await fetchKnowledgePublishConsole(token);
      setConsolePayload(payload);
      const nextSelectedId =
        preferredArticleId && [
          ...payload.pending_publish_items,
          ...payload.current_effective_items,
          ...payload.recent_version_records,
        ].some((item) => item.id === preferredArticleId)
          ? preferredArticleId
          : payload.pending_publish_items[0]?.id ||
            payload.current_effective_items[0]?.id ||
            payload.recent_version_records[0]?.id ||
            null;
      setSelectedArticleId(nextSelectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载知识发布台失败");
      setConsolePayload(null);
    } finally {
      setConsoleLoading(false);
    }
  };

  const loadVersions = async (articleId: number) => {
    const token = getMaintenanceToken();
    if (!token) {
      setVersions([]);
      return;
    }
    setVersionsLoading(true);
    try {
      const payload = await fetchKnowledgeArticleVersions(token, articleId);
      setVersions(payload.items);
    } catch (err) {
      setVersions([]);
      toast.error(err instanceof Error ? err.message : "加载版本记录失败");
    } finally {
      setVersionsLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!canRead) {
      setConsoleLoading(false);
      setConsolePayload(null);
      return;
    }
    void loadConsole();
  }, [authLoading, canRead]);

  useEffect(() => {
    if (!selectedArticleId || !canRead) {
      setVersions([]);
      return;
    }
    void loadVersions(selectedArticleId);
  }, [selectedArticleId, canRead]);

  const handlePublish = async (articleId: number) => {
    const token = getMaintenanceToken();
    if (!token) return;
    setActionKey(`publish-${articleId}`);
    try {
      const updated = await publishKnowledgeArticle(token, articleId);
      toast.success("知识条目已发布");
      await loadConsole(updated.id);
      await loadVersions(updated.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发布失败");
    } finally {
      setActionKey(null);
    }
  };

  const handleWithdraw = async (articleId: number) => {
    const token = getMaintenanceToken();
    if (!token) return;
    setActionKey(`withdraw-${articleId}`);
    try {
      const updated = await withdrawKnowledgeArticle(token, articleId);
      toast.success("知识条目已撤回");
      await loadConsole(updated.id);
      await loadVersions(updated.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "撤回失败");
    } finally {
      setActionKey(null);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="app-main app-main-wide space-y-6">
        <section className="app-page-head">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-2">
              <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
                <ChevronLeft className="h-4 w-4" />
                返回工作台
              </Link>
              <div>
                <h1 className="text-2xl font-semibold text-foreground">知识发布</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  管理待发布知识、当前生效版本、版本记录和是否进入检索库的状态。
                </p>
              </div>
            </div>
            <button type="button" className="app-btn-secondary" onClick={() => void loadConsole(selectedArticleId)} disabled={consoleLoading || !canRead}>
              <RefreshCw className={`h-4 w-4 ${consoleLoading ? "animate-spin" : ""}`} />
              刷新
            </button>
          </div>
        </section>

        {!canRead && !authLoading ? (
          <section className="app-card p-6">
            <div className="text-base font-medium text-foreground">当前页面仅限管理员或专家查看。</div>
            <p className="mt-2 text-sm text-muted-foreground">管理员可执行发布与撤回，专家可只读查看版本与发布状态。</p>
          </section>
        ) : null}

        {canRead ? (
          <>
            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <SummaryCard label="待发布知识" value={consolePayload?.summary.pending_publish_count || 0} />
              <SummaryCard label="当前生效版本" value={consolePayload?.summary.current_effective_count || 0} />
              <SummaryCard label="已撤回版本" value={consolePayload?.summary.withdrawn_count || 0} />
              <SummaryCard label="进入检索库" value={consolePayload?.summary.retrieval_enabled_count || 0} />
            </section>

            {error ? (
              <section className="app-card p-6 text-sm text-red-400">{error}</section>
            ) : null}

            <section className="grid gap-6 xl:grid-cols-3">
              <div className="app-card">
                <div className="flex items-center gap-2 border-b border-border px-5 py-4 text-base font-medium text-foreground">
                  <UploadCloud className="h-4 w-4 text-muted-foreground" />
                  待发布知识
                </div>
                <div className="space-y-3 p-5">
                  {consoleLoading ? (
                    <div className="app-skeleton h-32 w-full rounded-xl" />
                  ) : consolePayload?.pending_publish_items.length ? (
                    consolePayload.pending_publish_items.map((item) => (
                      <ArticleCard
                        key={item.id}
                        item={item}
                        selected={selectedArticleId === item.id}
                        actionLabel="发布"
                        actionBusy={actionKey === `publish-${item.id}`}
                        actionDisabled={!canPublish}
                        onSelect={() => setSelectedArticleId(item.id)}
                        onAction={canPublish ? () => void handlePublish(item.id) : undefined}
                      />
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-border bg-muted/20 px-4 py-10 text-center text-sm text-muted-foreground">
                      当前没有待发布知识。
                    </div>
                  )}
                </div>
              </div>

              <div className="app-card">
                <div className="flex items-center gap-2 border-b border-border px-5 py-4 text-base font-medium text-foreground">
                  <RadioTower className="h-4 w-4 text-muted-foreground" />
                  当前生效版本
                </div>
                <div className="space-y-3 p-5">
                  {consoleLoading ? (
                    <div className="app-skeleton h-32 w-full rounded-xl" />
                  ) : consolePayload?.current_effective_items.length ? (
                    consolePayload.current_effective_items.map((item) => (
                      <ArticleCard
                        key={item.id}
                        item={item}
                        selected={selectedArticleId === item.id}
                        actionLabel="撤回"
                        actionBusy={actionKey === `withdraw-${item.id}`}
                        actionDisabled={!canPublish}
                        onSelect={() => setSelectedArticleId(item.id)}
                        onAction={canPublish ? () => void handleWithdraw(item.id) : undefined}
                      />
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-border bg-muted/20 px-4 py-10 text-center text-sm text-muted-foreground">
                      当前没有正在生效的发布版本。
                    </div>
                  )}
                </div>
              </div>

              <div className="app-card">
                <div className="flex items-center gap-2 border-b border-border px-5 py-4 text-base font-medium text-foreground">
                  <History className="h-4 w-4 text-muted-foreground" />
                  版本记录
                </div>
                <div className="space-y-3 p-5">
                  {versionsLoading ? (
                    <div className="app-skeleton h-40 w-full rounded-xl" />
                  ) : versions.length ? (
                    versions.map((item) => {
                      const statusMeta = getStatusMeta(item.status);
                      const active = selectedArticleId === item.id;
                      return (
                        <button
                          key={item.id}
                          type="button"
                          className={`w-full rounded-xl border p-4 text-left transition-colors ${active ? "border-primary bg-primary/5" : "border-border bg-card hover:bg-muted/30"}`}
                          onClick={() => setSelectedArticleId(item.id)}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="text-sm font-medium text-foreground">V{item.version} · {item.title}</div>
                            <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${statusMeta.className}`}>{statusMeta.label}</span>
                          </div>
                          <div className="mt-2 text-xs text-muted-foreground">
                            发布时间：{formatDateTimeLocal(item.published_at)} · 发布人：{item.published_by_name || "无"}
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            更新时间：{formatDateTimeLocal(item.updated_at)} · {item.retrieval_status_label}
                          </div>
                        </button>
                      );
                    })
                  ) : (
                    <div className="rounded-xl border border-dashed border-border bg-muted/20 px-4 py-10 text-center text-sm text-muted-foreground">
                      请选择一个知识条目查看版本链。
                    </div>
                  )}
                </div>
              </div>
            </section>

            <section className="app-card p-6">
              <div className="flex items-center gap-2 text-base font-medium text-foreground">
                <BookOpen className="h-4 w-4 text-muted-foreground" />
                条目详情
              </div>
              {selectedArticle ? (
                <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
                  <div className="space-y-3">
                    <div>
                      <div className="text-sm text-muted-foreground">标题</div>
                      <div className="mt-1 text-base font-medium text-foreground">{selectedArticle.title}</div>
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground">摘要</div>
                      <div className="mt-1 rounded-xl border border-border bg-muted/20 p-4 text-sm leading-7 text-foreground/90">
                        {selectedArticle.body_excerpt || selectedArticle.body || "无"}
                      </div>
                    </div>
                  </div>
                  <div className="space-y-3 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">状态</span>
                      <span className="text-foreground">{getStatusMeta(selectedArticle.status).label}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">系列 / 版本</span>
                      <span className="text-foreground">#{selectedArticle.series_id} / V{selectedArticle.version}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">发布人</span>
                      <span className="text-foreground">{selectedArticle.published_by_name || "无"}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">发布时间</span>
                      <span className="text-foreground">{formatDateTimeLocal(selectedArticle.published_at)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">审核人</span>
                      <span className="text-foreground">{selectedArticle.reviewed_by_name || "无"}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">来源工单</span>
                      <span className="text-foreground">{selectedArticle.source_work_order_id ? `#${selectedArticle.source_work_order_id}` : "无"}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">检索库状态</span>
                      <span className="text-foreground">{selectedArticle.retrieval_status_label}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="mt-4 rounded-xl border border-dashed border-border bg-muted/20 px-4 py-10 text-center text-sm text-muted-foreground">
                  当前没有可查看的知识条目。
                </div>
              )}
            </section>
          </>
        ) : null}
      </main>
    </div>
  );
}
