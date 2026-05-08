"""Phase 32: 离线评测体系与 RAGAS 数据集生成验证."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.evaluation.offline_eval import build_eval_dataset, flatten_dataset_rows, load_json


_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _sample_cases() -> list[dict[str, object]]:
    return [
        {
            "id": "CASE-TEXT-1",
            "query": "发动机启动困难时应该先检查什么？",
            "category": "success",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "启动困难",
            "expected_titles": ["启动系统检查"],
            "expected_terms": ["火花塞", "点火线路"],
            "resolution_summary": "优先检查点火系统与供油状态。",
            "processing_steps": [],
        },
        {
            "id": "CASE-IMAGE-1",
            "query": "根据图片判断发动机外观渗漏点",
            "category": "success",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "机油渗漏",
            "expected_titles": ["外观渗漏排查"],
            "expected_terms": ["渗漏", "密封垫"],
            "resolution_summary": "结合外观渗漏位置检查密封件老化。",
            "processing_steps": [],
        },
        {
            "id": "CASE-PROC-1",
            "query": "拆卸发动机步骤",
            "category": "success",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "拆卸流程",
            "expected_titles": ["发动机拆卸流程"],
            "expected_terms": ["拆卸", "顺序", "固定螺栓"],
            "resolution_summary": "按标准顺序拆卸并做好部件标记。",
            "processing_steps": ["断开电源并放净机油", "拆除外部附件与连接件", "按顺序松开固定螺栓并吊离总成"],
        },
    ]


def _sample_seed_docs() -> list[dict[str, object]]:
    return [
        {
            "title": "启动系统检查",
            "source_name": "startup_manual.md",
            "source_type": "manual",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "启动困难",
            "section_reference": "第2章 启动系统",
            "page_reference": "P12",
            "content": "启动困难时先检查火花塞间隙、点火线路连接状态和供油是否正常，必要时清洁或更换火花塞。",
        },
        {
            "title": "外观渗漏排查",
            "source_name": "leak_manual.md",
            "source_type": "manual",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "机油渗漏",
            "section_reference": "第5章 外观检查",
            "page_reference": "P33",
            "content": "观察图片中的渗漏轨迹，重点检查缸体结合面、密封垫和放油螺栓周边是否存在油污扩散。",
        },
        {
            "title": "发动机拆卸流程",
            "source_name": "disassembly_manual.md",
            "source_type": "procedure",
            "equipment_type": "摩托车发动机",
            "equipment_model": "LX200",
            "fault_type": "拆卸流程",
            "section_reference": "第7章 发动机拆装",
            "page_reference": "P58",
            "content": "发动机拆卸步骤：1. 断开电源并放净机油。2. 拆除外部附件与连接件。3. 按顺序松开固定螺栓并吊离总成。",
        },
    ]


def test_build_eval_dataset_covers_three_sample_types():
    """正式离线数据集应稳定覆盖 text/image/procedural 三类样本。"""
    cases = _sample_cases()
    seed_docs = _sample_seed_docs()

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
    cases = _sample_cases()
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    seed_docs_path = tmp_path / "seed_docs.json"
    seed_docs_path.write_text(json.dumps(_sample_seed_docs(), ensure_ascii=False), encoding="utf-8")

    config = {
        "version": "test",
        "seed_documents_path": str(seed_docs_path).replace("\\", "/"),
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
    cases = _sample_cases()
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    seed_docs_path = tmp_path / "seed_docs.json"
    seed_docs_path.write_text(json.dumps(_sample_seed_docs(), ensure_ascii=False), encoding="utf-8")

    config = {
        "version": "test",
        "seed_documents_path": str(seed_docs_path).replace("\\", "/"),
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
