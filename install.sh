#!/usr/bin/env bash
# =============================================================================
# Agent OS 一键安装脚本（Grok #21）
#
# 把本仓库的 11 个 Core Skills + AGENTS.md 安装到用户的 OpenClaw 环境，
# 消除「cp -r + 手合 AGENTS.md」的摩擦。行为对齐 docs/INSTALL.md。
#
#   1. 检测 OpenClaw 版本（≥ 2026.7.1-2）
#   2. 定位用户 skills 目录（默认 ~/.openclaw/skills，可用 --skills-dir 覆盖）
#   3. 备份同名 Skill（若目标已存在同目录先备份为 skill.prepatch备份时间戳）
#   4. cp -r skills/* -> 目标 skills 目录（保持 _lib，不复制运行时 memory）
#   5. AGENTS.md：目标已有则【备份 + 打印合并指引】(不覆盖用户现有内容)；
#      目标无则以本仓库 AGENTS.md 为准【复制】
#   6. 重载 / 重启 OpenClaw gateway
#   7. openclaw skills list 验证 ≥ 11 ready
#
# 用法:
#   ./install.sh                      # 安装到默认 ~/.openclaw/skills
#   ./install.sh --skills-dir /path   # 指定 skills 目录
#   ./install.sh --no-reload          # 跳过 gateway restart
#   ./install.sh --no-verify          # 跳过 skills list 验证
# =============================================================================
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO/skills"
AGENTS_SRC="$REPO/AGENTS.md"
NOW="$(date +%Y%m%d-%H%M%S)"

MIN_VERSION="2026.7.1"

# ---- 参数解析 ----
SKILLS_DIR="${OPENCLAW_SKILLS_DIR:-${HOME}/.openclaw/skills}"
WORKSPACE_AGENTS="${OPENCLAW_WS_AGENTS:-${HOME}/.openclaw/AGENTS.md}"
DO_RELOAD=1
DO_VERIFY=1

while [ $# -gt 0 ]; do
  case "$1" in
    --skills-dir) SKILLS_DIR="$2"; shift 2 ;;
    --ws-agents)  WORKSPACE_AGENTS="$2"; shift 2 ;;
    --no-reload)  DO_RELOAD=0; shift ;;
    --no-verify)  DO_VERIFY=0; shift ;;
    -h|--help)    sed -n '1,30p' "$0"; exit 0 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done

echo "==> Agent OS 安装：源=$REPO  目标skills=$SKILLS_DIR"

# ---- 1. 检测 OpenClaw 版本 ----
if command -v openclaw >/dev/null 2>&1; then
  VER="$(openclaw --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  if [ -z "${VER:-}" ]; then
    echo "!! 无法解析 openclaw 版本；继续但请手工确认 ≥ $MIN_VERSION"
  elif [ "$(printf '%s\n' "$MIN_VERSION" "$VER" | sort -V | head -1)" = "$MIN_VERSION" ]; then
    echo "==> OpenClaw 版本 $VER ≥ $MIN_VERSION OK"
  else
    echo "!! OpenClaw 版本 $VER < $MIN_VERSION(建议)；可能不兼容，继续但请谨慎"
  fi
else
  echo "!! 未找到 openclaw 命令；跳过版本检测（请确保已装 OpenClaw ≥ $MIN_VERSION）"
fi

# ---- 2. 创建目标 skills 目录 ----
mkdir -p "$SKILLS_DIR" || { echo "!! 无法创建 $SKILLS_DIR"; exit 1; }
mkdir -p "$(dirname "$WORKSPACE_AGENTS")" 2>/dev/null || true

# ---- 3+4. 备份同名 Skill + 复制 11 个 Core Skills ----
echo "==> 复制 skills/* -> $SKILLS_DIR"
COPIED=0
for d in "$SKILLS_SRC"/*/; do
  name="$(basename "$d")"
  [ "$name" = "_lib" ] && continue
  target="$SKILLS_DIR/$name"
  if [ -e "$target" ]; then
    printf "   - %-24s 已存在 → 备份到 %s/%s.prepatch%s\n" "$name" "$SKILLS_DIR" "$name" "$NOW"
    if [ -d "$target" ] && [ ! -e "$target.prepatch$NOW" ]; then
      cp -r "$target" "${target}.prepatch${NOW}"
    fi
    rm -rf "$target"
  fi
  cp -r "$d" "$target"
  COPIED=$((COPIED+1))
done
echo "==> 复制完成：$COPIED 个 Skill"

# ---- 5. AGENTS.md：合并 or 复制 ----
if [ -e "$WORKSPACE_AGENTS" ]; then
  cp "$WORKSPACE_AGENTS" "${WORKSPACE_AGENTS}.prepatch${NOW}" 2>/dev/null \
    && echo "==> 目标 AGENTS.md 已存在 → 已备份到 ${WORKSPACE_AGENTS}.prepatch${NOW}"
  echo "==> 目标 AGENTS.md 已存在 → 未覆盖。请将本仓库 AGENTS.md 的「Agent OS 核心协议」段合并进去"
  echo "    （见 docs/INSTALL.md Step 3；勿删其中的 Release Gate 硬规则）"
else
  cp "$AGENTS_SRC" "$WORKSPACE_AGENTS" \
    && echo "==> 目标 AGENTS.md 不存在 → 已复制到 $WORKSPACE_AGENTS"
fi

# ---- 6. 重载 / 重启 ----
if [ "$DO_RELOAD" -eq 1 ]; then
  echo "==> 重载 OpenClaw gateway"
  openclaw gateway restart 2>/dev/null \
    || (openclaw gateway stop 2>/dev/null; openclaw gateway start 2>/dev/null) \
    || echo "!! gateway 重载失败，请手工重启 openclaw"
fi

# ---- 7. 验证 11 ready ----
if [ "$DO_VERIFY" -eq 1 ] && command -v openclaw >/dev/null 2>&1; then
  N="$(openclaw skills list 2>/dev/null | grep -c '✓ ready')"
  echo "==> 检测到 ready Skill 数：$N（应 ≥ 11）"
  if [ "$N" -lt 11 ]; then
    echo "!! 未达 11 ready：请检查 skills 目录路径 $SKILLS_DIR 是否被 OpenClaw 配置加载"
    exit 3
  fi
  echo "==> 11 个 Core Skill 全部 ready ✓"
else
  echo "==> 跳过验证（--no-verify 或 openclaw 命令不可用），请手工确认: openclaw skills list | grep -c '✓ ready'"
fi

echo "==> Agent OS 安装完成。跑 5 项验收见 docs/QUICK-START.md；跑协议合规自检: python3 docs/tests/scripts/compliance.py"
exit 0
