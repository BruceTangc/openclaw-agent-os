#!/usr/bin/env bash
# =============================================================================
# Agent OS 一键安装脚本（Grok #21）
#
# 把本仓库的 Core Skills + 共享库 + Runtime 模板安装到用户的 OpenClaw 环境，
# 消除「cp -r + 手合 AGENTS.md」的摩擦。行为对齐 docs/INSTALL.md。
#
#   1. 检测 OpenClaw 版本（≥ 2026.7.1-2）
#   2. 定位用户 skills 目录（默认 ~/.openclaw/skills，可用 --skills-dir 覆盖）
#   3. 备份同名 Skill（若目标已存在同目录先备份为 skill.prepatch备份时间戳）
#   4. cp -r skills/* -> 目标 skills 目录（包括共享 _lib）
#   5. 安装运行时 AGENTS.md，并为旧 HEARTBEAT.md 补充代码化维护入口
#   6. Active profile 显式启用 OpenClaw 原生 Heartbeat；不创建业务 Cron
#   7. 重载 / 重启 OpenClaw gateway 并动态验证全部 Core Skills ready
#
# 用法:
#   ./install.sh                      # 安装到默认 ~/.openclaw/skills
#   ./install.sh --skills-dir /path   # 指定 skills 目录
#   ./install.sh --profile basic      # 仅对话模式，不写 Heartbeat 配置
#   ./install.sh --heartbeat-every 1h # Active 模式自定义周期（默认 30m）
#   ./install.sh --heartbeat-agent main # 唯一 Heartbeat owner（默认 main）
#   ./install.sh --vault-dir /path/to/Vault # 启用 Obsidian 投影视图
#   ./install.sh --no-reload          # 跳过 gateway restart
#   ./install.sh --no-verify          # 跳过 skills list 验证
# =============================================================================
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO/skills"
AGENTS_SRC="$REPO/templates/AGENTS.runtime.md"
HEARTBEAT_SRC="$REPO/templates/HEARTBEAT.md"
NOW="$(date +%Y%m%d-%H%M%S)"

MIN_VERSION="2026.7.1"
MIN_PYTHON="3.9"

# ---- 参数解析 ----
SKILLS_DIR="${OPENCLAW_SKILLS_DIR:-${HOME}/.openclaw/skills}"
WORKSPACE_AGENTS="${OPENCLAW_WS_AGENTS:-${HOME}/.openclaw/AGENTS.md}"
WORKSPACE_HEARTBEAT="${OPENCLAW_WS_HEARTBEAT:-}"
PROFILE="active"
HEARTBEAT_EVERY="30m"
HEARTBEAT_AGENT="main"
VAULT_DIR=""
DO_RELOAD=1
DO_VERIFY=1

while [ $# -gt 0 ]; do
  case "$1" in
    --skills-dir) SKILLS_DIR="$2"; shift 2 ;;
    --ws-agents)  WORKSPACE_AGENTS="$2"; shift 2 ;;
    --profile)    PROFILE="$2"; shift 2 ;;
    --heartbeat-every) HEARTBEAT_EVERY="$2"; shift 2 ;;
    --heartbeat-agent) HEARTBEAT_AGENT="$2"; shift 2 ;;
    --vault-dir) VAULT_DIR="$2"; shift 2 ;;
    --no-reload)  DO_RELOAD=0; shift ;;
    --no-verify)  DO_VERIFY=0; shift ;;
    -h|--help)    sed -n '1,30p' "$0"; exit 0 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done

case "$PROFILE" in
  basic|active) ;;
  *) echo "未知 profile: $PROFILE（可选 basic|active）"; exit 2 ;;
esac
[ -n "$HEARTBEAT_AGENT" ] || { echo "Heartbeat Agent ID 不能为空"; exit 2; }
[ -n "$WORKSPACE_HEARTBEAT" ] || WORKSPACE_HEARTBEAT="$(dirname "$WORKSPACE_AGENTS")/HEARTBEAT.md"

echo "==> Agent OS 安装：源=$REPO  目标skills=$SKILLS_DIR"

# ---- 1. 检测强制运行依赖 ----
command -v openclaw >/dev/null 2>&1 \
  || { echo "!! 未找到 openclaw；Agent OS 不是独立 Runtime，安装终止"; exit 2; }
PYTHON_BIN=""
command -v python3 >/dev/null 2>&1 && PYTHON_BIN="python3"
[ -n "$PYTHON_BIN" ] || { command -v python >/dev/null 2>&1 && PYTHON_BIN="python"; }
[ -n "$PYTHON_BIN" ] \
  || { echo "!! 未找到 Python 3；Agent OS 核心脚本无法运行，安装终止"; exit 2; }
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' \
  || { echo "!! Python 版本低于 $MIN_PYTHON，安装终止"; exit 2; }
echo "==> Python $("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))') OK"

if command -v openclaw >/dev/null 2>&1; then
  VER="$(openclaw --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  if [ -z "${VER:-}" ]; then
    echo "!! 无法解析 openclaw 版本，安装终止"; exit 2
  elif [ "$(printf '%s\n' "$MIN_VERSION" "$VER" | sort -V | head -1)" = "$MIN_VERSION" ]; then
    echo "==> OpenClaw 版本 $VER ≥ $MIN_VERSION OK"
  else
    echo "!! OpenClaw 版本 $VER < $MIN_VERSION，安装终止"; exit 2
  fi
fi

# ---- 2. 创建目标 skills 目录 ----
mkdir -p "$SKILLS_DIR" || { echo "!! 无法创建 $SKILLS_DIR"; exit 1; }
mkdir -p "$(dirname "$WORKSPACE_AGENTS")" 2>/dev/null || true
mkdir -p "$(dirname "$WORKSPACE_AGENTS")/.agent-os/agents/$HEARTBEAT_AGENT" \
  "$(dirname "$WORKSPACE_AGENTS")/.agent-os/projects" \
  "$(dirname "$WORKSPACE_AGENTS")/.agent-os/shared" \
  "$(dirname "$WORKSPACE_AGENTS")/memory" || { echo "!! 无法初始化 Agent OS 状态目录"; exit 1; }

# ---- 2b. 旧版 Skill-local 状态安全迁移（复制+校验，不删除源） ----
if [ -n "$PYTHON_BIN" ] && [ -f "$REPO/scripts/migrate_runtime_state.py" ]; then
  echo "==> 检查旧版运行状态（目标 Agent: main）"
  if ! "$PYTHON_BIN" "$REPO/scripts/migrate_runtime_state.py" \
      --skills-root "$SKILLS_DIR" --workspace "$(dirname "$WORKSPACE_AGENTS")" \
      --agent main --apply >/dev/null; then
    echo "!! 运行状态迁移存在冲突，已停止安装；旧数据和现有目标均未被覆盖"
    exit 4
  fi
fi

# ---- 3+4. 备份同名 Skill + 复制 Core Skills 与共享库 ----
echo "==> 复制 skills/* -> $SKILLS_DIR"
COPIED=0
for d in "$SKILLS_SRC"/*/; do
  name="$(basename "$d")"
  target="$SKILLS_DIR/$name"
  if [ -e "$target" ]; then
    printf "   - %-24s 已存在 → 备份到 %s/%s.prepatch%s\n" "$name" "$SKILLS_DIR" "$name" "$NOW"
    if [ -d "$target" ] && [ ! -e "$target.prepatch$NOW" ]; then
      cp -r "$target" "${target}.prepatch${NOW}"
    fi
    rm -rf "$target"
  fi
  cp -r "$d" "$target"
  [ "$name" = "_lib" ] || COPIED=$((COPIED+1))
done
echo "==> 复制完成：$COPIED 个 Skill（11 Core + bundled extensions）+ 共享 _lib"

# ---- 5. AGENTS.md：合并 or 复制 ----
if [ -e "$WORKSPACE_AGENTS" ]; then
  cp "$WORKSPACE_AGENTS" "${WORKSPACE_AGENTS}.prepatch${NOW}" 2>/dev/null \
    && echo "==> 目标 AGENTS.md 已存在 → 已备份到 ${WORKSPACE_AGENTS}.prepatch${NOW}"
  echo "==> 目标 AGENTS.md 已存在 → 未覆盖。请按需合并 $AGENTS_SRC"
else
  cp "$AGENTS_SRC" "$WORKSPACE_AGENTS" \
    && echo "==> 目标 AGENTS.md 不存在 → 已复制到 $WORKSPACE_AGENTS"
fi

if [ -e "$WORKSPACE_HEARTBEAT" ]; then
  if grep -Fq "proactive.py heartbeat" "$WORKSPACE_HEARTBEAT"; then
    echo "==> 目标 HEARTBEAT.md 已包含 Agent OS 代码化维护入口 → 保留"
  else
    cp "$WORKSPACE_HEARTBEAT" "${WORKSPACE_HEARTBEAT}.prepatch${NOW}" 2>/dev/null \
      && echo "==> 旧 HEARTBEAT.md 已备份到 ${WORKSPACE_HEARTBEAT}.prepatch${NOW}"
    {
      printf '\n<!-- agent-os-maintenance-entry -->\n'
      cat "$HEARTBEAT_SRC"
      printf '<!-- /agent-os-maintenance-entry -->\n'
    } >> "$WORKSPACE_HEARTBEAT"
    echo "==> 已保留原内容并追加 Agent OS 代码化维护入口"
  fi
else
  cp "$HEARTBEAT_SRC" "$WORKSPACE_HEARTBEAT" \
    && echo "==> 已安装 Agent OS HEARTBEAT.md"
fi

# ---- 6. Active profile：使用 OpenClaw 原生 Heartbeat，零业务 Cron ----
if [ "$PROFILE" = "active" ] && command -v openclaw >/dev/null 2>&1; then
  echo "==> Active profile：配置 OpenClaw Heartbeat every=$HEARTBEAT_EVERY"
  openclaw config set agents.defaults.heartbeat.every "$HEARTBEAT_EVERY" >/dev/null 2>&1 \
    || { echo "!! Heartbeat 配置失败；可稍后手工设置，不影响 Basic 对话能力"; }
  openclaw config set agents.defaults.heartbeat.agentId "$HEARTBEAT_AGENT" >/dev/null 2>&1 \
    || { echo "!! Heartbeat owner 配置失败；为避免多 Agent 同时巡检，安装终止"; exit 5; }
  echo "==> Heartbeat owner：$HEARTBEAT_AGENT（其他 Agent 不单独启用）"
  CRON_ENABLED="$(openclaw config get cron.enabled 2>/dev/null || true)"
  if [ "$CRON_ENABLED" = "false" ]; then
    echo "!! 检测到 cron.enabled=false；OpenClaw 不会运行 Heartbeat。保留用户显式设置，未自动开启。"
  fi
  echo "==> 未创建业务 Cron（仅精确时间任务按用户需求创建）"
elif [ "$PROFILE" = "basic" ]; then
  echo "==> Basic profile：不修改 Heartbeat 配置"
fi

# ---- 6b. 可选 Obsidian：使用 OpenClaw 官方 env.vars 持久化普通路径变量 ----
if [ -n "$VAULT_DIR" ]; then
  command -v openclaw >/dev/null 2>&1 \
    || { echo "!! --vault-dir 需要 openclaw config；安装终止"; exit 6; }
  mkdir -p "$VAULT_DIR" || { echo "!! 无法创建 Vault 目录: $VAULT_DIR"; exit 6; }
  openclaw config set env.vars.AGENT_OS_VAULT_DIR "$VAULT_DIR" >/dev/null 2>&1 \
    || { echo "!! 无法持久化 AGENT_OS_VAULT_DIR；安装终止"; exit 6; }
  echo "==> Obsidian Vault 已启用：$VAULT_DIR（Heartbeat 仅自动 export+reconcile）"
else
  echo "==> Obsidian Vault 未配置：保持禁用，不创建默认目录"
fi

# ---- 7. 重载 / 重启 ----
if [ "$DO_RELOAD" -eq 1 ]; then
  echo "==> 重载 OpenClaw gateway"
  openclaw gateway restart 2>/dev/null \
    || (openclaw gateway stop 2>/dev/null; openclaw gateway start 2>/dev/null) \
    || echo "!! gateway 重载失败，请手工重启 openclaw"
fi

# ---- 8. 动态验证 Core Skills ready ----
if [ "$DO_VERIFY" -eq 1 ] && command -v openclaw >/dev/null 2>&1; then
  SKILLS_OUTPUT="$(openclaw skills list 2>/dev/null || true)"
  MISSING=""
  VERIFIED=0
  for d in "$SKILLS_SRC"/*/; do
    name="$(basename "$d")"
    [ "$name" = "_lib" ] && continue
    if printf '%s\n' "$SKILLS_OUTPUT" | grep -F "$name" | grep -q '✓ ready'; then
      VERIFIED=$((VERIFIED+1))
    else
      MISSING="$MISSING $name"
    fi
  done
  if [ -n "$MISSING" ]; then
    echo "!! 以下 Skill 未 ready:$MISSING"
    echo "!! 请确认共享目录 $SKILLS_DIR 已被 OpenClaw 加载"
    exit 3
  fi
  OWNER="$(openclaw config get agents.defaults.heartbeat.agentId 2>/dev/null || true)"
  if [ "$PROFILE" = "active" ] && [ "$OWNER" != "$HEARTBEAT_AGENT" ]; then
    echo "!! Heartbeat owner 验证失败：期望=$HEARTBEAT_AGENT 实际=${OWNER:-<empty>}"
    exit 5
  fi
  echo "==> $VERIFIED 个 bundled Skills 全部 ready；Heartbeat owner 验证通过 ✓"
  if [ -n "$PYTHON_BIN" ]; then
    OPENCLAW_WORKSPACE="$(dirname "$WORKSPACE_AGENTS")" OPENCLAW_AGENT_ID="$HEARTBEAT_AGENT" \
      AGENT_OS_VAULT_DIR="$VAULT_DIR" \
      "$PYTHON_BIN" "$SKILLS_DIR/proactive/scripts/agent_os.py" doctor \
      || { echo "!! Agent OS Doctor 验收失败"; exit 7; }
    echo "==> Agent OS Doctor 验收通过 ✓"
  fi
else
  echo "==> 跳过验证（--no-verify 或 openclaw 命令不可用），请手工确认: openclaw skills list | grep -c '✓ ready'"
fi

echo "==> Agent OS 安装完成（profile=$PROFILE）。验收见 docs/QUICK-START.md；质量门: python3 scripts/quality_gate.py"
exit 0
