"""检查软件杯评测结果是否满足功能3/4门禁阈值。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATE_CONFIG = ROOT / "evaluation" / "softbei_quality_gate.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_number(data: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    if isinstance(current, (int, float)):
        return float(current)
    return default


def _check_minimum(
    *,
    actual: float,
    expected: float,
    label: str,
    failed: list[str],
    passed: list[str],
) -> None:
    if actual + 1e-8 < expected:
        failed.append(f"{label}: {actual:.2f} < {expected:.2f}")
    else:
        passed.append(f"{label}: {actual:.2f} >= {expected:.2f}")


def run_gate(gate_path: Path, result_path: Path | None) -> int:
    gate_cfg = _load_json(gate_path)
    result_file_cfg = str(gate_cfg.get("result_file") or "evaluation/softbei_eval_results.json")
    eval_path = (ROOT / result_file_cfg).resolve() if result_path is None else result_path.resolve()
    eval_payload = _load_json(eval_path)
    current = ((eval_payload.get("metrics") or {}).get("current_system") or {})
    thresholds = gate_cfg.get("thresholds") or {}
    guards = gate_cfg.get("guards") or {}

    workflow_total = _read_number(current, "workflow", "total")
    feedback_total = _read_number(current, "feedback", "total")
    agent_total = _read_number(current, "agent", "total")
    authorization_total = _read_number(current, "agent", "authorization_total")

    workflow_completion_rate = _read_number(current, "workflow", "completion_rate")
    feedback_recall_rate = _read_number(current, "feedback", "recall_rate")
    agent_success_rate = _read_number(current, "agent", "success_rate")
    authorization_hit_rate = _read_number(current, "agent", "authorization_hit_rate")

    failed: list[str] = []
    passed: list[str] = []

    _check_minimum(
        actual=workflow_total,
        expected=float(guards.get("workflow_total_min", 0.0)),
        label="workflow.total",
        failed=failed,
        passed=passed,
    )
    _check_minimum(
        actual=feedback_total,
        expected=float(guards.get("feedback_total_min", 0.0)),
        label="feedback.total",
        failed=failed,
        passed=passed,
    )
    _check_minimum(
        actual=agent_total,
        expected=float(guards.get("agent_total_min", 0.0)),
        label="agent.total",
        failed=failed,
        passed=passed,
    )
    _check_minimum(
        actual=authorization_total,
        expected=float(guards.get("authorization_total_min", 0.0)),
        label="agent.authorization_total",
        failed=failed,
        passed=passed,
    )

    _check_minimum(
        actual=workflow_completion_rate,
        expected=float(thresholds.get("workflow_completion_rate_min", 0.0)),
        label="workflow.completion_rate(%)",
        failed=failed,
        passed=passed,
    )
    _check_minimum(
        actual=feedback_recall_rate,
        expected=float(thresholds.get("feedback_recall_rate_min", 0.0)),
        label="feedback.recall_rate(%)",
        failed=failed,
        passed=passed,
    )
    _check_minimum(
        actual=agent_success_rate,
        expected=float(thresholds.get("agent_success_rate_min", 0.0)),
        label="agent.success_rate(%)",
        failed=failed,
        passed=passed,
    )
    _check_minimum(
        actual=authorization_hit_rate,
        expected=float(thresholds.get("authorization_hit_rate_min", 0.0)),
        label="agent.authorization_hit_rate(%)",
        failed=failed,
        passed=passed,
    )

    print(f"[softbei-gate] 评测文件: {eval_path}")
    print(f"[softbei-gate] 门禁配置: {gate_path.resolve()}")
    for line in passed:
        print(f"[PASS] {line}")
    if failed:
        for line in failed:
            print(f"[FAIL] {line}")
        print(f"[softbei-gate] 门禁失败，共 {len(failed)} 项不达标。")
        return 1

    print("[softbei-gate] 门禁通过，功能3/4自动化评测达标。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查软件杯评测结果门禁")
    parser.add_argument(
        "--gate-config",
        default=str(DEFAULT_GATE_CONFIG),
        help="门禁配置 JSON 路径（默认 backend/evaluation/softbei_quality_gate.json）",
    )
    parser.add_argument(
        "--result-file",
        default=None,
        help="评测结果 JSON 路径（默认读取 gate-config 中 result_file）",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    gate_path = Path(args.gate_config)
    result_path = Path(args.result_file) if args.result_file else None
    code = run_gate(gate_path, result_path)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
