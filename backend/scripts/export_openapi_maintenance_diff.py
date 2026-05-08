#!/usr/bin/env python3
"""导出 OpenAPI 中 `/api/v1/maintenance` 路径列表，写入 docs/OPENAPI与接口文档_差异摘要.md。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "OPENAPI与接口文档_差异摘要.md"
PREFIX = "/api/v1/maintenance"


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from app.main import app

    schema = app.openapi()
    paths = schema.get("paths") or {}
    ours = sorted(p for p in paths if p.startswith(PREFIX))
    lines = [
        "# OpenAPI 与《接口文档》差异摘要（检修域）",
        "",
        "本文件由 `scripts/export_openapi_maintenance_diff.py` 自动生成，**非**手工逐字段 diff。",
        "权威契约说明仍以 [接口文档.md](接口文档.md) 为准；此处列出当前 FastAPI 暴露的检修域路径，便于答辩前核对。",
        "",
        f"## 当前 OpenAPI 路径前缀 `{PREFIX}`（共 {len(ours)} 条）",
        "",
    ]
    for p in ours:
        methods = sorted(k.upper() for k in paths[p].keys() if k in ("get", "post", "put", "patch", "delete"))
        lines.append(f"- `{', '.join(methods)}` `{p}`")
    lines.extend(
        [
            "",
            "## 与文档对齐说明",
            "",
            "- 新增 **P1 占位**：`GET .../retrieval/stream`（SSE 占位）、`POST .../asr/transcribe`（501）。",
            "- 若《接口文档》未收录上述路径，请在下一版文档中补充或标注「P1」。",
            "",
        ]
    )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
