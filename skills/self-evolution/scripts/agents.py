#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agents.py - Agent Registry 管理（V3.2 Multi-Agent Learning OS）

扫描工作区的多个 Agent 工作区，维护 memory/agents/REGISTRY.md，
支持列表 / 状态 / 能力 / 重叠检测。

用法：
  python3 agents.py --list           # 列出所有 Agent
  python3 agents.py --status         # 显示 Agent 状态
  python3 agents.py --capabilities   # 显示 Agent 能力
  python3 agents.py --overlap        # 检测能力重叠

数据存储：memory/agents/registry.json（结构化）+ memory/agents/REGISTRY.md（可读）
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

HOME = os.path.expanduser("~")
OPENCLAW_DIR = os.environ.get("OPENCLAW_HOME") or os.path.join(HOME, ".openclaw")
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.environ.get("OPENCLAW_WORKSPACE_DIR") or os.path.join(OPENCLAW_DIR, "workspace")

AGENTS_DIR = os.path.join(WORKSPACE, "memory", "agents")
REGISTRY_JSON = os.path.join(AGENTS_DIR, "registry.json")
REGISTRY_MD = os.path.join(AGENTS_DIR, "REGISTRY.md")

NL = chr(10)  # 真实换行


def discover_agents():
    """扫描工作区目录，识别 Agent 工作区。"""
    agents = []
    base = os.path.dirname(WORKSPACE)
    seen = set()
    for name in sorted(os.listdir(base or ".")):
        if not name.startswith("workspace-"):
            continue
        wdir = os.path.join(base, name)
        if not os.path.isdir(wdir):
            continue
        # 跳过备份目录
        if ".bak" in name:
            continue
        agent_id = name[len("workspace-"):]
        if agent_id in seen:
            continue
        # 只接受真正的 Agent 工作区：必须有 AGENTS.md 或 IDENTITY.md 或 SOUL.md
        # （排除 attestations 等非 Agent 目录）
        if not (os.path.exists(os.path.join(wdir, "AGENTS.md"))
                or os.path.exists(os.path.join(wdir, "IDENTITY.md"))
                or os.path.exists(os.path.join(wdir, "SOUL.md"))):
            continue
        seen.add(agent_id)
        info = {
            "id": agent_id,
            "path": wdir,
            "role": guess_role(wdir, agent_id),
            "skills": count_skills(wdir),
            "status": "active",
            "last_seen": None,
        }
        agents.append(info)

    # 从已有 registry 补充 last_seen 和 role 覆盖
    old = load_registry_data()
    old_map = {a.get("id"): a for a in old.get("agents", [])}
    for a in agents:
        if a["id"] in old_map:
            o = old_map[a["id"]]
            a["last_seen"] = o.get("last_seen")
            if o.get("role"):
                a["role"] = o["role"]
            if o.get("status"):
                a["status"] = o["status"]
    return agents


def guess_role(wdir, agent_id):
    """从工作区 AGENTS.md 猜测角色。"""
    try:
        with open(os.path.join(wdir, "AGENTS.md"), encoding="utf-8") as f:
            content = f.read()[:2000]
        for line in content.splitlines():
            line = line.strip()
            if any(k in line for k in ("角色", "Role", "主管", "负责")):
                cleaned = re.sub(r"[#*`|]", "", line)
                if cleaned and len(cleaned) < 80:
                    return cleaned
    except (OSError, IOError):
        pass
    return "未定义"


def count_skills(wdir):
    skills_dir = os.path.join(wdir, "skills")
    if os.path.isdir(skills_dir):
        try:
            return len([d for d in os.listdir(skills_dir)
                        if os.path.isdir(os.path.join(skills_dir, d))])
        except OSError:
            return 0
    return 0


def load_registry_data():
    if os.path.exists(REGISTRY_JSON):
        try:
            with open(REGISTRY_JSON, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"agents": [], "updated": None}


def save_registry_data(data):
    os.makedirs(AGENTS_DIR, exist_ok=True)
    with open(REGISTRY_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_registry_md(agents):
    os.makedirs(AGENTS_DIR, exist_ok=True)
    lines = ["# Agent Registry", ""]
    lines.append("> 自动生成于 %s（agents.py）" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    lines.append("")
    for a in agents:
        lines.append("## Agent: %s" % a["id"])
        lines.append("- ID: %s" % a["id"])
        lines.append("- Role: %s" % a["role"])
        lines.append("- Path: %s" % a["path"])
        lines.append("- Skills: %d" % a["skills"])
        lines.append("- Status: %s" % a["status"])
        lines.append("- Last seen: %s" % (a["last_seen"] or "unknown"))
        lines.append("")
    with open(REGISTRY_MD, "w", encoding="utf-8") as f:
        f.write(NL.join(lines))


def cmd_list(agents):
    if not agents:
        print("⚠️ 未发现任何 Agent 工作区（workspace-*）")
        return
    print("📇 Agent Registry（%d 个）" % len(agents))
    print()
    for a in agents:
        print("  • %s" % a["id"])
        print("      Role:   %s" % a["role"])
        print("      Skills: %s" % a["skills"])
        print("      Status: %s" % a["status"])


def cmd_status(agents):
    if not agents:
        print("⚠️ 未发现任何 Agent 工作区")
        return
    print("📊 Agent 状态")
    print()
    active = sum(1 for a in agents if a.get("status") == "active")
    print("  总数: %d，active: %d" % (len(agents), active))
    print()
    for a in agents:
        print("  [%s] %s — %s" % (a.get("status", "?"), a["id"], a["role"]))


def cmd_capabilities(agents):
    if not agents:
        print("⚠️ 未发现任何 Agent 工作区")
        return
    print("🧩 Agent 能力")
    print()
    for a in agents:
        print("  %s:" % a["id"])
        print("    role = %s" % a["role"])
        print("    skills = %d 个" % a["skills"])


def cmd_overlap(agents):
    if not agents:
        print("⚠️ 未发现任何 Agent 工作区")
        return
    print("🔍 能力重叠检测（按 role 文本相似）")
    print()
    by_role = defaultdict(list)
    for a in agents:
        by_role[a["role"]].append(a["id"])
    found = False
    for role, ids in by_role.items():
        if len(ids) > 1 and role != "未定义":
            print("  ⚠️ 重叠: [%s] 都定义为「%s」" % (", ".join(ids), role))
            found = True
    if not found:
        print("  ✅ 未发现明显重叠")
        print("  （如需精确检测请扩展 skills 交集分析）")


def cmd_sync_ontology(agents, deprecate=False):
    """把 Agent Registry 同步到 ontology（规范 §22/§23）。

    每次 agents.py 运行时调用：新增 Agent 自动建 ontology 实体；
    --deprecate 时对 registry 中缺失/退休的 Agent 走 proposal 治理。
    """
    import subprocess
    import sys
    bridge = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ontology_bridge.py")
    if not os.path.exists(bridge):
        print("⚠  ontology_bridge.py 不存在，跳过 ontology 同步")
        return
    print("🔗 同步 Agent 生命周期 → ontology")
    if deprecate:
        # 退休模式：registry 中不存在的 agent 标 deprecated（proposal）
        registry_ids = {a["id"] for a in agents}
        # 读取 ontology 现有 AGT 实体
        try:
            subprocess.run([sys.executable, bridge, "--status"],
                           capture_output=True, text=True, timeout=30)
        except Exception:
            pass
        print("  （退休标记请在 ontology 侧确认实体后再 --verify）")
        return
    # 正常同步：每个 active agent 建/确认实体（按名称查重，避免重复）
    for a in agents:
        if a.get("status") != "active":
            continue
        # 用 resolve 按名称查重：若 ontology 已有同名 Agent 则跳过
        r = subprocess.run(
            [sys.executable, bridge, "--resolve", "--text", a["id"]],
            capture_output=True, text=True, timeout=30)
        out = r.stdout or ""
        hit_existing = False
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("- AGT-") and a["id"] in s:
                hit_existing = True
                break
        if hit_existing:
            print("  ✓ 已存在（按名称查重跳过）: {0}".format(a["id"]))
            continue
        subprocess.run(
            [sys.executable, bridge, "--sync-agent",
             "--agent_id", a["id"], "--role", a.get("role", "")],
            capture_output=True, text=True, timeout=30)
    print("  ✓ Agent 生命周期已同步")


def main():
    parser = argparse.ArgumentParser(description="Agent Registry 管理（V3.2）")
    parser.add_argument("--list", action="store_true", help="列出所有 Agent")
    parser.add_argument("--status", action="store_true", help="显示 Agent 状态")
    parser.add_argument("--capabilities", action="store_true", help="显示 Agent 能力")
    parser.add_argument("--overlap", action="store_true", help="检测能力重叠")
    parser.add_argument("--sync-ontology", action="store_true", help="同步 Agent 生命周期到 ontology")
    parser.add_argument("--deprecate", action="store_true", help="退休标记（配合 --sync-ontology）")
    args = parser.parse_args()

    agents = discover_agents()

    data = load_registry_data()
    data["agents"] = agents
    data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_registry_data(data)
    write_registry_md(agents)

    if args.list:
        cmd_list(agents)
    elif args.status:
        cmd_status(agents)
    elif args.capabilities:
        cmd_capabilities(agents)
    elif args.overlap:
        cmd_overlap(agents)
    elif args.sync_ontology:
        cmd_sync_ontology(agents, deprecate=args.deprecate)
    else:
        cmd_list(agents)
        print()
        print("用法: agents.py --list|--status|--capabilities|--overlap")


if __name__ == "__main__":
    main()
