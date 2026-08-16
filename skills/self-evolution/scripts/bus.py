#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bus.py - Learning Bus（V3.2 Multi-Agent Learning OS）

Agent 与中央 Learning OS 之间的受控学习事件总线。
Agent 通过发布事件提交学习候选，由 Learning OS 决定 scope 与去向。

用法：
  python3 bus.py --status                 # 显示总线状态
  python3 bus.py --pending                # 显示待处理事件
  python3 bus.py --publish <event_json>   # 发布学习事件
  python3 bus.py --publish-easy --topic X --content Y --scope AGENT --agent ID --confidence 82

数据存储：memory/agents/bus.json（事件队列）
"""
import argparse
import json
import os
import sys
from datetime import datetime

HOME = os.path.expanduser("~")
OPENCLAW_DIR = os.environ.get("OPENCLAW_HOME") or os.path.join(HOME, ".openclaw")
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.environ.get("OPENCLAW_WORKSPACE_DIR") or os.path.join(OPENCLAW_DIR, "workspace")

AGENTS_DIR = os.path.join(WORKSPACE, "memory", "agents")
BUS_JSON = os.path.join(AGENTS_DIR, "bus.json")

# 中央总线（单一事实源）：所有 Agent 上报都写到这里（L3: 跟随 WORKSPACE, 不硬编码）
CENTRAL_BUS_JSON = os.path.join(WORKSPACE, "memory", "agents", "bus.json")
CENTRAL_AGENTS_DIR = os.path.join(WORKSPACE, "memory", "agents")

ALLOWED_SCOPES = ("TASK", "AGENT", "PROJECT", "USER", "GLOBAL")
ALLOWED_EVENTS = (
    "learning_candidate", "correction", "error", "success", "intermediate_state",
    "decision", "skill_candidate", "verification_result", "contradiction",
    "promotion_request", "demotion_request", "rollback_request",
    "agent_created", "agent_updated", "agent_deprecated",
)


def load_bus():
    if os.path.exists(BUS_JSON):
        try:
            with open(BUS_JSON, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"events": [], "stats": {"total": 0, "pending": 0, "resolved": 0}}


def save_bus(bus):
    os.makedirs(AGENTS_DIR, exist_ok=True)
    with open(BUS_JSON, "w", encoding="utf-8") as f:
        json.dump(bus, f, indent=2, ensure_ascii=False)


def next_id(bus):
    # 幂等: 用时间戳+单调计数, 避免删除后重号
    seq = bus.get("stats", {}).get("total", 0) + 1
    return "EVT-%s-%04d" % (datetime.now().strftime("%Y%m%d%H%M%S"), seq % 10000)


def publish(bus, event):
    """发布一个学习事件，默认 scope=AGENT。"""
    ev = dict(event)
    ev.setdefault("event", "learning_candidate")
    ev.setdefault("scope", "AGENT")
    ev.setdefault("confidence", 0)
    ev.setdefault("status", "pending")
    ev.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    ev.setdefault("id", next_id(bus))
    # 校验 scope
    scope = ev.get("scope")
    if scope not in ALLOWED_SCOPES:
        print("❌ 非法 scope: %s（允许: %s）" % (scope, ", ".join(ALLOWED_SCOPES)))
        return None
    # 校验 event 类型 (L1 修复)
    etype = ev.get("event")
    if etype not in ALLOWED_EVENTS:
        print("❌ 非法 event 类型: %s（允许: %s）" % (etype, ", ".join(ALLOWED_EVENTS)))
        return None
    bus.setdefault("events", []).append(ev)
    bus.setdefault("stats", {}).setdefault("total", 0)
    bus["stats"]["total"] += 1
    bus["stats"]["pending"] = bus["stats"].get("pending", 0) + 1
    save_bus(bus)
    print("✅ 事件已发布: [%s] %s (scope=%s, 来自 %s)" % (
        ev["id"], ev.get("event"), ev.get("scope"), ev.get("source_agent", "?")))
    return ev["id"]


def cmd_status(bus):
    events = bus.get("events", [])
    pending = [e for e in events if e.get("status") == "pending"]
    resolved = [e for e in events if e.get("status") == "resolved"]
    print("🚌 Learning Bus 状态")
    print("  总事件: %d" % len(events))
    print("  pending: %d" % len(pending))
    print("  resolved: %d" % len(resolved))
    by_scope = {}
    for e in events:
        s = e.get("scope", "AGENT")
        by_scope[s] = by_scope.get(s, 0) + 1
    if by_scope:
        print("  按 scope:")
        for s in ALLOWED_SCOPES:
            if s in by_scope:
                print("    %s: %d" % (s, by_scope[s]))


def cmd_pending(bus):
    events = bus.get("events", [])
    pend = [e for e in events if e.get("status") == "pending"]
    if not pend:
        print("✅ 没有待处理事件")
        return
    print("⏳ 待处理事件（%d 条）:" % len(pend))
    for e in pend[:20]:
        print("  [%s] %s | scope=%s | 来自 %s | conf=%s" % (
            e.get("id"), e.get("event"),
            e.get("scope"), e.get("source_agent", "?"), e.get("confidence", 0)))
        print("      %s" % (e.get("content", ""))[:80])


def main():
    parser = argparse.ArgumentParser(description="Learning Bus（V3.2）")
    parser.add_argument("--status", action="store_true", help="显示总线状态")
    parser.add_argument("--pending", action="store_true", help="显示待处理事件")
    parser.add_argument("--publish", nargs=1, metavar="JSON", help="发布事件（JSON 字符串）")
    parser.add_argument("--event", default="learning_candidate", help="事件类型")
    parser.add_argument("--topic", default=None, help="主题")
    parser.add_argument("--content", default=None, help="内容")
    parser.add_argument("--scope", default="AGENT", help="scope: TASK|AGENT|PROJECT|USER|GLOBAL")
    parser.add_argument("--agent", default=None, help="来源 Agent ID")
    parser.add_argument("--confidence", type=int, default=0, help="置信度 0-100")
    parser.add_argument("--project", default=None, help="项目名")
    parser.add_argument("--central", action="store_true", help="强制写入中央 Learning Bus（主工作区 memory/agents/bus.json）")
    args = parser.parse_args()

    global BUS_JSON, AGENTS_DIR
    if args.central:
        BUS_JSON = CENTRAL_BUS_JSON
        AGENTS_DIR = CENTRAL_AGENTS_DIR

    bus = load_bus()

    if args.publish:
        raw = args.publish[0]
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            print("❌ 无效 JSON: %s" % raw)
            return
        publish(bus, ev)
    elif args.content:
        ev = {
            "event": args.event,
            "topic": args.topic,
            "content": args.content,
            "scope": args.scope.upper(),
            "source_agent": args.agent,
            "confidence": args.confidence,
            "project": args.project,
        }
        publish(bus, ev)
    elif args.status:
        cmd_status(bus)
    elif args.pending:
        cmd_pending(bus)
    else:
        cmd_status(bus)
        print()
        print("用法:")
        print("  bus.py --publish '{\"event\":\"learning_candidate\",\"topic\":\"x\",\"content\":\"y\"}'")
        print("  bus.py --topic x --content y --scope AGENT --agent my-agent --confidence 82")
        print("  bus.py --status | --pending")


if __name__ == "__main__":
    main()
