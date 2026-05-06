"""Phase 17: 软件杯效果证据与测试报告资产验证."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.evaluation.softbei_metrics import (
    build_quality_highlights,
    build_runtime_highlights,
    build_scorecard,
)


# tests/ 位于 backend/tests/，评测资产在 backend/evaluation/
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_softbei_eval_case_asset_count():
    """标准案例资产应保持在合理规模，并覆盖成功/模糊/失败场景。"""
    cases = json.loads(
        (_BACKEND_ROOT / "evaluation" / "softbei_eval_cases.json").read_text(encoding="utf-8")
    )

    assert 10 <= len(cases) <= 50
    categories = {item["category"] for item in cases}
    assert categories == {"success", "fuzzy", "failure"}


def test_build_scorecard_metrics():
    """评测汇总指标应正确计算比例和分类命中率。"""
    payload = build_scorecard(
        [
            {
                "case_id": "A",
                "category": "success",
                "retrieval_hit": True,
                "top1_hit": True,
                "top3_hit": True,
                "same_model_expected": True,
                "same_model_hit": True,
                "citation_ok": True,
                "anchor_trace_ok": True,
                "workflow_expected": True,
                "workflow_completed": True,
                "feedback_expected": False,
                "feedback_hit": False,
                "agent_expected": True,
                "agent_completed": True,
                "tooling_ok": True,
                "run_playback_ok": True,
                "authorization_expected": True,
                "authorization_ok": True,
            },
            {
                "case_id": "B",
                "category": "failure",
                "retrieval_hit": False,
                "top1_hit": False,
                "top3_hit": False,
                "same_model_expected": False,
                "same_model_hit": False,
                "citation_ok": False,
                "anchor_trace_ok": False,
                "workflow_expected": False,
                "workflow_completed": False,
                "feedback_expected": False,
                "feedback_hit": False,
                "agent_expected": False,
                "agent_completed": False,
                "tooling_ok": False,
                "run_playback_ok": False,
                "authorization_expected": None,
                "authorization_ok": None,
            },
            {
                "case_id": "C",
                "category": "success",
                "retrieval_hit": True,
                "top1_hit": False,
                "top3_hit": True,
                "same_model_expected": True,
                "same_model_hit": False,
                "citation_ok": False,
                "anchor_trace_ok": True,
                "workflow_expected": True,
                "workflow_completed": False,
                "feedback_expected": True,
                "feedback_hit": True,
                "agent_expected": True,
                "agent_completed": True,
                "tooling_ok": True,
                "run_playback_ok": False,
                "authorization_expected": False,
                "authorization_ok": True,
            },
        ]
    )

    assert payload["retrieval"]["hit_rate"] == 66.67
    assert payload["retrieval"]["top1_hit_rate"] == 33.33
    assert payload["retrieval"]["top3_hit_rate"] == 66.67
    assert payload["retrieval"]["same_model_hit_rate"] == 50.0
    assert payload["citation"]["coverage_rate"] == 50.0
    assert payload["citation"]["anchor_trace_rate"] == 100.0
    assert payload["workflow"]["completion_rate"] == 50.0
    assert payload["feedback"]["recall_rate"] == 100.0
    assert payload["agent"]["success_rate"] == 100.0
    assert payload["agent"]["playback_rate"] == 50.0
    assert payload["agent"]["authorization_hit_rate"] == 100.0
    assert payload["category_breakdown"]["success"]["hit_rate"] == 100.0


def test_workbench_highlight_builders():
    """工作台评测卡片和运行指标卡片应能从结果结构中生成稳定摘要。"""
    quality = build_quality_highlights(
        {
            "metrics": {
                "current_system": {
                    "retrieval": {"top1_hits": 8, "hits": 9, "top1_hit_rate": 80.0, "top3_hits": 9, "top3_hit_rate": 90.0, "total": 10},
                    "citation": {"anchor_hits": 9, "hits": 9, "anchor_trace_rate": 100.0, "total": 9},
                    "workflow": {"hits": 7, "total": 8, "completion_rate": 87.5},
                    "feedback": {"hits": 4, "total": 5, "recall_rate": 80.0},
                    "agent": {"hits": 8, "total": 8, "success_rate": 100.0, "playback_hits": 8},
                }
            }
        }
    )
    runtime = build_runtime_highlights(
        {
            "counters": [
                {"name": "knowledge_search_requests_total", "labels": {}, "value": 12},
                {"name": "agent_assist_requests_total", "labels": {}, "value": 5},
                {"name": "agent_runs_persisted_total", "labels": {"status": "completed"}, "value": 5},
                {"name": "knowledge_import_jobs_completed_total", "labels": {}, "value": 3},
                {"name": "knowledge_import_jobs_failed_total", "labels": {}, "value": 1},
                {"name": "agent_tool_calls_total", "labels": {}, "value": 20},
            ],
            "durations": [
                {"name": "knowledge_search_duration_ms", "count": 3, "total_ms": 300.0},
                {"name": "knowledge_import_processing_ms", "count": 2, "total_ms": 800.0},
                {"name": "agent_tool_call_duration_ms", "count": 4, "total_ms": 200.0},
            ],
        }
    )

    assert quality[0]["label"] == "Top1 命中率"
    assert quality[0]["value"] == "80.00%"
    assert runtime[0]["label"] == "知识检索请求"
    assert runtime[0]["value"] == "12"


def test_softbei_evaluation_script_generates_report():
    """评测脚本应在当前解释器环境下成功运行并生成固定结果文件。"""
    script = _BACKEND_ROOT / "scripts" / "run_softbei_eval.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(_BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    assert "评测结果已写入" in result.stdout

    payload = json.loads(
        (_BACKEND_ROOT / "evaluation" / "softbei_eval_results.json").read_text(encoding="utf-8")
    )
    retrieval = payload["metrics"]["current_system"]["retrieval"]
    assert retrieval["hits"] >= 8
    assert retrieval["total"] >= retrieval["hits"]
    assert "top1_hit_rate" in payload["metrics"]["current_system"]["retrieval"]
    assert "anchor_trace_rate" in payload["metrics"]["current_system"]["citation"]
    assert payload["metrics"]["current_system"]["workflow"]["completion_rate"] == 100.0
    assert payload["metrics"]["current_system"]["feedback"]["recall_rate"] == 100.0
    assert "agent" in payload["metrics"]["current_system"]
