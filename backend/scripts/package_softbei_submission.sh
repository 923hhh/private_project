#!/usr/bin/env bash
# 生成公开交付用「源码包」ZIP：基于当前 HEAD 的 git 树。
# 用法：bash backend/scripts/package_softbei_submission.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
mkdir -p dist
STAMP="$(date +%Y%m%d-%H%M)"
OUT="dist/dachuang_project-SB8-src-${STAMP}.zip"
git archive --format=zip -o "$OUT" HEAD
echo "已写入: $OUT"
echo "请将 PPT、演示视频、截图/录屏等二进制产物单独归档到本地或私有归档位置，勿提交进公开 Git 仓库。"
