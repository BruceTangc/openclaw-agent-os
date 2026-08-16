#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrator 纯逻辑层 (V1.0)

OpenClaw 总调度中枢可运行的确定性核心。实现文档【Orchestrator v1.0】中被
可以确定性落地的部分，供上层(Agent/LLM)作为规划调度辅助调用：

  --task        解析/拆解请求 → Task 列表 (Intent Understanding + Goal Model)
  --dag         构建任务 DAG + 环路检测 + 拓扑排序 (§8)
  --route       能力匹配 / Agent 选择 (routing_score, §12-13)
  --plan        生成执行计划 (execution_plan, §18)
  --verify      结果验证分级 (V0-V4, §36)
  --dag-check   依赖检查 + 环路检测

与 Proactive 的接口 (文档 §1.1 §55):
  Proactive 提交 orchestration_request (source=proactive)
  → Orchestrator 拆解/路由/执行
  → 返回 orchestration_result

与现有系统的边界:
  - Ontology      → 读世界模型辅助规划, 由上层调 ontology.py
  - Self-Evol     → --route 发现连续失败 / --evol 提进化候选
  - Agent-Browser → 搜索浏览由上层调 openclaw browser
  - Summarize     → 压缩由上层调 summarize.py
  - Proactive     → 决定"是否值得做", Orchestrator 决定"怎么做"
"""

import argparse
import json
import os
import sys
from collections import deque

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
# 标准 Task Types (文档 §9)
TASK_TYPES = [
    "research", "search", "browse", "retrieve", "summarize", "analyze",
    "compare", "write", "transform", "calculate", "execute", "update",
    "verify", "review", "decision", "handoff",
]

# 风险等级 (文档 §29)
RISK_LEVELS = ["low", "medium", "high", "critical"]

# 权限等级 (文档 §28)
PERMISSION_LEVELS = [
    "READ", "SEARCH", "WRITE", "EXECUTE",
    "DELETE", "EXTERNAL_SEND", "FINANCIAL", "ADMIN",
]

# 验证等级 (文档 §36)
VERIFY_LEVELS = ["V0", "V1", "V2", "V3", "V4"]

# Execution 状态 (文档 §21-22)
EXEC_STATES = [
    "pending", "ready", "running", "waiting", "paused",
    "retrying", "failed", "completed", "cancelled", "blocked",
]

# 默认重试 (文档 §23)
DEFAULT_MAX_RETRIES = 2

# 默认预算 (文档 §31)
DEFAULT_BUDGET = {
    "max_runtime_minutes": 30,
    "max_tool_calls": 50,
    "max_parallel_tasks": 5,
    "max_retries": 2,
    "max_iterations": 3,
    "max_cost": None,
}


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_json(path, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_stdin_or_json(raw, label):
    if raw == "-":
        return json.load(sys.stdin)
    if raw is None:
        return {}
    try:
        return json.loads(raw)
    except Exception as e:
        return {"__error": f"{label}不是合法JSON: {e}", "_raw": raw}


# ---------------------------------------------------------------------------
# Intent Understanding + Goal Model (文档 §4 §5)
# ---------------------------------------------------------------------------
def parse_request(req):
    """统一输入 → 结构化 orchestration_request (文档 §3)."""
    now_req = dict(req or {})
    out = {
        "id": now_req.get("id", "req_" + str(hash(json.dumps(now_req, sort_keys=True)) & 0xffff)),
        "source": now_req.get("source", "user"),
        "objective": now_req.get("objective", now_req.get("goal", "")),
        "context": now_req.get("context", {}),
        "constraints": now_req.get("constraints", []),
        "deadline": now_req.get("deadline"),
        "priority": _f(now_req.get("priority")),
        "risk_level": now_req.get("risk_level", "low"),
        "requested_output": now_req.get("requested_output", {}),
        "permissions": now_req.get("permissions", []),
    }
    if out["risk_level"] not in RISK_LEVELS:
        out["risk_level"] = "low"
    return out


def goal_model(req):
    """建立 Goal (文档 §5). 目标不清晰 → 标记需要 ASK."""
    g = {
        "id": "goal_" + str(abs(hash(req.get("objective", ""))) & 0xfffff),
        "objective": req.get("objective", ""),
        "success_condition": req.get("success_condition", []),
        "constraints": req.get("constraints", []),
        "deadline": req.get("deadline"),
        "priority": _f(req.get("priority")),
        "risk": req.get("risk_level", "low"),
    }
    if not g["objective"] or not g["success_condition"]:
        g["_needs_ask"] = True
        g["_reason"] = "目标缺失或缺少成功条件"
    return g


# ---------------------------------------------------------------------------
# Task Decomposition (文档 §7 §9)
# ---------------------------------------------------------------------------
def decompose(req):
    """拆解目标 → Task 列表. 支持显式 tasks 或由 objective 推断."""
    if req.get("tasks"):
        return [dict(t) for t in req["tasks"]]
    # 无显式 task 时, 按 objective 关键字做简单映射(纯启发式, 供上层补充)
    objective = req.get("objective", "").lower()
    hint_tasks = []
    if any(k in objective for k in ["研究", "调研", "research", "分析趋势"]):
        hint_tasks.append({"type": "research", "objective": "研究"})
    if any(k in objective for k in ["搜索", "search", "找", "查"]):
        hint_tasks.append({"type": "search", "objective": "搜索"})
    if any(k in objective for k in ["总结", "摘要", "summarize", "压缩"]):
        hint_tasks.append({"type": "summarize", "objective": "总结"})
    if any(k in objective for k in ["写", "write", "报告", "report"]):
        hint_tasks.append({"type": "write", "objective": "撰写"})
    if any(k in objective for k in ["对比", "比较", "compare", "评估"]):
        hint_tasks.append({"type": "compare", "objective": "对比"})
    if any(k in objective for k in ["执行", "execute", "运行", "下单", "创建"]):
        hint_tasks.append({"type": "execute", "objective": "执行"})
    if not hint_tasks:
        hint_tasks.append({"type": "analyze", "objective": objective or "分析"})
    out = []
    for i, t in enumerate(hint_tasks, 1):
        out.append({
            "id": "T%d" % i,
            "objective": t.get("objective") or req.get("objective", ""),
            "type": t["type"] if t["type"] in TASK_TYPES else "analyze",
            "inputs": [],
            "outputs": [],
            "dependencies": [],
            "required_capabilities": [],
            "risk": "low",
            "priority": 0,
        })
    return out


# ---------------------------------------------------------------------------
# DAG (文档 §8)
# ---------------------------------------------------------------------------
def build_dag(tasks, edges):
    """建 DAG + 环路检测 + 拓扑排序. edges: [["T1","T2"], ...] (T1 → T2)."""
    ids = set(t["id"] for t in tasks)
    graph = {tid: [] for tid in ids}
    indeg = {tid: 0 for tid in ids}
    for a, b in edges:
        if a in ids and b in ids:
            graph[a].append(b)
            indeg[b] += 1
    # 环路检测 (Kahn)
    q = deque([n for n in ids if indeg[n] == 0])
    order = []
    while q:
        n = q.popleft()
        order.append(n)
        for m in graph[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    cycle = [n for n in ids if indeg[n] > 0]
    return {
        "node_count": len(ids),
        "edge_count": len(edges),
        "has_cycle": bool(cycle),
        "cycle_nodes": cycle,
        "topological_order": order if not cycle else [],
        "graph": graph,
    }


# ---------------------------------------------------------------------------
# Capability Routing (文档 §10 §12 §13)
# ---------------------------------------------------------------------------
# 内置能力注册表(最小集, 上层可覆盖)
CAPABILITY_REGISTRY = [
    {"id": "web_research", "provider": "agent-browser",
     "capabilities": ["research", "search", "browse", "retrieve"],
     "risk": "low", "reliability": 0.90, "avg_cost": 0.3, "avg_latency": 20},
    {"id": "summarize", "provider": "summarize",
     "capabilities": ["summarize", "compare", "write"],
     "risk": "low", "reliability": 0.95, "avg_cost": 0.05, "avg_latency": 3},
    {"id": "ontology", "provider": "ontology",
     "capabilities": ["retrieve", "update", "analyze"],
     "risk": "low", "reliability": 0.95, "avg_cost": 0.02, "avg_latency": 1},
    {"id": "social_research", "provider": "social-search",
     "capabilities": ["research", "search"],
     "risk": "low", "reliability": 0.85, "avg_cost": 0.2, "avg_latency": 15},
    {"id": "self_evolution", "provider": "self-evolution",
     "capabilities": ["analyze", "update"],
     "risk": "low", "reliability": 0.80, "avg_cost": 0.1, "avg_latency": 5},
    {"id": "proactive", "provider": "proactive",
     "capabilities": ["decision", "analyze"],
     "risk": "low", "reliability": 0.90, "avg_cost": 0.03, "avg_latency": 2},
]


def routing_score(cap, required_type, req_risk="low"):
    """文档 §13: 能力匹配 × 可靠性 ... / (成本×延迟×风险)."""
    match = 1.0 if required_type in cap["capabilities"] else 0.0
    reliability = _f(cap.get("reliability"))
    cost = max(_f(cap.get("avg_cost")), 0.05)
    latency = max(_f(cap.get("avg_latency")), 1)
    risk_mult = {"low": 1.0, "medium": 1.2, "high": 1.5, "critical": 2.0}[req_risk]
    score = match * reliability * 100.0 / (cost * latency * risk_mult)
    return round(max(0, min(100, score)), 1)


def route(required_type, registry=None, req_risk="low"):
    """能力匹配 → 排序结果列表."""
    reg = registry or CAPABILITY_REGISTRY
    results = []
    for cap in reg:
        score = routing_score(cap, required_type, req_risk)
        results.append({
            "capability_id": cap["id"],
            "provider": cap["provider"],
            "type": required_type,
            "score": score,
            "reliability": cap["reliability"],
            "risk": cap["risk"],
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results




# ---------------------------------------------------------------------------
# Permission Gate (Agent OS v1.1 H2 修复): route 分发前的权限闸门
# 调用 permission-security 分类器, L3+ 无授权 → 标记需审批, 阻断自动分发
# ---------------------------------------------------------------------------
PERMISSION_CLASSIFIER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "permission-security", "scripts", "permission.py")


def permission_gate(action, resource_type="internal", side_effect="NONE",
                    scope=None, authorized=False):
    """分发前闸门: 返回 {allowed, level, decision, reason}."""
    try:
        import subprocess
        req = {
            "action": action,
            "resource_type": resource_type,
            "external_side_effect": side_effect,
            "scope": scope,
            "authorized": authorized,
        }
        proc = subprocess.run(
            [sys.executable, PERMISSION_CLASSIFIER, "check",
             "--json", json.dumps(req, ensure_ascii=False)],
            capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            result = json.loads(proc.stdout)
            level = result.get("level", "L0")
            decision = result.get("decision", "allow")
            return {
                "allowed": decision == "allow",
                "level": level,
                "decision": decision,
                "reason": result.get("reason", ""),
                "requires_approval": result.get("requires_approval", False),
            }
    except Exception as e:
        # Fail closed: 分类器不可用 → 高风险动作拒绝 (§111)
        return {"allowed": False, "level": "R?", "decision": "deny",
                "reason": "permission classifier unavailable: " + str(e),
                "requires_approval": True}
    return {"allowed": True, "level": "L0", "decision": "allow",
            "reason": "no permission check requested", "requires_approval": False}

# ---------------------------------------------------------------------------
# Execution Plan (文档 §18)
# ---------------------------------------------------------------------------
def build_plan(req, tasks, dag_result=None):
    """生成 execution_plan."""
    return {
        "id": "plan_" + str(abs(hash(json.dumps(req, sort_keys=True))) & 0xfffff),
        "objective": req.get("objective", ""),
        "tasks": tasks,
        "dag": dag_result,
        "budget": DEFAULT_BUDGET,
        "success_condition": req.get("success_condition", []),
    }


# ---------------------------------------------------------------------------
# Verification (文档 §35 §36)
# ---------------------------------------------------------------------------
def verify_result(result, level="V1"):
    """按验证等级检查结果. V0→V4 逐级累计, 高等级必须同时满足低等级全部检查 (§55)."""
    if level not in VERIFY_LEVELS:
        level = "V1"
    res = {"level": level, "passed": False, "checks": []}
    # V0: 工具返回成功
    res["checks"].append({"check": "V0 tool_success", "ok": bool(result.get("tool_success"))})
    if level == "V0":
        res["passed"] = all(c["ok"] for c in res["checks"])
        return res
    # V1: 输出格式正确
    has_output = "output" in result or "outputs" in result or "summary" in result
    res["checks"].append({"check": "V1 format", "ok": has_output})
    if level == "V1":
        res["passed"] = all(c["ok"] for c in res["checks"])
        return res
    # V2: 结果符合任务条件
    condition_ok = bool(result.get("success_condition_met"))
    res["checks"].append({"check": "V2 condition", "ok": condition_ok})
    if level == "V2":
        res["passed"] = all(c["ok"] for c in res["checks"])
        return res
    # V3: 独立验证
    independent = bool(result.get("independently_verified"))
    res["checks"].append({"check": "V3 independent", "ok": independent})
    if level == "V3":
        res["passed"] = all(c["ok"] for c in res["checks"])
        return res
    # V4: 外部状态变化
    state_changed = bool(result.get("state_changed"))
    res["checks"].append({"check": "V4 external_state", "ok": state_changed})
    res["passed"] = all(c["ok"] for c in res["checks"])
    return res


# ---------------------------------------------------------------------------
# Orchestration Result (文档 §55)
# ---------------------------------------------------------------------------
def orchestration_result(req, plan, status="completed", summary=""):
    """Proactive/上层拿到的标准返回."""
    return {
        "request_id": req.get("id"),
        "status": status,  # completed|partial|failed|waiting
        "plan_id": plan.get("id"),
        "summary": summary,
        "completed_tasks": [],
        "pending_tasks": [t["id"] for t in plan.get("tasks", [])],
        "artifacts": [],
        "next_action": None,
        "confidence": 0.0,
    }


# ---------------------------------------------------------------------------
# Evolution Candidate (文档 §42)
# ---------------------------------------------------------------------------
def evolution_candidate(category, problem, evidence, frequency, impact,
                        proposed_change, confidence, requires_approval=True):
    if category not in ("routing", "skill", "workflow", "capability"):
        category = "skill"
    return {
        "category": category,
        "problem": problem,
        "evidence": evidence if isinstance(evidence, list) else [evidence],
        "frequency": frequency,
        "impact": impact,
        "proposed_change": proposed_change,
        "confidence": confidence,
        "requires_approval": requires_approval,
    }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Orchestrator 纯逻辑层")
    sub = parser.add_subparsers(dest="cmd")

    p_parse = sub.add_parser("parse", help="解析请求 → orchestration_request")
    p_parse.add_argument("--json", help="请求 JSON 或 -")

    p_goal = sub.add_parser("goal", help="建立 Goal Model")
    p_goal.add_argument("--json", help="请求 JSON 或 -")

    p_dec = sub.add_parser("decompose", help="任务拆解")
    p_dec.add_argument("--json", help="请求 JSON 或 -")

    p_dag = sub.add_parser("dag", help="构建 DAG + 环路检测")
    p_dag.add_argument("--json", help="tasks JSON 或 -")
    p_dag.add_argument("--edges", nargs="*", help="边 A-B")

    p_route = sub.add_parser("route", help="能力匹配/路由")
    p_route.add_argument("--type", required=True)
    p_route.add_argument("--risk", default="low")
    p_route.add_argument("--action", default=None, help="闸门检查的动作名 (read/send/delete/...)")
    p_route.add_argument("--authorized", action="store_true", help="是否已有授权")

    p_plan = sub.add_parser("plan", help="生成执行计划")
    p_plan.add_argument("--json", help="请求 JSON 或 -")

    p_verify = sub.add_parser("verify", help="结果验证")
    p_verify.add_argument("--json", help="result JSON 或 -")
    p_verify.add_argument("--level", default="V1")

    p_evol = sub.add_parser("evol", help="进化候选")
    p_evol.add_argument("--category", default="skill")
    p_evol.add_argument("--problem", required=True)
    p_evol.add_argument("--evidence", nargs="*", default=[])
    p_evol.add_argument("--frequency", type=int, default=1)
    p_evol.add_argument("--impact", type=float, default=0.0)
    p_evol.add_argument("--change", required=True)
    p_evol.add_argument("--confidence", type=float, default=0.0)
    p_evol.add_argument("--no-approval", action="store_true")

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        return

    if args.cmd == "parse":
        print(json.dumps(parse_request(read_stdin_or_json(args.json, "request")),
                         ensure_ascii=False, indent=2))
        return

    if args.cmd == "goal":
        req = parse_request(read_stdin_or_json(args.json, "request"))
        print(json.dumps(goal_model(req), ensure_ascii=False, indent=2))
        return

    if args.cmd == "decompose":
        req = read_stdin_or_json(args.json, "request")
        print(json.dumps(decompose(req), ensure_ascii=False, indent=2))
        return

    if args.cmd == "dag":
        tasks = read_stdin_or_json(args.json, "tasks")
        if not isinstance(tasks, list):
            tasks = tasks.get("tasks", []) if isinstance(tasks, dict) else []
        # edges 解析: ["T1-T2", "T3-T4"]
        edges = []
        for e in (args.edges or []):
            if "-" in e:
                a, b = e.split("-", 1)
                edges.append([a.strip(), b.strip()])
        print(json.dumps(build_dag(tasks, edges), ensure_ascii=False, indent=2))
        return

    if args.cmd == "route":
        out = {"route": route(args.type, req_risk=args.risk)}
        if args.action:
            out["permission_gate"] = permission_gate(
                args.action, side_effect=args.risk,
                authorized=args.authorized)
            if not out["permission_gate"]["allowed"]:
                out["blocked"] = True
                out["block_reason"] = out["permission_gate"]["reason"]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.cmd == "plan":
        req = read_stdin_or_json(args.json, "request")
        tasks = decompose(req)
        dag = build_dag(tasks, [])
        print(json.dumps(build_plan(req, tasks, dag), ensure_ascii=False, indent=2))
        return

    if args.cmd == "verify":
        result = read_stdin_or_json(args.json, "result")
        print(json.dumps(verify_result(result, args.level), ensure_ascii=False, indent=2))
        return

    if args.cmd == "evol":
        cand = evolution_candidate(
            args.category, args.problem, args.evidence, args.frequency,
            args.impact, args.change, args.confidence,
            requires_approval=not args.no_approval)
        print(json.dumps(cand, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
