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
import subprocess
import sys
from collections import deque

# v1.3 Hardening B2: 统一 ID helper
_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "_lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from id_utils import generate_id, deterministic_id

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
        "id": now_req.get("id") or generate_id("request"),
        "source": now_req.get("source", "user"),
        "objective": now_req.get("objective", now_req.get("goal", "")),
        "success_condition": now_req.get("success_condition", now_req.get("success_criteria", [])),
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
        "id": "goal_" + deterministic_id("goal", {"objective": req.get("objective", "")}).split("_", 1)[1],
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
    """拆解目标 → Task 列表. 支持显式 tasks 或由 objective 推断。

    ORC-05：无显式 tasks 时，关键词映射仅是 heuristic fallback candidate（启发式
    候选），不是最终 execution DAG。真正 DAG 应由 LLM plan → dependency → validation →
    DAG；本函数产出只作 fallback，供上层补充依赖/校验后使用。
    """
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
            "_decompose_source": "heuristic_fallback",
        })
    return out


# ---------------------------------------------------------------------------
# DAG (文档 §8)
# ---------------------------------------------------------------------------
def build_dag(tasks, edges):
    """建 DAG + 环路检测 + 拓扑排序. edges: [["T1","T2"], ...] (T1 → T2)。

    ORC-04：非法 edge（引用不存在的节点）不静默忽略，而是记录 invalid_edges 并
    标记 planning_error，避免「输入 DAG ≠ 实际 DAG」。
    CHAIN-01/审计9：cycle（含 self-dependency）同样是规划完整性错误，一并标记
    planning_error —— 环无法拓扑排序，不得当作 PLAN_READY / 交付可执行序列。
    """
    ids = set(t["id"] for t in tasks)
    graph = {tid: [] for tid in ids}
    indeg = {tid: 0 for tid in ids}
    invalid_edges = []
    for a, b in edges:
        if a not in ids or b not in ids:
            # 引用了不存在的节点 → 非法依赖，不静默忽略
            invalid_edges.append([a, b])
            continue
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
    has_cycle = bool(cycle)
    return {
        "node_count": len(ids),
        "edge_count": len(edges),
        "has_cycle": has_cycle,
        "cycle_nodes": cycle,
        "invalid_edges": invalid_edges,
        # 审计9: planning_error 覆盖两种规划完整性错误 ——
        #   ① 非法 edge（引用不存在节点, ORC-04）
        #   ② 环/自依赖（无法拓扑排序）
        # 任一为真即判定 planning_error，build_plan 将 PLAN_REJECTED + 清空 tasks。
        "planning_error": bool(invalid_edges) or has_cycle,
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
    """分发前闸门 (fail-closed): 返回 {allowed, level, decision, reason}.

    PHASE 1 P0 (Hardening Patch):
      classifier 正常 → ALLOW / ASK / DENY
      classifier timeout / non-zero / malformed JSON / missing fields /
      exception → DENY (fail-closed)

    只有分类器明确返回 decision == "allow" 才放行; 任何异常/缺失/歧义一律拒绝。
    OpenClaw 原生 policy/approval 仍是最终执行边界, 本函数不取代它。

    ORC-01（收口）：本函数是 permission-security 的 **adapter**，不是第二 Permission
    Engine。只调 classifier 透传 decision。禁止在 Orchestrator 层增加 risk scoring /
    authority calculation / approval state / permission policy / permission delegation。
    Orchestrator 只能：Permission Request → permission-security → Authorization Decision
    → OpenClaw Runtime（最终执行边界）。
    """
    fail_closed = {
        "allowed": False, "level": "R?", "decision": "deny",
        "requires_approval": True,
    }
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
        if proc.returncode != 0:
            # non-zero exit → DENY
            return dict(fail_closed, reason="permission classifier exited non-zero")
        try:
            result = json.loads(proc.stdout)
        except Exception as e:
            # malformed JSON → DENY
            return dict(fail_closed, reason="permission classifier returned malformed JSON: " + str(e))
        if not isinstance(result, dict):
            return dict(fail_closed, reason="permission classifier returned non-object result")
        decision = result.get("decision")
        if decision is None:
            # missing decision field → DENY
            return dict(fail_closed, reason="permission classifier missing decision field")
        return {
            "allowed": str(decision) == "allow",
            "level": result.get("level", "R?"),
            "decision": decision,
            "reason": result.get("reason", ""),
            "requires_approval": result.get("requires_approval", True),
        }
    except subprocess.TimeoutExpired:
        return dict(fail_closed, reason="permission classifier timed out")
    except Exception as e:
        # exception → DENY
        return dict(fail_closed, reason="permission classifier unavailable: " + str(e))

# ---------------------------------------------------------------------------
# Execution Plan (文档 §18)
# ---------------------------------------------------------------------------
def build_plan(req, tasks, dag_result=None):
    """生成 execution_plan。

    CHAIN-01：planning_error（非法 DAG edge）是规划完整性错误，不是某个 Task 的执行
    失败——必须硬阻断。当 dag_result.planning_error == true 时，plan.status = PLAN_REJECTED，
    tasks 置空，禁止进入 Permission / Execution（不得「尽量执行剩下的任务」）。
    """
    rejected = bool(dag_result and dag_result.get("planning_error"))
    return {
        "id": generate_id("plan"),
        "objective": req.get("objective", ""),
        "status": "PLAN_REJECTED" if rejected else "PLAN_READY",
        "tasks": [] if rejected else tasks,
        "dag": dag_result,
        "budget": DEFAULT_BUDGET,
        "success_condition": req.get("success_condition", []),
        "planning_error": rejected,
    }


# ---------------------------------------------------------------------------
# Verification (文档 §35 §36) — adapter（ORC-02 收口）
# ---------------------------------------------------------------------------
# Orchestrator 不再自己实现 V0-V4 判定（否则会与 verification-evaluation 形成第二
# Verification Engine）。本函数只做 adapter：结构校验 + 转发到
# verification-evaluation/scripts/verify.py。真正的 success_condition / evidence /
# independent verification / external state / confidence 判定全归 verification-evaluation。
VERIFY_MODULE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "verification-evaluation", "scripts", "verify.py")


def verify_result(result, level="V1"):
    """adapter：转发到 verification-evaluation 的 verify 实现。

    Orchestrator 只做 basic structural validation（result 是否 dict），
    不自己判 V0-V4 / verdict（ORC-02：Verification 不得形成第二引擎）。

    CHAIN-02：验证器自身不可用（timeout / returncode≠0 / 模块缺失 / 异常）返回
    UNAVAILABLE，不是 Task FAIL——任务失败和验证器坏了是两件事，UNAVAILABLE 交给
    Evaluation / Autonomy Decision，不能直接判死（避免「执行成功+验证超时→误判失败」）。
    """
    # basic structural validation：非 dict 直接 FAIL，不进 verify
    if not isinstance(result, dict):
        return {
            "level": level, "verdict": "FAIL", "passed": False,
            "retry_eligible": False, "reason": "result 非 dict（结构校验失败）",
            "checks": [],
        }
    # 转发到 verification-evaluation
    try:
        proc = subprocess.run(
            [sys.executable, VERIFY_MODULE, "--json", json.dumps(result, ensure_ascii=False),
             "--level", level],
            capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            # 子进程异常退出 = 验证器不可用（如 verify.py 自身崩溃），非任务失败
            return {"level": level, "verdict": "UNAVAILABLE", "passed": False,
                    "retry_eligible": False,
                    "reason": "verification-evaluation 调用失败（exit=%s）" % proc.returncode}
        try:
            return json.loads(proc.stdout)
        except Exception:
            return {"level": level, "verdict": "UNAVAILABLE", "passed": False,
                    "retry_eligible": False,
                    "reason": "verification-evaluation 返回非 JSON（输出损坏）"}
    except subprocess.TimeoutExpired:
        # 验证器超时 = 不可用，非任务失败
        return {"level": level, "verdict": "UNAVAILABLE", "passed": False,
                "retry_eligible": False, "reason": "verification-evaluation 超时"}
    except Exception as e:
        # 模块缺失/不可用
        return {"level": level, "verdict": "UNAVAILABLE", "passed": False,
                "retry_eligible": False,
                "reason": "verification-evaluation 不可用: " + str(e)}


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

    p_record = sub.add_parser("record", help="记录执行结果到 Execution Record 并判断 no-progress")
    p_record.add_argument("--json", required=True, help="记录 JSON")

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
        dag = build_dag(tasks, edges)
        # CHAIN-01：planning_error 硬阻断——顶层直接给出 PLAN_REJECTED 信号，
        #   不交付 topological_order 给执行层（避免「输入 DAG ≠ 实际 DAG」）。
        if dag.get("planning_error"):
            dag["blocked"] = True
            dag["block_reason"] = "planning_error: 非法 DAG edge（引用不存在的节点）"
            dag["topological_order"] = []  # 不得交付可执行序列
        print(json.dumps(dag, ensure_ascii=False, indent=2))
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

    if args.cmd == "record":
        # v1.3 修复(P1-1): 统一调用 execution_record 的唯一 Progress Gate，
        #   不再在 Orchestrator 里复制一套并行的 Anti-loop 判断。
        #   Agent → Orchestrator.record → Execution Record.check_action_loop → 唯一决策。
        rec = read_stdin_or_json(args.json, "record")
        er_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "..", "proactive", "scripts", "execution_record.py")

        # 1) 生成 action_signature / result_hash / evidence_hash / input_hash / strategy
        import hashlib as _h
        goal_id = str(rec.get("goal_id", ""))
        task_id = str(rec.get("task_id", ""))
        action_type = str(rec.get("action_type", "unknown"))
        target = str(rec.get("target", ""))
        raw = "|".join([goal_id, task_id, action_type, target])
        action_signature = _h.sha256(raw.encode()).hexdigest()[:12]

        result = rec.get("result", {}) or {}
        clean_result = {k: v for k, v in sorted(result.items())
                        if k not in ("timestamp", "created_at", "updated_at")}
        result_hash = _h.sha256(
            json.dumps(clean_result, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:12]
        evidence_hash = str(rec.get("evidence_hash", ""))
        input_hash = str(rec.get("input_hash", ""))
        strategy = str(rec.get("strategy", ""))

        # 2) 通过 execution_record 的 check 命令走唯一 Progress Gate
        #    (check 内部会 load 历史 + 调 check_action_loop)。
        check_payload = {
            "goal_id": goal_id,
            "task_id": task_id,
            "action_type": action_type,
            "action_signature": action_signature,
            "result_hash": result_hash,
            "evidence_hash": evidence_hash,
            "input_hash": input_hash,
            "strategy": strategy,
            "current_state": str(rec.get("current_state", "")),
            "progress": {
                "new_artifact": rec.get("new_artifact", False),
                "goal_progress": rec.get("goal_progress", False),
                "new_state": rec.get("new_state", False),
            },
        }
        try:
            proc = subprocess.run(
                [sys.executable, er_path, "check", "--json",
                 json.dumps(check_payload, ensure_ascii=False)],
                capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                gate = json.loads(proc.stdout)
            else:
                # 记录层异常 → 不静默 pass：降级为 UNKNOWN，禁止当首次 CONTINUE
                gate = {"decision": "UNKNOWN",
                        "reason": "execution_record check 失败 rc=%s: %s" % (proc.returncode, proc.stderr[:200]),
                        "consecutive_no_progress": 0,
                        "history_unavailable": True}
        except Exception as e:
            gate = {"decision": "UNKNOWN",
                    "reason": "execution_record check 不可用: %s" % str(e),
                    "consecutive_no_progress": 0,
                    "history_unavailable": True}

        decision = gate.get("decision", "UNKNOWN")
        stop_reason = gate.get("reason", "")
        consecutive = gate.get("consecutive_no_progress", 0)

        # 3) 把本次记录（含 gate 结果）追加写入 execution record（append-only, 带锁）。
        record = {
            "goal_id": goal_id,
            "task_id": task_id,
            "action_type": action_type,
            "action_signature": action_signature,
            "result_hash": result_hash,
            "evidence_hash": evidence_hash,
            "input_hash": input_hash,
            "strategy": strategy,
            "previous_state": str(rec.get("previous_state", "")),
            "current_state": str(rec.get("current_state", "")),
            "progress": {
                "new_evidence": bool(rec.get("new_evidence", rec.get("evidence_hash", "") != "")),
                "new_artifact": rec.get("new_artifact", False),
                "new_state": rec.get("new_state", False),
                "goal_progress": rec.get("goal_progress", False),
                "no_progress": consecutive,
            },
            "decision": decision,
            "stop_reason": stop_reason,
        }
        try:
            proc = subprocess.run(
                [sys.executable, er_path, "log", "--json",
                 json.dumps(record, ensure_ascii=False)],
                capture_output=True, text=True, timeout=10)
            # 记录写入失败不应静默 pass：反映到输出 reason
            if proc.returncode != 0:
                stop_reason = (stop_reason + " | log_failed rc=%s" % proc.returncode).strip()
        except Exception as e:
            stop_reason = (stop_reason + " | log_unavailable: %s" % str(e)).strip()

        print(json.dumps({
            "decision": decision,
            "stop_reason": stop_reason,
            "consecutive_no_progress": consecutive,
            "action_signature": action_signature,
            "gate": "execution_record.check_action_loop",
        }, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
