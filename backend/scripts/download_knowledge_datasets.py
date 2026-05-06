#!/usr/bin/env python3
"""从 Hugging Face 下载与「设备维护 / 机泵检修」相关的公开语料，写入仓库 datasets/knowledge/。

用法（在 backend 目录下，已安装依赖）::

    python scripts/download_knowledge_datasets.py

可选：国内网络可设置镜像后再运行::

    set HF_ENDPOINT=https://hf-mirror.com
    python scripts/download_knowledge_datasets.py

许可与引用请以各数据集在 Hugging Face 上的卡片为准；本脚本仅做格式转换与落盘。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_content_min_length(text: str, min_len: int = 20) -> str:
    stripped = (text or "").strip()
    if len(stripped) >= min_len:
        return stripped
    return f"设备维护操作建议：{stripped}"


def download_jaya_maintenance(out_dir: Path) -> Path:
    try:
        from datasets import load_dataset
    except ImportError as e:
        print("请先安装：pip install datasets pyarrow", file=sys.stderr)
        raise SystemExit(1) from e

    ds = load_dataset("Jaya1995/Maintenance")
    rows = ds["train"]
    out_path = out_dir / "hf_jaya1995_maintenance.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    for i, item in enumerate(rows):
        sentence = item.get("sentence") or item.get("text") or ""
        content = _ensure_content_min_length(str(sentence))
        records.append(
            {
                "title": f"通用维护规程条目 {i + 1:03d}",
                "source_name": f"Jaya1995/Maintenance#train-{i}",
                "source_type": "procedure",
                "equipment_type": "机泵类设备",
                "equipment_model": None,
                "fault_type": None,
                "content": content,
            }
        )

    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="下载知识库配套公开数据集到 datasets/knowledge/")
    parser.add_argument(
        "--out-subdir",
        default="text",
        help="相对于 datasets/knowledge/ 的输出子目录（默认 text）",
    )
    args = parser.parse_args()

    root = _repo_root()
    out_dir = root / "datasets" / "knowledge" / args.out_subdir
    path = download_jaya_maintenance(out_dir)
    print(f"已写入 {path} ，共 {sum(1 for _ in path.open(encoding='utf-8'))} 条记录。")


if __name__ == "__main__":
    main()
