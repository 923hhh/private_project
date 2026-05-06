"""Phase 32: 离线评测体系与 RAGAS 数据集生成验证."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.evaluation.offline_eval import build_eval_dataset, flatten_dataset_rows, load_json


_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_build_eval_dataset_covers_three_sample_types():
    """正式离线数据集应稳定覆盖 text/image/procedural 三类样本。"""
    cases = load_json(_BACKEND_ROOT / "evaluation" / "softbei_eval_cases.json")
    seed_docs = load_json(_BACKEND_ROOT / "evaluation" / "softbei_knowledge_seed.json")

    rows = build_eval_dataset(cases, seed_docs)

    sample_types = {row["metadata"]["sample_type"] for row in rows}
    assert {"text", "image", "procedural"}.issubset(sample_types)
    assert all(row["reference"] for row in rows)
    assert all("metadata" in row for row in rows)


def test_flatten_dataset_rows_is_csv_friendly():
    """CSV 展平视图应保留关键索引字段。"""
    rows = [
        {
            "user_input": "发动机启动困难",
            "reference": "检查火花塞。",
            "reference_contexts": ["ctx1"],
            "metadata": {
                "sample_type": "text",
                "case_id": "A-1",
                "category": "success",
                "equipment_type": "摩托车发动机",
                "equipment_model": "LX200",
                "fault_type": "启动困难",
                "expected_terms": ["火花塞"],
            },
        }
    ]
    flat = flatten_dataset_rows(rows)
    assert flat[0]["sample_type"] == "text"
    assert flat[0]["reference_context_count"] == 1
    assert "火花塞" in flat[0]["expected_terms"]


def test_generate_offline_eval_dataset_script(tmp_path: Path):
    """生成脚本应产出 JSONL/CSV/summary 三套文件。"""
    cases = load_json(_BACKEND_ROOT / "evaluation" / "softbei_eval_cases.json")[:3]
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")

    config = {
        "version": "test",
        "seed_documents_path": "backend/evaluation/softbei_knowledge_seed.json",
        "source_cases_path": str(cases_path).replace("\\", "/"),
        "output_dir": str(tmp_path).replace("\\", "/"),
        "dataset_prefix": "offline_eval_test",
        "ragas": {"enabled_by_default": False, "testset_size": 4},
        "runner": {"top_k": 5, "output_file": str(tmp_path / "report.json").replace("\\", "/")},
    }
    config_path = tmp_path / "offline_eval_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    script = _BACKEND_ROOT / "scripts" / "generate_offline_eval_dataset.py"
    result = subprocess.run(
        [sys.executable, str(script), "--config", str(config_path)],
        cwd=str(_BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    assert "jsonl" in result.stdout.lower()
    assert (tmp_path / "offline_eval_test_testset.jsonl").exists()
    assert (tmp_path / "offline_eval_test_testset.csv").exists()
    assert (tmp_path / "offline_eval_test_testset_summary.json").exists()


def test_run_offline_rag_eval_script(tmp_path: Path):
    """离线 runner 应能读取生成数据集并输出正式报告。"""
    cases = load_json(_BACKEND_ROOT / "evaluation" / "softbei_eval_cases.json")[:3]
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")

    config = {
        "version": "test",
        "seed_documents_path": "backend/evaluation/softbei_knowledge_seed.json",
        "source_cases_path": str(cases_path).replace("\\", "/"),
        "output_dir": str(tmp_path).replace("\\", "/"),
        "dataset_prefix": "offline_eval_test",
        "ragas": {"enabled_by_default": False, "testset_size": 4},
        "runner": {"top_k": 5, "output_file": str(tmp_path / "offline_report.json").replace("\\", "/")},
    }
    config_path = tmp_path / "offline_eval_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    gen_script = _BACKEND_ROOT / "scripts" / "generate_offline_eval_dataset.py"
    subprocess.run(
        [sys.executable, str(gen_script), "--config", str(config_path)],
        cwd=str(_BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    run_script = _BACKEND_ROOT / "scripts" / "run_offline_rag_eval.py"
    result = subprocess.run(
        [sys.executable, str(run_script), "--config", str(config_path)],
        cwd=str(_BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    assert "report" in result.stdout.lower()
    report_path = tmp_path / "offline_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["case_count"] >= 3
    assert "retrieval" in report["metrics"]
    assert "grounded" in report["metrics"]
