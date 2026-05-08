"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import {
  fetchTaskDetail,
  fetchTaskExport,
  fetchHealth,
  createMaintenanceDevice,
  createWorkOrder,
  downloadJsonInBrowser,
  getApiBase,
  listMaintenanceDevices,
  retryMaintenanceTask,
  saveMaintenanceTaskExecutionTimeline,
  type MaintenanceDeviceItem,
  type MaintenanceTaskDetail,
} from "@/features/tasks/api";
import { Header } from "@/shared/components/brand/app-header";
import { getMaintenanceToken } from "@/features/auth/lib/token-store";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { formatDateTimeLocal, formatDurationBetween } from "@/shared/lib/utils";
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  Cpu,
  Download,
  FileCode,
  FileText,
  Loader2,
  RefreshCw,
  Server,
  Share2,
  Wrench,
  XCircle,
} from "lucide-react";

type TaskStatus = "running" | "completed" | "failed";
type DisplayStatus = TaskStatus | "loading";
type EventType = "connected" | "node_start" | "node_finish" | "report" | "error" | "done";

type TimelineEvent = {
  id: string;
  type: EventType;
  title: string;
  description: string;
  time: string;
};

function hasResolvedDiagnosisPayload(detail: MaintenanceTaskDetail | null, persistedReport?: string | null) {
  if (!detail) return false;
  if ((persistedReport || "").trim()) return true;
  const structured = detail.diagnosis_structured;
  if (!structured) return false;
  return Boolean(
    (structured.preliminary_conclusion || "").trim() ||
      (structured.most_likely_fault || "").trim() ||
      (structured.next_steps || []).length > 0 ||
      (structured.root_causes || []).length > 0,
  );
}

function inferTaskRuntimeStatus(detail: MaintenanceTaskDetail | null, persistedReport?: string | null): TaskStatus {
  if (!detail) return "running";
  if (hasResolvedDiagnosisPayload(detail, persistedReport)) return "completed";

  const timeline = Array.isArray(detail.execution_timeline) ? detail.execution_timeline : [];
  const timelineTypes = new Set(timeline.map((event) => String(event.type || "").toLowerCase()));
  if (timelineTypes.has("done")) return "completed";
  if (timelineTypes.has("stream_error") || timelineTypes.has("error")) return "failed";

  const rawStatus = String(detail.status || "").toLowerCase();
  if (rawStatus === "completed") return "completed";
  if (rawStatus === "skipped" || rawStatus === "failed") return "failed";
  return "running";
}

type KnowledgeRef = NonNullable<MaintenanceTaskDetail["source_refs"]>[number];

type RootCauseCandidate = {
  title: string;
  confidence: number;
  evidence: string;
};

type DiagnosisWorkspaceTab = "fault" | "actions" | "evidence" | "timeline";
type StructuredDiagnosisStep = Extract<
  NonNullable<NonNullable<MaintenanceTaskDetail["diagnosis_structured"]>["next_steps"]>[number],
  {
    title: string;
  }
>;

type StructuredProcedureStep = {
  key: string;
  stepNo: string | null;
  title: string;
  summary: string;
  sections: Array<{
    label: string;
    items: string[];
  }>;
  meta: string[];
};

function isPlanningLabel(text: string | null | undefined) {
  const normalized = (text || "").trim();
  if (!normalized) return false;
  return /作业步骤规划/.test(normalized);
}

function hasPlanningRuntimeEvents(
  runtimeEvents:
    | Array<{ title?: string | null; description?: string | null }>
    | null
    | undefined,
) {
  return (runtimeEvents || []).some(
    (event) => isPlanningLabel(event.title) || isPlanningLabel(event.description),
  );
}

function isStructuredDiagnosisStep(value: unknown): value is StructuredDiagnosisStep {
  return Boolean(value && typeof value === "object" && "title" in value);
}

function extractReportSection(report: string | null | undefined, headings: string[]) {
  const text = (report || "").trim();
  if (!text) return "";

  const escaped = headings.map((heading) => heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(?:${escaped.join("|")})\\s*([\\s\\S]*?)(?=\\n(?:■|\\*\\*)\\s*|$)`);
  const match = text.match(pattern);
  return match?.[1]?.trim() || "";
}

function normalizeSectionItems(section: string) {
  return section
    .split("\n")
    .map((line) => line.replace(/^[\-•●■\d．。、)\s]+/, "").trim())
    .filter(Boolean);
}

function stripReportHeadingMarkdown(text: string | null | undefined) {
  return (text || "")
    .replace(/\*\*/g, "")
    .replace(/^■\s*/gm, "")
    .trim();
}

function splitReportSentences(text: string | null | undefined) {
  return stripReportHeadingMarkdown(text)
    .split(/[；;。]/)
    .map((item) => item.replace(/^[\-•●■\d．。、)\s]+/, "").trim())
    .filter(Boolean);
}

function deriveConfidenceScore(
  refs: KnowledgeRef[],
  reasonSection: string,
  conclusionSection: string,
  actionItems: string[],
) {
  const evidenceScore = Math.min(refs.length * 12, 36);
  const conclusionScore = conclusionSection ? 18 : 0;
  const reasonScore = reasonSection ? 18 : 0;
  const actionScore = Math.min(actionItems.length * 6, 24);
  return Math.max(35, Math.min(92, 28 + evidenceScore + conclusionScore + reasonScore + actionScore));
}

function looksLikeProcessStatement(text: string) {
  return /(知识依据|步骤预案|风险提示|标准检修|执行准备|现场复核|先核对|可进入|建议先|已形成)/.test(text);
}

function compactFaultLabel(text: string | null | undefined) {
  const cleaned = (text || "").replace(/^[\-•●■\d．。、)\s]+/, "").trim();
  if (!cleaned) return "";
  const first = cleaned.split(/[；;。]/)[0]?.trim() || cleaned;
  return first.replace(/^最可能故障[:：]\s*/, "").trim();
}

function deriveReadableLikelyFault(
  structuredFault: string | null | undefined,
  rootCauseCandidates: RootCauseCandidate[],
  reasonSection: string,
  headline: string,
) {
  const normalizedStructured = compactFaultLabel(structuredFault);
  if (normalizedStructured && !looksLikeProcessStatement(normalizedStructured)) {
    return normalizedStructured;
  }
  const topCause = rootCauseCandidates.find((item) => {
    const title = compactFaultLabel(item.title);
    return title && !looksLikeProcessStatement(title);
  });
  if (topCause) return compactFaultLabel(topCause.title);
  const reasonLine = splitReportSentences(reasonSection).find((item) => !looksLikeProcessStatement(item));
  if (reasonLine) return compactFaultLabel(reasonLine);
  return compactFaultLabel(headline) || "待进一步定位";
}

function buildRootCauseCandidates(
  reasonSection: string,
  conclusionSection: string,
  refs: KnowledgeRef[],
  confidenceScore: number,
): RootCauseCandidate[] {
  const causeLines = [...splitReportSentences(reasonSection), ...splitReportSentences(conclusionSection)]
    .filter((item) => item.length >= 4)
    .slice(0, 4);

  return causeLines.map((line, index) => {
    const fallbackEvidence = refs[index]?.title || refs[index]?.source_name || "来源于当前知识命中与诊断结论";
    const excerptEvidence = refs[index]?.excerpt?.trim();
    return {
      title: line,
      confidence: Math.max(28, Math.min(95, confidenceScore - index * 14)),
      evidence: excerptEvidence || fallbackEvidence,
    };
  });
}

function getKnowledgeSectionLabel(ref: KnowledgeRef) {
  if (ref.section_path?.trim()) return ref.section_path.trim();
  if (ref.section_reference?.trim()) return ref.section_reference.trim();
  if (ref.page_reference?.trim()) return ref.page_reference.trim();
  const excerpt = ref.excerpt?.trim() || "";
  const matched = excerpt.match(/(?:章节|步骤|部件|页码|P\d+)[^，。；]*/);
  return matched?.[0] || "命中片段";
}

function normalizeRankingScoreToPercent(score: number) {
  if (!Number.isFinite(score) || score <= 0) return 0;
  // Saturating curve: preserve ordering while converting open-ended rerank scores to a readable 0-99% range.
  return Math.max(1, Math.min(99, Math.round((1 - Math.exp(-score / 3.2)) * 100)));
}

function getEvidenceSimilarity(refs: KnowledgeRef[], confidenceScore: number, structuredTopSimilarity?: number | null) {
  const rerankScores = refs
    .map((ref) => Number(ref.rerank_score))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (rerankScores.length > 0) {
    return `重排相关度 ${normalizeRankingScoreToPercent(Math.max(...rerankScores))}%`;
  }
  const retrievalScores = refs
    .map((ref) => Number(ref.retrieval_score))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (retrievalScores.length > 0) {
    return `召回相关度 ${normalizeRankingScoreToPercent(Math.max(...retrievalScores))}%`;
  }
  if (structuredTopSimilarity) return `重排相关度 ${structuredTopSimilarity}%`;
  if (refs.length === 0) return "--";
  const top = Math.max(confidenceScore - 6, 40);
  return `重排相关度 ${top}%`;
}

function getEvidenceSortScore(ref: KnowledgeRef) {
  const rerankScore = Number(ref.rerank_score);
  if (Number.isFinite(rerankScore) && rerankScore > 0) return rerankScore;
  const retrievalScore = Number(ref.retrieval_score);
  if (Number.isFinite(retrievalScore) && retrievalScore > 0) return retrievalScore;
  return -1;
}

function formatEvidenceScore(ref: KnowledgeRef, fallbackScore: number) {
  const rerankScore = Number(ref.rerank_score);
  if (Number.isFinite(rerankScore)) {
    return { label: "重排相关度", value: `${normalizeRankingScoreToPercent(rerankScore)}%` };
  }
  const retrievalScore = Number(ref.retrieval_score);
  if (Number.isFinite(retrievalScore)) {
    return { label: "召回相关度", value: `${normalizeRankingScoreToPercent(retrievalScore)}%` };
  }
  return { label: "参考相关度", value: `${fallbackScore}%` };
}

function formatDurationFromSeconds(totalSeconds: number): string | null {
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return null;
  const sec = Math.floor(totalSeconds);
  if (sec === 0) return "不足 1 秒";
  if (sec < 60) return `${sec} 秒`;
  const minutes = Math.floor(sec / 60);
  const seconds = sec % 60;
  if (minutes < 60) return seconds > 0 ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const remainMinutes = minutes % 60;
  return remainMinutes > 0 ? `${hours} 小时 ${remainMinutes} 分` : `${hours} 小时`;
}

function formatTimelineDuration(eventList: TimelineEvent[]): string | null {
  if (eventList.length < 2) return null;
  const parseClock = (value: string) => {
    const directTimestamp = Date.parse(value);
    if (!Number.isNaN(directTimestamp)) return Math.floor(directTimestamp / 1000);

    const matched = value.trim().match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
    if (!matched) return null;
    const hour = Number(matched[1]);
    const minute = Number(matched[2]);
    const second = Number(matched[3] ?? "0");
    if (hour > 23 || minute > 59 || second > 59) return null;
    return hour * 3600 + minute * 60 + second;
  };

  const first = parseClock(eventList[0]?.time || "");
  const last = parseClock(eventList[eventList.length - 1]?.time || "");
  if (first == null || last == null) return null;
  const diff = last >= first ? last - first : last + 24 * 3600 - first;
  return formatDurationFromSeconds(diff);
}

function getTimelineEventVisual(type: EventType) {
  if (type === "done" || type === "report") {
    return {
      badgeClass: "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
      bubbleClass: "border-emerald-500/20 bg-emerald-500/8",
    };
  }
  if (type === "error") {
    return {
      badgeClass: "border-red-500/25 bg-red-500/10 text-red-700 dark:text-red-300",
      bubbleClass: "border-red-500/20 bg-red-500/8",
    };
  }
  if (type === "node_finish") {
    return {
      badgeClass: "border-indigo-500/25 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300",
      bubbleClass: "border-indigo-500/20 bg-indigo-500/8",
    };
  }
  return {
    badgeClass: "border-sky-500/25 bg-sky-500/10 text-sky-700 dark:text-sky-300",
    bubbleClass: "border-sky-500/20 bg-sky-500/8",
  };
}

function parseTimelineEventTimeMs(value: string | null | undefined): number | null {
  const normalized = String(value || "").trim();
  if (!normalized) return null;
  const timestamp = Date.parse(normalized);
  if (!Number.isNaN(timestamp)) return timestamp;
  const matched = normalized.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (!matched) return null;
  const base = new Date();
  base.setHours(Number(matched[1]), Number(matched[2]), Number(matched[3] ?? "0"), 0);
  return base.getTime();
}

function normalizeProcedureStepKey(text: string | null | undefined) {
  return (text || "").replace(/\s+/g, " ").replace(/[：:，。,；;]+$/g, "").trim();
}

function tidyChineseProcedureText(text: string | null | undefined) {
  return (text || "")
    .replace(/\s+/g, " ")
    .replace(/\s*([：:，。,；;、）])/g, "$1")
    .replace(/([（])\s*/g, "$1")
    .replace(/(拆下|取下|松开|打开|关闭|断开|拔下|敲平|排放|加注|检查|取出)\s+/g, "$1")
    .replace(/([\u4e00-\u9fff])\s+(?=\d)/g, "$1")
    .replace(/(\d)\s+(?=[\u4e00-\u9fff])/g, "$1")
    .trim();
}

function splitProcedureItems(text: string | null | undefined) {
  const compact = (text || "").replace(/\s+/g, " ").trim();
  if (!compact) return [];
  if (compact.includes(" ")) {
    return compact
      .split(/\s+/)
      .map((item) => tidyChineseProcedureText(item))
      .filter(Boolean);
  }
  return [tidyChineseProcedureText(compact)];
}

function splitProcedureActionItems(text: string | null | undefined) {
  const compact = (text || "").replace(/\s+/g, " ").trim();
  if (!compact) return [];
  const parts = compact
    .split(/(?=取下|拆下|松开|断开|打开|关闭|拔下|取出)/)
    .map((item) => tidyChineseProcedureText(item))
    .filter(Boolean);
  return parts.length > 0 ? parts : [tidyChineseProcedureText(compact)];
}

function dedupeProcedureSteps(items: string[]) {
  const deduped: string[] = [];
  const stepIndexByNo = new Map<string, number>();
  const seen = new Set<string>();

  for (const rawItem of items) {
    const item = normalizeProcedureStepKey(rawItem);
    if (!item) continue;
    if (seen.has(item)) continue;

    const matched = item.match(/^(\d+)\.\s*(.*)$/);
    if (matched) {
      const stepNo = matched[1];
      const existingIndex = stepIndexByNo.get(stepNo);
      if (existingIndex != null) {
        if (item.length > deduped[existingIndex].length) {
          seen.delete(deduped[existingIndex]);
          deduped[existingIndex] = item;
          seen.add(item);
        }
        continue;
      }
      stepIndexByNo.set(stepNo, deduped.length);
    }

    deduped.push(item);
    seen.add(item);
  }

  return deduped;
}

/** 标准作业步骤与诊断建议步骤的弱匹配（笔画级二元组 + 字符重合），用于无同名模板时的对齐提示 */
const DIAG_STEP_MATCH_MIN_SCORE = 6;

type DiagnosisMatchCandidate = { diagIndex: number; text: string };

function corpusForTaskStepMatch(step: { title?: string; instruction?: string }) {
  return tidyChineseProcedureText(`${step.title || ""} ${(step.instruction || "").slice(0, 160)}`);
}

function overlapScoreForDiagnosisLink(a: string, b: string): number {
  const A = (a || "").replace(/\s/g, "");
  const B = (b || "").replace(/\s/g, "");
  if (!A || !B) return 0;
  let score = 0;
  for (let i = 0; i < A.length - 1; i++) {
    if (B.includes(A.slice(i, i + 2))) score += 3;
  }
  const shorter = A.length <= B.length ? A : B;
  const longer = A.length <= B.length ? B : A;
  for (let i = 0; i < shorter.length; i++) {
    if (longer.includes(shorter[i]!)) score += 0.12;
  }
  return score;
}

function buildDiagnosisMatchCandidates(
  isProceduralAnswer: boolean,
  structuredProcedureSteps: StructuredProcedureStep[],
  backendStructuredNextSteps: StructuredDiagnosisStep[],
  displayedRecommendedSteps: string[],
): DiagnosisMatchCandidate[] {
  if (isProceduralAnswer && structuredProcedureSteps.length > 0) {
    return structuredProcedureSteps.map((item, diagIndex) => ({
      diagIndex,
      text: tidyChineseProcedureText(
        [item.title, item.summary, ...(item.meta ?? [])].filter(Boolean).join(" "),
      ),
    })).filter((c) => c.text.length > 0);
  }
  if (backendStructuredNextSteps.length > 0) {
    return backendStructuredNextSteps
      .map((item, diagIndex) => ({
        diagIndex,
        text: tidyChineseProcedureText(item.raw_text || item.title || item.summary || ""),
      }))
      .filter((c) => c.text.length > 0);
  }
  return displayedRecommendedSteps
    .map((text, diagIndex) => ({
      diagIndex,
      text: tidyChineseProcedureText(text),
    }))
    .filter((c) => c.text.length > 0);
}

/** 诊断工作区每一行建议 → 对应的标准作业步骤标题（便于反向跳转心智模型） */
function computeDiagnosisToStandardStepTitles(
  steps: Array<{ title?: string; instruction?: string; step_order?: number }> | undefined,
  candidates: DiagnosisMatchCandidate[],
): (string | null)[] {
  const list = steps ?? [];
  if (list.length === 0 || candidates.length === 0) return candidates.map(() => null);

  const sameLengthPairing = candidates.length === list.length;
  if (sameLengthPairing) {
    return candidates.map((_, candIdx) => list[candIdx]?.title?.trim() || null);
  }

  return candidates.map((c) => {
    let best: { title: string; score: number } | null = null;
    for (const step of list) {
      const corpus = corpusForTaskStepMatch(step);
      const score = overlapScoreForDiagnosisLink(corpus, c.text);
      const title = step.title?.trim();
      if (!title) continue;
      if (!best || score > best.score) {
        best = { title, score };
      }
    }
    if (best && best.score >= DIAG_STEP_MATCH_MIN_SCORE) return best.title;
    return null;
  });
}

function parseStructuredProcedureStep(rawItem: string, index: number): StructuredProcedureStep {
  const compact = normalizeProcedureStepKey(rawItem);
  const matched = compact.match(/^(\d+)\.\s*(.*)$/);
  const stepNo = matched?.[1] ?? null;
  const body = (matched?.[2] ?? compact).trim();

  const meta: string[] = [];
  let cleanedBody = body;

  const toolMatch = cleanedBody.match(/所需工具[:：]?\s*([^。；]+)$/);
  if (toolMatch) {
    meta.push(`所需工具：${toolMatch[1].trim()}`);
    cleanedBody = cleanedBody.slice(0, toolMatch.index).trim();
  }

  const torqueMatch = cleanedBody.match(/([^。；]*扭矩[:：]?\s*[^。；]+)/);
  if (torqueMatch) {
    meta.unshift(torqueMatch[1].trim());
    cleanedBody = cleanedBody.replace(torqueMatch[1], "").trim();
  }

  let title = cleanedBody;
  let remainder = "";
  const firstSentence = cleanedBody.match(/^([^。；]+)[。；]?\s*(.*)$/);
  if (firstSentence) {
    title = firstSentence[1].trim();
    remainder = firstSentence[2].trim();
  }

  const actionSplit = title.match(/^([^\s]+)\s+(.+)$/);
  if (actionSplit && actionSplit[1].length <= 12 && actionSplit[2].length >= 4) {
    title = actionSplit[1].trim();
    remainder = [actionSplit[2].trim(), remainder].filter(Boolean).join(" ");
  }

  const sections: Array<{ label: string; items: string[] }> = [];
  let summary = "";
  let mutableRemainder = remainder;

  const patternHandlers = [
    {
      pattern: /(依次松开以下部件的固定螺栓)[:：]\s*([\s\S]*?)(?=(具体操作顺序为)[:：]|$)/,
      split: splitProcedureItems,
    },
    {
      pattern: /(具体操作顺序为)[:：]\s*([\s\S]*?)(?=$)/,
      split: splitProcedureActionItems,
    },
    {
      pattern: /(依次取下)[:：]\s*([\s\S]*?)(?=$)/,
      split: splitProcedureItems,
    },
  ] as const;

  for (const handler of patternHandlers) {
    const matchSection = mutableRemainder.match(handler.pattern);
    if (!matchSection) continue;
    const label = tidyChineseProcedureText(matchSection[1]);
    const items = handler.split(matchSection[2]);
    if (items.length > 0) {
      sections.push({ label, items });
    }
    mutableRemainder = mutableRemainder.replace(matchSection[0], " ").trim();
  }

  summary = tidyChineseProcedureText(mutableRemainder)
    .replace(/\s*具体操作顺序为\s*$/g, "")
    .replace(/\s*依次取下\s*$/g, "")
    .trim();

  if (!summary && sections.length === 0) {
    summary = "按手册原文执行该步骤。";
  }

  return {
    key: `${stepNo ?? index}-${title}-${summary}`.trim(),
    stepNo,
    title: tidyChineseProcedureText(title) || `步骤 ${index + 1}`,
    summary,
    sections,
    meta,
  };
}

function normalizeStructuredProcedureStep(
  step: StructuredDiagnosisStep,
  index: number,
): StructuredProcedureStep {
  const stepNo = step.step_no != null ? String(step.step_no) : null;
  const title = tidyChineseProcedureText(step.title) || `步骤 ${index + 1}`;
  const summary = tidyChineseProcedureText(step.summary || "");
  const sections = Array.isArray(step.sections)
    ? step.sections
        .map((section) => ({
          label: tidyChineseProcedureText(section.label || ""),
          items: Array.isArray(section.items)
            ? section.items.map((item) => tidyChineseProcedureText(item)).filter(Boolean)
            : [],
        }))
        .filter((section) => section.label && section.items.length > 0)
    : [];
  const meta = Array.isArray(step.meta) ? step.meta.map((item) => item.trim()).filter(Boolean) : [];

  return {
    key: `${stepNo ?? index}-${title}-${summary}-${step.raw_text ?? ""}`.trim(),
    stepNo,
    title,
    summary,
    sections,
    meta,
  };
}

function sortStructuredProcedureSteps(items: StructuredProcedureStep[]) {
  return [...items].sort((left, right) => {
    const leftStepNo = left.stepNo ? Number(left.stepNo) : Number.NaN;
    const rightStepNo = right.stepNo ? Number(right.stepNo) : Number.NaN;
    const leftHasStepNo = Number.isFinite(leftStepNo);
    const rightHasStepNo = Number.isFinite(rightStepNo);

    if (leftHasStepNo && rightHasStepNo && leftStepNo !== rightStepNo) {
      return leftStepNo - rightStepNo;
    }
    if (leftHasStepNo !== rightHasStepNo) {
      return leftHasStepNo ? -1 : 1;
    }
    return 0;
  });
}

const statusMeta = {
  loading: {
    label: "加载中",
    badgeClass: "border-slate-500/20 bg-slate-500/8 text-slate-600 dark:text-slate-300",
    panelClass: "border-slate-500/15 bg-slate-500/5",
    summary: "正在获取任务详情，请稍候。",
    icon: Loader2,
  },
  completed: {
    label: "诊断完成",
    badgeClass: "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    panelClass: "border-emerald-500/20 bg-emerald-500/6",
    summary: "结论与建议已同步，可直接复核并导出。",
    icon: CheckCircle2,
  },
  running: {
    label: "诊断中",
    badgeClass: "border-blue-500/25 bg-blue-500/10 text-blue-600 dark:text-blue-400",
    panelClass: "border-blue-500/20 bg-blue-500/6",
    summary: "协作诊断流已建立，结论和时间线会持续更新。",
    icon: Loader2,
  },
  failed: {
    label: "诊断失败",
    badgeClass: "border-red-500/25 bg-red-500/10 text-red-600 dark:text-red-400",
    panelClass: "border-red-500/20 bg-red-500/6",
    summary: "当前流程中断，请检查最近错误事件后重新运行。",
    icon: XCircle,
  },
} as const;

function StatusBadge({ status }: { status: DisplayStatus }) {
  const meta = statusMeta[status];
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium ${meta.badgeClass}`}>
      <Icon className={`h-4 w-4 ${status === "running" || status === "loading" ? "animate-spin" : ""}`} />
      {meta.label}
    </span>
  );
}

function OverviewItem({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof Clock;
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/35 p-3">
      <div className="mb-1 text-xs text-muted-foreground">{label}</div>
      <div className="inline-flex items-center gap-1.5 text-sm text-foreground">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        <span>{value}</span>
      </div>
    </div>
  );
}

export default function TaskDetailPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const backHref = useMemo(() => {
    const raw = searchParams.get("from")?.trim();
    if (raw && raw.startsWith("/")) return raw;
    return "/tasks";
  }, [searchParams]);
  const numericTaskId = useMemo(() => (/^\d+$/.test(taskId) ? Number(taskId) : null), [taskId]);
  const streamRef = useRef<EventSource | null>(null);
  const eventsRef = useRef<TimelineEvent[]>([]);
  const ragConclusionRef = useRef<string | null>(null);
  const autoStartGuardRef = useRef(false);

  const [task, setTask] = useState<MaintenanceTaskDetail | null>(null);
  const [status, setStatus] = useState<TaskStatus>("running");
  const [detailLoaded, setDetailLoaded] = useState(false);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [ragConclusion, setRagConclusion] = useState<string | null>(null);
  const [runStartedAtMs, setRunStartedAtMs] = useState<number | null>(null);
  const [runningNowMs, setRunningNowMs] = useState<number>(() => Date.now());
  const [streaming, setStreaming] = useState(false);
  const [createWorkOrderOpen, setCreateWorkOrderOpen] = useState(false);
  const [workOrderSubmitting, setWorkOrderSubmitting] = useState(false);
  const [workOrderError, setWorkOrderError] = useState<string | null>(null);
  const [matchedDevice, setMatchedDevice] = useState<MaintenanceDeviceItem | null>(null);
  const [matchingDevice, setMatchingDevice] = useState(false);
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<DiagnosisWorkspaceTab>("fault");
  const hasPersistedDiagnosis = hasResolvedDiagnosisPayload(task, ragConclusionRef.current);
  const hasTerminalTimeline = Boolean(task?.execution_timeline?.some((event) => event.type === "done"));
  const shouldBackfillReport =
    task != null &&
    status === "completed" &&
    !ragConclusionRef.current?.trim() &&
    !task.diagnosis_structured?.preliminary_conclusion?.trim();
  const workOrderAssetCode = task?.asset_code || "";
  const workOrderDeviceType = task?.equipment_type || "";
  const workOrderDeviceModel = task?.equipment_model?.trim() || "";

  const getTaskStreamGuardKey = useCallback(
    () => (numericTaskId == null ? null : `maintenance-task-stream-started:${numericTaskId}`),
    [numericTaskId],
  );

  const clearProcessActionParam = useCallback(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (url.searchParams.get("action") !== "process") return;
    url.searchParams.delete("action");
    const nextQuery = url.searchParams.toString();
    const nextUrl = `${url.pathname}${nextQuery ? `?${nextQuery}` : ""}${url.hash}`;
    window.history.replaceState(window.history.state, "", nextUrl);
  }, []);

  const closeStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    setStreaming(false);
  }, []);

  const appendEvent = useCallback((type: EventType, title: string, description: string) => {
    const id = `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const evt = {
      id,
      type,
      title,
      description,
      time: new Date().toISOString(),
    };
    const next = [...eventsRef.current, evt];
    eventsRef.current = next;
    setEvents(next);
    if (next.length === 1) {
      const firstEventTime = parseTimelineEventTimeMs(evt.time);
      if (firstEventTime != null) {
        setRunStartedAtMs(firstEventTime);
      }
    }
    return next;
  }, []);

  const syncTaskDetailState = useCallback((detail: MaintenanceTaskDetail) => {
    setTask(detail);
    const persistedReport =
      detail.diagnosis_report?.trim() ||
      detail.diagnosis_structured?.preliminary_conclusion?.trim() ||
      null;
    setRagConclusion(persistedReport);
    ragConclusionRef.current = persistedReport;
    if (Array.isArray(detail.execution_timeline) && detail.execution_timeline.length > 0) {
      const restored = detail.execution_timeline as TimelineEvent[];
      setEvents(restored);
      eventsRef.current = restored;
      setRunStartedAtMs(parseTimelineEventTimeMs(restored[0]?.time) ?? null);
    } else {
      setEvents([]);
      eventsRef.current = [];
      setRunStartedAtMs(parseTimelineEventTimeMs(detail.run_started_at) ?? null);
    }
    setStatus(inferTaskRuntimeStatus(detail, persistedReport));
  }, []);

  const loadTaskDetail = useCallback(async () => {
    if (numericTaskId == null) return null;
    try {
      const detail = await fetchTaskDetail(numericTaskId);
      syncTaskDetailState(detail);
      return detail;
    } catch {
      setStatus("failed");
      return null;
    } finally {
      setDetailLoaded(true);
    }
  }, [numericTaskId, syncTaskDetailState]);

  const startDiagnosisStream = useCallback(
    (sourceTask?: MaintenanceTaskDetail | null) => {
      if (numericTaskId == null) return;
      const currentTask = sourceTask ?? task;
      if (currentTask == null) return;

      const streamGuardKey = getTaskStreamGuardKey();
      if (streamGuardKey && typeof window !== "undefined") {
        window.sessionStorage.setItem(streamGuardKey, "1");
      }

      closeStream();
      setStreaming(true);
      setStatus("running");

      const query = currentTask.symptom_description || currentTask.fault_type || currentTask.title || "";
      const params = new URLSearchParams({
        maintenance_task_id: String(numericTaskId),
        query,
        equipment_type: currentTask.equipment_type || "",
        maintenance_level: currentTask.maintenance_level || "standard",
        model_provider: "openai",
      });
      if (currentTask.equipment_model) params.set("equipment_model", currentTask.equipment_model);
      if (currentTask.fault_type) params.set("fault_type", currentTask.fault_type);

      const source = new EventSource(`${getApiBase()}/api/v1/agents/assist/stream?${params.toString()}`);
      streamRef.current = source;

      source.addEventListener("connected", () => appendEvent("connected", "SSE 连接建立", "已连接协作诊断流"));
      source.addEventListener("stage_start", (e) => {
        try {
          const payload = JSON.parse((e as MessageEvent).data) as { title?: string; message?: string };
          appendEvent("node_start", payload.title || "阶段开始", payload.message || "正在执行");
        } catch {
          appendEvent("node_start", "阶段开始", "正在执行");
        }
      });
      source.addEventListener("stage_finish", (e) => {
        try {
          const payload = JSON.parse((e as MessageEvent).data) as { title?: string; summary?: string };
          appendEvent("node_finish", payload.title || "阶段完成", payload.summary || "执行完成");
        } catch {
          appendEvent("node_finish", "阶段完成", "执行完成");
        }
      });
      source.addEventListener("report", (e) => {
        try {
          const payload = JSON.parse((e as MessageEvent).data) as { report?: string };
          const reportText = (payload.report || "").trim();
          appendEvent("report", "RAG 诊断报告生成", reportText || "已生成诊断摘要");
          if (reportText) {
            setRagConclusion(reportText);
            ragConclusionRef.current = reportText;
          }
        } catch {
          appendEvent("report", "诊断报告生成", "已生成诊断摘要");
        }
      });
      source.addEventListener("stream_error", (e) => {
        try {
          const payload = JSON.parse((e as MessageEvent).data) as { error?: string };
          appendEvent("error", "诊断失败", payload.error || "流式执行失败");
        } catch {
          appendEvent("error", "诊断失败", "流式执行失败");
        }
        setStatus("failed");
        closeStream();
      });
      source.addEventListener("done", () => {
        appendEvent("done", "诊断任务完成", "已结束并回写任务状态");
        setStatus("completed");
        closeStream();
        void loadTaskDetail();
      });
      source.onerror = () => {
        closeStream();
      };
    },
    [appendEvent, closeStream, getTaskStreamGuardKey, loadTaskDetail, numericTaskId, task],
  );

  useEffect(() => {
    if (searchParams.get("action") !== "process") return;
    const t = window.setTimeout(() => {
      document.getElementById("task-handle-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 300);
    return () => window.clearTimeout(t);
  }, [searchParams]);

  useEffect(() => {
    if (numericTaskId == null) return;
    void (async () => {
      const detail = await loadTaskDetail();
      if (detail == null || autoStartGuardRef.current) return;
      const streamGuardKey = getTaskStreamGuardKey();
      const hasStartedInSession =
        streamGuardKey && typeof window !== "undefined" ? window.sessionStorage.getItem(streamGuardKey) === "1" : false;
      const hasTimeline = Array.isArray(detail.execution_timeline) && detail.execution_timeline.length > 0;
      const hasPersistedReport = Boolean(
        detail.diagnosis_report?.trim() || detail.diagnosis_structured?.preliminary_conclusion?.trim(),
      );
      const rawStatus = String(detail.status || "").toLowerCase();
      const shouldAutoStartInitialRun =
        searchParams.get("action") === "process" &&
        !hasStartedInSession &&
        !hasTimeline &&
        !hasPersistedReport &&
        rawStatus === "pending" &&
        (detail.completed_steps ?? 0) === 0;
      if (shouldAutoStartInitialRun) {
        autoStartGuardRef.current = true;
        startDiagnosisStream(detail);
      }
      if (searchParams.get("action") === "process") {
        clearProcessActionParam();
      }
    })();
  }, [clearProcessActionParam, getTaskStreamGuardKey, loadTaskDetail, numericTaskId, searchParams, startDiagnosisStream]);

  useEffect(() => () => closeStream(), []);

  useEffect(() => {
    if (numericTaskId == null || streaming) return;
    if (hasPersistedDiagnosis && !shouldBackfillReport) return;
    if (hasTerminalTimeline && !shouldBackfillReport) return;
    const rawStatus = String(task?.status || "").toLowerCase();
    const shouldPoll = rawStatus === "pending" || rawStatus === "in_progress" || status === "running";
    if (!shouldPoll) return;
    const tick = () => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      void loadTaskDetail();
    };
    tick();
    const id = window.setInterval(tick, 4000);
    return () => window.clearInterval(id);
  }, [
    hasPersistedDiagnosis,
    hasTerminalTimeline,
    loadTaskDetail,
    numericTaskId,
    shouldBackfillReport,
    status,
    streaming,
    task?.status,
  ]);

  useEffect(() => {
    if (status !== "running" || runStartedAtMs == null) return;
    setRunningNowMs(Date.now());
    const id = window.setInterval(() => setRunningNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [status, runStartedAtMs]);

  useEffect(() => {
    if (!createWorkOrderOpen) return;
    let cancelled = false;
    setWorkOrderError(null);
    setMatchedDevice(null);
    setMatchingDevice(true);
    const token = getMaintenanceToken();
    if (!token) {
      setWorkOrderError("当前未检测到检修域登录状态，无法生成工单。");
      setMatchingDevice(false);
      return;
    }
    if (!workOrderAssetCode) {
      setWorkOrderError("当前任务缺少设备编号，无法自动关联检修设备。");
      setMatchingDevice(false);
      return;
    }
    void (async () => {
      try {
        const deviceList = await listMaintenanceDevices(token, 1);
        if (cancelled) return;
        const exact = deviceList.items.find((item) => item.asset_code === workOrderAssetCode) ?? null;
        if (exact) {
          if (cancelled) return;
          setMatchedDevice(exact);
          return;
        }
        const createdDevice = await createMaintenanceDevice(token, {
          device_type: workOrderDeviceType || "未分类设备",
          model: workOrderDeviceModel || "AUTO-GENERATED",
          asset_code: workOrderAssetCode,
          location: "智能诊断自动建档",
        });
        if (cancelled) return;
        setMatchedDevice(createdDevice);
      } catch (e) {
        if (cancelled) return;
        setWorkOrderError(e instanceof Error ? e.message : "加载检修设备失败");
      } finally {
        if (cancelled) return;
        setMatchingDevice(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [createWorkOrderOpen, workOrderAssetCode, workOrderDeviceType, workOrderDeviceModel]);

  const retry = () => {
    if (numericTaskId == null) return;
    closeStream();
    void (async () => {
      try {
        let resetTask: MaintenanceTaskDetail;
        try {
          resetTask = await retryMaintenanceTask(numericTaskId);
        } catch (e) {
          const message = e instanceof Error ? e.message : "";
          if (!message.includes("Not Found")) {
            throw e;
          }
          await saveMaintenanceTaskExecutionTimeline(numericTaskId, [], null);
          resetTask = await fetchTaskDetail(numericTaskId);
        }
        syncTaskDetailState(resetTask);
        setRunStartedAtMs(Date.now());
        toast.success("已重置诊断状态，正在重新运行");
        startDiagnosisStream(resetTask);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "重新运行失败");
      }
    })();
  };

  const exportReport = () => {
    void (async () => {
      if (numericTaskId == null) return;
      try {
        const payload = await fetchTaskExport(numericTaskId);
        const stamp = new Date().toISOString().slice(0, 19).replace(/:/g, "-");
        downloadJsonInBrowser(`检修任务-${numericTaskId}-导出-${stamp}.json`, payload);
        toast.success("导出成功，文件已开始下载");
      } catch {
        toast.error("导出失败，请稍后重试");
      }
    })();
  };

  const createLinkedWorkOrder = () => {
    if (!task) return;
    const token = getMaintenanceToken();
    if (!token) {
      setWorkOrderError("当前未检测到检修域登录状态，无法生成工单。");
      return;
    }
    if (!matchedDevice) {
      setWorkOrderError("当前任务尚未匹配到检修设备，无法生成工单。");
      return;
    }
    setWorkOrderSubmitting(true);
    setWorkOrderError(null);
    void (async () => {
      try {
        const createdWorkOrder = await createWorkOrder(token, {
          device_id: matchedDevice.id,
          maintenance_level: task.maintenance_level || "standard",
          source_task_id: numericTaskId ?? undefined,
        });
        const workOrderId = Number(createdWorkOrder?.id);
        setCreateWorkOrderOpen(false);
        toast.success("已基于当前诊断任务生成检修工单");
        if (Number.isFinite(workOrderId) && workOrderId > 0) {
          router.push(`/tickets/${workOrderId}`);
        }
      } catch (e) {
        setWorkOrderError(e instanceof Error ? e.message : "生成工单失败");
      } finally {
        setWorkOrderSubmitting(false);
      }
    })();
  };

  const deviceLabel = task
    ? `${task.equipment_type}${task.equipment_model ? ` ${task.equipment_model}` : ""}`
    : "设备";
  const headline = task?.symptom_description || task?.title || "正在同步任务信息";
  const timelineDuration = useMemo(() => formatTimelineDuration(events), [events]);
  const runningDuration =
    status === "running" && runStartedAtMs != null
      ? formatDurationFromSeconds(Math.max(0, Math.floor((runningNowMs - runStartedAtMs) / 1000)))
      : null;
  const duration =
    status === "running"
      ? runningDuration || "进行中"
      : timelineDuration ||
        (task && status === "completed"
          ? formatDurationBetween(task.run_started_at || task.created_at, task.run_finished_at || task.updated_at)
          : null) ||
        "--";
  const latestReportEvent = [...events].reverse().find((event) => event.type === "report" || event.type === "done");
  const latestErrorEvent = [...events].reverse().find((event) => event.type === "error");
  const citedRefs = task?.source_refs ?? [];
  const conclusionSection = stripReportHeadingMarkdown(
    extractReportSection(ragConclusion, ["■ 诊断结论", "诊断结论", "结论"]),
  );
  const reasonSection = stripReportHeadingMarkdown(
    extractReportSection(ragConclusion, ["■ 原因判断", "原因判断"]),
  );
  const knowledgeSection = stripReportHeadingMarkdown(
    extractReportSection(ragConclusion, ["■ 知识依据", "知识依据"]),
  );
  const llmActionSection = stripReportHeadingMarkdown(
    extractReportSection(ragConclusion, ["■ 建议措施", "建议措施", "■ 下一步建议", "下一步建议"]),
  );
  const llmKnowledgeItems = normalizeSectionItems(knowledgeSection);
  const llmActionItems = normalizeSectionItems(llmActionSection);
  const sourceRefPreview = useMemo(
    () =>
      [...citedRefs]
        .sort((left, right) => {
          const scoreGap = getEvidenceSortScore(right) - getEvidenceSortScore(left);
          if (scoreGap !== 0) return scoreGap;
          return String(left.title || "").localeCompare(String(right.title || ""), "zh-CN");
        }),
    [citedRefs],
  );
  const ragFallbackText =
    citedRefs.length > 0
      ? `已基于 ${citedRefs.length} 条知识依据启动 RAG 检索，请结合引用条目继续复核当前结论。`
      : "当前尚未拿到稳定知识引用，建议补充设备型号、故障现象或现场图片后重新触发诊断。";
  const structuredDiagnosis = task?.diagnosis_structured ?? null;
  const isProceduralAnswer = structuredDiagnosis?.answer_mode === "procedure";

  const conclusionText =
    !detailLoaded
      ? "正在加载任务详情与诊断结果。"
      : status === "completed"
      ? structuredDiagnosis?.preliminary_conclusion || conclusionSection || ragConclusion || latestReportEvent?.description || ragFallbackText
      : status === "failed"
        ? latestErrorEvent?.description || "协作诊断流中断，建议检查输入信息或重新运行。"
        : structuredDiagnosis?.preliminary_conclusion || conclusionSection || ragConclusion || latestReportEvent?.description || "协作诊断已接入实时流，系统正在进行知识召回、依据汇总和处理建议生成。";

  const displayStatus: DisplayStatus = detailLoaded ? status : "loading";
  const statusSummaryMeta = statusMeta[displayStatus];
  const confidenceScore = structuredDiagnosis?.confidence ?? deriveConfidenceScore(citedRefs, reasonSection, conclusionSection, llmActionItems);
  const rootCauseCandidates = structuredDiagnosis?.root_causes?.length
    ? structuredDiagnosis.root_causes.map((item) => ({
        title: item.name,
        confidence: item.confidence,
        evidence: item.evidence,
      }))
    : buildRootCauseCandidates(reasonSection, conclusionSection, citedRefs, confidenceScore);
  const evidenceCount = structuredDiagnosis?.evidence_count ?? citedRefs.length;
  const evidenceSimilarity = getEvidenceSimilarity(citedRefs, confidenceScore, structuredDiagnosis?.top_similarity);
  const rawBackendNextSteps = structuredDiagnosis?.next_steps ?? [];
  const backendStructuredNextSteps = rawBackendNextSteps.filter(isStructuredDiagnosisStep);
  const backendLegacyNextSteps = rawBackendNextSteps.filter((item): item is string => typeof item === "string");
  const hasStructuredBackendSteps = backendStructuredNextSteps.length > 0;
  const recommendedSteps = hasStructuredBackendSteps
    ? backendStructuredNextSteps
        .map((item) => tidyChineseProcedureText(item.raw_text || item.title || item.summary || ""))
        .filter(Boolean)
    : dedupeProcedureSteps(backendLegacyNextSteps.length > 0 ? backendLegacyNextSteps : llmActionItems);
  const structuredProcedureSteps = isProceduralAnswer
    ? sortStructuredProcedureSteps(
        hasStructuredBackendSteps
          ? backendStructuredNextSteps.map((item, index) => normalizeStructuredProcedureStep(item, index))
          : recommendedSteps.map((item, index) => parseStructuredProcedureStep(item, index)),
      )
    : [];
  const displayedRecommendedSteps = isProceduralAnswer
    ? structuredProcedureSteps.map((item) => `${item.stepNo ? `${item.stepNo}. ` : ""}${item.title}${item.summary ? ` ${item.summary}` : ""}`.trim())
    : hasStructuredBackendSteps
      ? backendStructuredNextSteps.map((item) => tidyChineseProcedureText(item.raw_text || item.title || item.summary || "")).filter(Boolean)
      : recommendedSteps;
  const mostLikelyFault = deriveReadableLikelyFault(
    structuredDiagnosis?.most_likely_fault,
    rootCauseCandidates,
    reasonSection,
    headline,
  );
  const diagnosisMatchCandidates = useMemo(
    () =>
      buildDiagnosisMatchCandidates(
        Boolean(isProceduralAnswer),
        structuredProcedureSteps,
        backendStructuredNextSteps,
        displayedRecommendedSteps,
      ),
    [
      isProceduralAnswer,
      structuredProcedureSteps,
      backendStructuredNextSteps,
      displayedRecommendedSteps,
    ],
  );
  const diagnosisRowStandardTitles = useMemo(
    () => computeDiagnosisToStandardStepTitles(task?.steps, diagnosisMatchCandidates),
    [task?.steps, diagnosisMatchCandidates],
  );
  const structuredEvidenceItems = structuredDiagnosis?.evidence_items ?? [];
  const createdAtText = formatDateTimeLocal(task?.created_at);
  const updatedAtText = formatDateTimeLocal(task?.updated_at);
  const visibleTimelineEvents = useMemo(
    () => events.filter((event) => !isPlanningLabel(event.title) && !isPlanningLabel(event.description)),
    [events],
  );
  const visibleTaskSteps = useMemo(
    () =>
      (task?.steps || []).filter(
        (step) =>
          !isPlanningLabel(step.title) &&
          !isPlanningLabel(step.instruction) &&
          !hasPlanningRuntimeEvents(
            Array.isArray(step.runtime_events)
              ? step.runtime_events.map((event) =>
                  event && typeof event === "object"
                    ? {
                        title: "title" in event ? String(event.title || "") : "",
                        description: "description" in event ? String(event.description || "") : "",
                      }
                    : { title: "", description: "" },
                )
              : [],
          ),
      ),
    [task?.steps],
  );
  const visibleCompletedSteps = useMemo(
    () => visibleTaskSteps.filter((step) => step.status === "completed").length,
    [visibleTaskSteps],
  );
  const keyEvidenceItems = sourceRefPreview.length > 0
    ? sourceRefPreview.map((ref, index) => ({
        id: `${ref.document_id ?? "doc"}-${ref.chunk_id ?? index}`,
        title: ref.title || `知识条目 ${index + 1}`,
        section: getKnowledgeSectionLabel(ref),
        excerpt: ref.excerpt?.trim() || "当前引用仅返回来源信息，暂无可展示摘录。",
        score: formatEvidenceScore(ref, Math.max(40, confidenceScore - index * 8)),
      }))
    : structuredEvidenceItems.map((item, index) => ({
        id: `structured-evidence-${index}`,
        title: item.document_title,
        section: item.section || "命中片段",
        excerpt: item.excerpt || "当前引用仅返回来源信息，暂无可展示摘录。",
        score: {
          label: item.relevance_score ? "重排相关度" : "参考相关度",
          value: item.relevance_score ? `${item.relevance_score}%` : `${Math.max(40, confidenceScore - index * 8)}%`,
        },
      }));
  const workspaceTabs: Array<{
    key: DiagnosisWorkspaceTab;
    label: string;
    helper: string;
    badge?: string;
    icon: typeof FileCode;
  }> = [
    {
      key: "fault",
      label: isProceduralAnswer ? "操作主题" : "最可能故障",
      helper: isProceduralAnswer ? "当前查询的操作对象" : "当前优先排查对象",
      icon: FileCode,
    },
    {
      key: "actions",
      label: isProceduralAnswer ? "操作步骤" : "建议动作",
      helper: isProceduralAnswer ? "按手册证据整理的步骤" : "建议先执行的动作",
      badge: `${displayedRecommendedSteps.length}`,
      icon: Wrench,
    },
    {
      key: "evidence",
      label: "关键证据来源",
      helper: "当前诊断引用的核心证据",
      badge: `${keyEvidenceItems.length}`,
      icon: Server,
    },
    {
      key: "timeline",
      label: "诊断时间线",
      helper: "系统进展摘要与阶段记录",
      badge: `${visibleTimelineEvents.length}`,
      icon: Clock,
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="app-main space-y-6 pb-10">
        <section className="app-page-head">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-3">
                  <Link
                    href={backHref}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </Link>
                  <span className="app-chip-muted">任务 #{taskId}</span>
                  <StatusBadge status={displayStatus} />
                </div>
                <div className="mt-4 space-y-1.5">
                  <h1 className="text-2xl font-semibold text-foreground">{deviceLabel}</h1>
                  <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{headline}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="app-btn-secondary px-3 py-1.5"
                  onClick={() => {
                    void (async () => {
                      try {
                        await navigator.clipboard.writeText(window.location.href);
                        await fetchHealth();
                        toast.success("复制链接成功");
                      } catch {
                        toast.error("复制链接失败，请检查浏览器权限");
                      }
                    })();
                  }}
                >
                  <Share2 className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  className="app-btn-secondary px-3 py-1.5 disabled:opacity-40"
                  disabled={status !== "completed"}
                  onClick={exportReport}
                >
                  <Download className="h-4 w-4" />
                </button>
                <button className="app-btn-primary px-3 py-1.5" onClick={retry} disabled={status === "running"}>
                  <RefreshCw className={`h-4 w-4 ${status === "running" ? "animate-spin" : ""}`} />
                  重新运行
                </button>
                <button
                  type="button"
                  className="app-btn-secondary px-3 py-1.5 disabled:opacity-40"
                  disabled={status !== "completed"}
                  onClick={() => setCreateWorkOrderOpen(true)}
                >
                  生成工单
                </button>
              </div>
            </div>

            <div className={`rounded-xl border p-4 ${statusSummaryMeta.panelClass}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-foreground">{statusSummaryMeta.label}</div>
                  <p className="mt-1 text-sm text-muted-foreground">{statusSummaryMeta.summary}</p>
                  <div className="mt-4">
                    <div className="rounded-lg border border-emerald-500/15 bg-background/45 p-3">
                      <div className="text-xs text-muted-foreground">{isProceduralAnswer ? "操作主题" : "最可能故障"}</div>
                      <div className="mt-1 text-sm font-medium leading-6 text-foreground">{mostLikelyFault}</div>
                    </div>
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2 lg:max-w-[520px]">
                  <OverviewItem label="创建时间" value={createdAtText} icon={Clock} />
                  <OverviewItem label="更新时间" value={updatedAtText} icon={Clock} />
                  <OverviewItem label="命中证据数" value={`${evidenceCount} 条`} icon={Server} />
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="space-y-4">
            <section className="app-card p-5">
              <div className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-foreground">
                <FileText className="h-4 w-4 text-muted-foreground" />
                任务概览
              </div>
              <div className="grid gap-3">
                <div className="rounded-lg border border-border bg-muted/35 p-3">
                  <div className="mb-1 text-xs text-muted-foreground">任务摘要</div>
                  <div className="text-sm leading-6 text-foreground">{headline}</div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                  <OverviewItem
                    label="任务进度"
                    value={`已完成 ${visibleCompletedSteps}/${visibleTaskSteps.length} 步`}
                    icon={Cpu}
                  />
                  <OverviewItem label="诊断耗时" value={duration} icon={Clock} />
                </div>
              </div>
            </section>
          </aside>

          <section className="space-y-4">
            <div id="task-handle-panel" className="app-card p-5">
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-4 border-b border-border pb-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="inline-flex items-center gap-2 text-base font-semibold text-foreground">
                          <FileCode className="h-4 w-4 text-muted-foreground" />
                          诊断工作区
                        </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {isProceduralAnswer
                          ? "在同一张卡片内切换查看操作主题、操作步骤、关键证据来源和诊断时间线。"
                          : "在同一张卡片内切换查看最可能故障、建议动作、关键证据来源和诊断时间线。"}
                      </p>
                    </div>
                    <span className="app-chip-muted">
                      {status === "running" ? "实时同步中" : status === "completed" ? "已完成回写" : "待重新运行"}
                    </span>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    {workspaceTabs.map((tab) => {
                      const Icon = tab.icon;
                      const active = activeWorkspaceTab === tab.key;
                      return (
                        <button
                          key={tab.key}
                          type="button"
                          onClick={() => setActiveWorkspaceTab(tab.key)}
                          className={`flex min-h-[84px] flex-col items-start justify-between rounded-xl border px-4 py-3 text-left transition-colors ${
                            active
                              ? "border-emerald-500/25 bg-emerald-500/8 shadow-sm"
                              : "border-border bg-background/70 hover:bg-muted/35"
                          }`}
                        >
                          <div className="flex w-full items-center justify-between gap-3">
                            <div className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card">
                              <Icon className={`h-4 w-4 ${active ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`} />
                            </div>
                            {tab.badge ? <span className="app-chip-muted">{tab.badge}</span> : null}
                          </div>
                          <div className="mt-3">
                            <div className="text-sm font-medium text-foreground">{tab.label}</div>
                            <div className="mt-1 text-xs leading-5 text-muted-foreground">{tab.helper}</div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {activeWorkspaceTab === "fault" ? (
                  <div>
                    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="inline-flex items-center gap-2 text-base font-semibold text-foreground">
                          <FileCode className="h-4 w-4 text-muted-foreground" />
                          {isProceduralAnswer ? "操作主题" : "最可能故障"}
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {isProceduralAnswer ? "这里展示当前问题对应的操作对象与整理说明。" : "这里只展示当前最优先排查的故障项或对象。"}
                        </p>
                      </div>
                    </div>

                    <div className={`rounded-xl border p-5 ${statusSummaryMeta.panelClass}`}>
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-card">
                          {status === "running" ? (
                            <Loader2 className="h-5 w-5 animate-spin text-blue-600 dark:text-blue-400" />
                          ) : status === "completed" ? (
                            <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                          ) : (
                            <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="rounded-lg border border-border/70 bg-background/50 p-4">
                            <div className="text-xs font-medium text-muted-foreground">{isProceduralAnswer ? "操作主题" : "最可能故障"}</div>
                            <div className="mt-2 text-base font-semibold leading-7 text-foreground">{mostLikelyFault}</div>
                            <div className="mt-3 text-sm leading-7 text-muted-foreground">{conclusionText}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {activeWorkspaceTab === "actions" ? (
                  <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/6 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <div className="text-sm font-semibold text-foreground">{isProceduralAnswer ? "操作步骤" : "建议动作"}</div>
                      <span className="text-xs text-muted-foreground">
                        {isProceduralAnswer
                          ? `按证据整理的推荐顺序，共 ${displayedRecommendedSteps.length} 步`
                          : `建议先执行的动作，共 ${displayedRecommendedSteps.length} 条`}
                      </span>
                    </div>
                    <div className="space-y-2">
                      {displayedRecommendedSteps.length > 0 ? (
                        isProceduralAnswer ? structuredProcedureSteps.map((item, index) => (
                          <div
                            key={item.key}
                            className="rounded-lg border border-emerald-500/10 bg-background/55 px-4 py-4"
                          >
                            <div className="flex items-start gap-3">
                              <div className="flex h-7 min-w-7 items-center justify-center rounded-full bg-emerald-500/12 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
                                {item.stepNo ?? index + 1}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="text-sm font-semibold leading-6 text-foreground">{item.title}</div>
                                {item.summary ? (
                                  <div className="mt-1 text-sm leading-6 text-muted-foreground">{item.summary}</div>
                                ) : null}
                                {item.sections.length > 0 ? (
                                  <div className="mt-3 space-y-3">
                                    {item.sections.map((section, sectionIndex) => (
                                      <div key={`${item.key}-section-${sectionIndex}-${section.label || "section"}`}>
                                        <div className="text-xs font-medium text-muted-foreground">{section.label}：</div>
                                        <ul className="mt-2 space-y-1.5 pl-5 text-sm leading-6 text-foreground/90">
                                          {section.items.map((sectionItem, sectionItemIndex) => (
                                            <li
                                              key={`${item.key}-section-${sectionIndex}-item-${sectionItemIndex}-${sectionItem || "item"}`}
                                              className="list-disc"
                                            >
                                              {sectionItem}
                                            </li>
                                          ))}
                                        </ul>
                                      </div>
                                    ))}
                                  </div>
                                ) : null}
                                {item.meta.length > 0 ? (
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    {item.meta.map((metaItem, metaIndex) => (
                                      <span
                                        key={`${item.key}-meta-${metaIndex}-${metaItem || "meta"}`}
                                        className="rounded-md border border-border bg-muted/35 px-2.5 py-1 text-xs text-foreground/85"
                                      >
                                        {metaItem}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                                {diagnosisRowStandardTitles[index] ? (
                                  <div className="mt-3 border-t border-emerald-500/15 pt-3 text-xs leading-5 text-muted-foreground">
                                    <span className="font-medium text-foreground/90">关联标准作业步骤：</span>
                                    {diagnosisRowStandardTitles[index]}
                                  </div>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        )) : displayedRecommendedSteps.map((item, index) => (
                          <div key={`${item}-${index}`} className="flex flex-col gap-2 rounded-lg border border-emerald-500/10 bg-background/45 px-3 py-3 text-sm text-foreground">
                            <div className="flex items-start gap-2">
                              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                              <span className="leading-6">{item}</span>
                            </div>
                            {diagnosisRowStandardTitles[index] ? (
                              <div className="border-t border-emerald-500/15 pt-2 text-xs leading-5 text-muted-foreground">
                                <span className="font-medium text-foreground/90">关联标准作业步骤：</span>
                                {diagnosisRowStandardTitles[index]}
                              </div>
                            ) : null}
                          </div>
                        ))
                      ) : (
                        <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-8 text-sm text-muted-foreground">
                          {isProceduralAnswer ? "当前尚未整理出可执行的操作步骤。" : "当前尚未生成可执行的建议动作。"}
                        </div>
                      )}
                    </div>
                  </div>
                ) : null}

                {activeWorkspaceTab === "evidence" ? (
                  <div className="rounded-xl border border-border bg-background/70 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <div className="text-sm font-semibold text-foreground">关键证据来源</div>
                      <span className="text-xs text-muted-foreground">当前诊断引用的核心证据</span>
                    </div>
                    <div className="space-y-3">
                      {keyEvidenceItems.length > 0 ? keyEvidenceItems.map((item) => (
                        <div key={item.id} className="rounded-lg border border-border bg-muted/30 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-foreground">{item.title}</div>
                              <div className="mt-1 text-xs text-muted-foreground">{item.section}</div>
                              <div className="mt-2 text-sm leading-6 text-foreground/90">{item.excerpt}</div>
                            </div>
                            <span className="app-chip-muted">{item.score.label} {item.score.value}</span>
                          </div>
                        </div>
                      )) : (
                        <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-8 text-sm text-muted-foreground">
                          当前任务尚未返回可展示的关键证据来源。
                        </div>
                      )}
                    </div>
                    <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs text-muted-foreground">
                      <span>命中证据数 {evidenceCount} 条</span>
                      <span>最高相关度 {evidenceSimilarity}</span>
                    </div>
                  </div>
                ) : null}

                {activeWorkspaceTab === "timeline" ? (
                  <div className="rounded-xl border border-border bg-background/70 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <div className="text-sm font-semibold text-foreground">诊断时间线</div>
                      <span className="text-xs text-muted-foreground">系统进展摘要与阶段记录</span>
                    </div>
                    {visibleTimelineEvents.length > 0 ? (
                      <div className="space-y-3 rounded-2xl border border-border bg-muted/15 p-4 sm:p-5">
                        {visibleTimelineEvents.map((event, index) => (
                          <div
                            key={event.id || `${event.type}-${index}`}
                            className="flex items-start gap-3"
                          >
                            <div className={`mt-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-sm font-semibold shadow-sm ${getTimelineEventVisual(event.type).badgeClass}`}>
                              {index + 1}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="mb-1 flex items-center gap-2 pl-1">
                                <span className="text-xs font-medium text-foreground">诊断引擎</span>
                                <span className="text-[11px] text-muted-foreground">{formatDateTimeLocal(event.time)}</span>
                              </div>
                              <div className={`relative rounded-2xl border px-4 py-3 shadow-sm ${getTimelineEventVisual(event.type).bubbleClass}`}>
                                <div className="absolute left-[-7px] top-4 h-3.5 w-3.5 rotate-45 border-b border-l border-inherit bg-inherit" />
                                <div className="text-sm font-semibold leading-6 text-foreground">{event.title || "阶段更新"}</div>
                                <div className="mt-1 text-sm leading-7 text-muted-foreground">
                                  {event.description || "系统已记录该阶段执行情况。"}
                                </div>
                                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                  <span className="app-chip-muted">阶段 {index + 1}</span>
                                  <span className="rounded-full border border-border bg-background/80 px-2 py-0.5">
                                    {event.type}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-8 text-sm text-muted-foreground">
                        当前暂无可展示的诊断时间线。
                      </div>
                    )}
                  </div>
                ) : null}

              </div>
            </div>
          </section>
        </div>
      </main>

      <Dialog open={createWorkOrderOpen} onOpenChange={setCreateWorkOrderOpen}>
        <DialogContent className="max-w-md border-border bg-popover text-popover-foreground">
          <DialogHeader>
            <DialogTitle>基于诊断生成工单</DialogTitle>
            <DialogDescription>
              检修工单需在智能诊断完成后生成，系统会按当前任务的设备编号与检修等级建立工单。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="rounded-lg border border-border bg-muted/25 p-3 text-sm">
              <div className="text-xs text-muted-foreground">当前任务</div>
              <div className="mt-1 font-medium text-foreground">{headline}</div>
              <div className="mt-2 text-xs text-muted-foreground">
                设备编号：{task?.asset_code || "未提供"} · 检修等级：{task?.maintenance_level || "standard"}
              </div>
            </div>
            <div
              className={`min-h-[100px] rounded-lg px-4 py-4 text-sm transition-colors ${
                matchedDevice
                  ? "border border-border bg-muted/25"
                  : workOrderError
                    ? "border border-dashed border-red-300/60 bg-red-50/70 text-red-500"
                    : "border border-dashed border-border bg-muted/20 text-muted-foreground"
              }`}
            >
              {matchedDevice ? (
                <>
                  <div className="text-xs text-muted-foreground">已匹配检修设备</div>
                  <div className="mt-1 font-medium text-foreground">
                    #{matchedDevice.id} · {matchedDevice.asset_code || "无编号"} · {matchedDevice.device_type}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    型号：{matchedDevice.model || "未提供"}{matchedDevice.location ? ` · 位置：${matchedDevice.location}` : ""}
                  </div>
                </>
              ) : workOrderError ? (
                <div className="flex min-h-[68px] items-center">
                  检修设备匹配失败，请先确认检修后端可用且当前登录状态有效。
                </div>
              ) : (
                <div className="flex min-h-[68px] items-center">正在匹配检修设备...</div>
              )}
            </div>
            <div className="min-h-[20px] text-sm text-red-400">
              {workOrderError || ""}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" className="border-border" onClick={() => setCreateWorkOrderOpen(false)}>
              取消
            </Button>
            <Button
              type="button"
              className="bg-[#5e6ad2] text-white hover:bg-[#6b77db]"
              disabled={workOrderSubmitting || matchingDevice || !matchedDevice}
              onClick={createLinkedWorkOrder}
            >
              {workOrderSubmitting ? "生成中…" : "确认生成工单"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
