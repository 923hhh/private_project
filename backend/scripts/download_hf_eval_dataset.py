"""从 Hugging Face 下载数据并转换为本项目评测格式。

默认来源：Jaya1995/Maintenance
输出：
  - backend/evaluation/hf_maintenance_eval_seed.json
  - backend/evaluation/hf_maintenance_eval_cases.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="下载 Hugging Face 数据并生成评测集")
    parser.add_argument("--dataset", default="Jaya1995/Maintenance", help="Hugging Face 数据集名称")
    parser.add_argument("--split", default="train", help="数据集 split，默认 train")
    parser.add_argument("--limit", type=int, default=50, help="生成评测题目数量，默认 50")
    parser.add_argument(
        "--out-seed",
        default="../backend/evaluation/hf_maintenance_eval_seed.json",
        help="输出 seed 文件路径",
    )
    parser.add_argument(
        "--out-cases",
        default="../backend/evaluation/hf_maintenance_eval_cases.json",
        help="输出 cases 文件路径",
    )
    parser.add_argument("--equipment-type", default="通用设备", help="评测样本设备类型")
    parser.add_argument("--equipment-model", default="HF-STD", help="评测样本设备型号")
    return parser


def extract_terms(text: str, max_terms: int = 3) -> list[str]:
    tokens = re.findall(r"[A-Za-z]{4,}|[\u4e00-\u9fff]{2,}", text)
    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        low = token.lower()
        if low in seen:
            continue
        seen.add(low)
        deduped.append(token)
        if len(deduped) >= max_terms:
            break
    return deduped or ["维护", "检查"]


def main() -> None:
    args = build_parser().parse_args()
    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("请先安装 datasets：pip install datasets pyarrow") from exc

    dataset = load_dataset(args.dataset, split=args.split)
    rows = dataset.select(range(min(args.limit, len(dataset))))

    seed_docs: list[dict] = []
    cases: list[dict] = []
    for idx, item in enumerate(rows, start=1):
        raw = str(item.get("sentence") or item.get("text") or "").strip()
        if not raw:
            continue
        title = f"HF维护知识条目 {idx:03d}"
        source_name = f"{args.dataset}#{args.split}-{idx:03d}"
        terms = extract_terms(raw)

        seed_docs.append(
            {
                "title": title,
                "source_name": source_name,
                "source_type": "manual",
                "equipment_type": args.equipment_type,
                "equipment_model": args.equipment_model,
                "fault_type": "维护作业",
                "section_reference": f"HF-{idx:03d}",
                "page_reference": "N/A",
                "content": raw,
            }
        )
        cases.append(
            {
                "id": f"HF-{idx:03d}",
                "category": "success",
                "query": f"设备维护问题：{raw}。请给出处理建议。",
                "equipment_type": args.equipment_type,
                "equipment_model": args.equipment_model,
                "fault_type": "维护作业",
                "expected_titles": [title],
                "expected_terms": terms,
                "workflow_expected": False,
                "feedback_expected": False,
                "case_title": f"{title} 评测案例",
                "processing_steps": ["读取维护建议。", "执行基础检查。"],
                "resolution_summary": "按维护建议执行。"
            }
        )

    out_seed = Path(args.out_seed).resolve()
    out_cases = Path(args.out_cases).resolve()
    out_seed.parent.mkdir(parents=True, exist_ok=True)
    out_cases.parent.mkdir(parents=True, exist_ok=True)

    out_seed.write_text(json.dumps(seed_docs, ensure_ascii=False, indent=2), encoding="utf-8")
    out_cases.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"已生成 seed: {out_seed} ({len(seed_docs)} 条)")
    print(f"已生成 cases: {out_cases} ({len(cases)} 条)")


if __name__ == "__main__":
    main()
