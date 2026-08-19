#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proactive Agent 纯逻辑层 (V1.0)

OpenClaw 主动智能中枢的可运行核心。实现文档【Proactive Agent v1.0】中
可以被确定性落地的部分，供上层(Agent/LLM)作为决策辅助调用：

  --signal       摄入一个 Signal (JSON)，做 Cheap Filter + 基础评分
  --score        对已有 Opportunity/Risk 做优先级计算 (0-100)
  --decision     基于 score 输出 IGNORE/OBSERVE/QUEUE/SUGGEST/PREPARE/EXECUTE/ASK/ESCALATE
  --queue        维护 Proactive Queue (list/add/update/done/dismiss)
  --state        读写 Proactive State (attention budget / cooldown / metrics)
  --noop         NO_ACTION 标记 (合法空白结果)

它不执行具体业务，只做"是否值得行动 + 优先级 + 建议动作"的判断与状态机。

与现有系统的边界:
  - ontology      → --state 可引用; 本文不直接读写, 由上层调 ontology.py
  - self-evol     → --signal type=failure 会生成 evolution_candidate 结构
  - summarize     → 信息压缩由上层调 summarize.py
  - agent-browser → 浏览搜索由上层调 openclaw browser
  - social-search → 社媒由上层调 social_search.py
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
DEFAULT_PRIORITY = 50

# 决策阈值 (对应文档 §11)
THRESHOLDS = {
    "ignore": 20,
    "observe": 40,
    "queue": 60,
    "suggest": 75,
    "prepare": 90,
    "execute_high": 100,
}

# 打扰预算 (文档 §13)
ATTENTION_BUDGET = {
    "critical_limit": None,       # 无限
    "important_limit": 3,
    "recommendation_limit": 5,
    "low_priority_limit": 0,
}

# 冷却时间 (文档 §14) 单位秒
COOLDOWNS = {
    "critical": 15 * 60,
    "important": 6 * 3600,
    "recommendation": 24 * 3600,
    "low": 72 * 3600,
}

# 风险类型 (文档 §8)
RISK_TYPES = [
    "system_risk", "financial_risk", "security_risk", "privacy_risk",
    "operational_risk", "reputation_risk", "deadline_risk",
    "data_quality_risk", "goal_risk", "automation_risk",
]

# 需要 ASK 的动作 (文档 §17)
ASK_ACTIONS = {
    "转账", "下单", "买卖资产", "对外发送重要消息", "删除重要数据",
    "修改权限", "修改生产系统", "发布公开内容", "重大承诺", "不可逆高风险",
}

# 决策输出 (文档 §16)
DECISIONS = ["IGNORE", "OBSERVE", "QUEUE", "SUGGEST", "PREPARE", "EXECUTE", "ASK", "ESCALATE"]


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default):
    if not os.path.isfile(path):
        return default
    # AE-5 (I-008): 损坏状态(CORRUPTED) ≠ 空状态(NOT_FOUND)。文件存在但无法解析 → 抛错，
    # 让调用方 (如 _atomic_mutate_*) 在锁内回滚不写盘，避免 corrupt→default→overwrite 静默丢数据。
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError("CORRUPTED: {} 无法解析 ({}), 拒绝当作空状态".format(path, e))
    return data


def save_json(path, data):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_stdin_or_json(raw, label):
    """入参可以是 JSON 字符串或 - (从 stdin 读)."""
    if raw == "-":
        return json.load(sys.stdin)
    if raw is None:
        return {}
    try:
        return json.loads(raw)
    except Exception as e:
        return {"__error": f"{label}不是合法JSON: {e}", "_raw": raw}


# ---------------------------------------------------------------------------
# Signal 模型 (文档 §4)
# ---------------------------------------------------------------------------
SIGNAL_TYPES = ["change", "anomaly", "deadline", "opportunity", "risk",
                "goal_drift", "followup", "failure"]

# v1.3 Hardening B2: 统一 ID helper
_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "_lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from id_utils import generate_id, deterministic_id
from persistence import atomic_write_json
from persistence import FileLock

import hashlib as _hashlib


def _signal_fingerprint(sig):
    """稳定 fingerprint: hash(type + subject + source)，不使用 timestamp。"""
    if isinstance(sig, str):
        return sig
    raw = "|".join([str(sig.get("type", "")),
                     str(sig.get("subject", "")),
                     str(sig.get("source", ""))])
    return _hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def ingest_signal(sig):
    """摄入 Signal, 做结构校验 + 默认值补齐."""
    now = utcnow_iso()
    out = dict(sig)
    out.setdefault("id", generate_id("signal"))
    out["fingerprint"] = _signal_fingerprint(out)
    out.setdefault("timestamp", now)
    out.setdefault("source", "system")
    out.setdefault("type", "change")
    out.setdefault("subject", "untitled")
    out.setdefault("summary", "")
    out.setdefault("evidence", [])
    # 归一化证据为列表
    if not isinstance(out["evidence"], list):
        out["evidence"] = [out["evidence"]]
    out.setdefault("confidence", 0.0)   # 0-1
    out.setdefault("freshness", 0.0)    # 0-1
    out.setdefault("novelty", 0.0)      # 0-1
    for k in ("confidence", "freshness", "novelty"):
        try:
            out[k] = float(out[k])
        except (TypeError, ValueError):
            out[k] = 0.0
    if out["type"] not in SIGNAL_TYPES:
        out["_type_unknown"] = out["type"]
        out["type"] = "change"
    return out


def cheap_filter(sig):
    """
    文档 §5: 深度分析前的低成本过滤.
    返回 (action, reason_list)
    action ∈ {pass, ignore}
    """
    reasons = []
    # 无行动空间
    if sig.get("no_action_possible"):
        reasons.append("no_action_possible=true")
    # 已处理/过期 (上层可注入 handled_at / expired 标记)
    if sig.get("handled"):
        reasons.append("已处理")
    if sig.get("expired"):
        reasons.append("已过期")
    # 低价值 + 低新颖 + 无行动空间 → ignore
    try:
        low_val = float(sig.get("value", 0.0)) < 0.25
    except (TypeError, ValueError):
        low_val = True
    if (sig.get("novelty", 0) < 0.3 and low_val
            and sig.get("no_action_possible")):
        reasons.append("低价值+低新颖+无行动空间")
    if reasons:
        return "ignore", reasons
    return "pass", reasons


# ---------------------------------------------------------------------------
# Opportunity / Risk (文档 §7 §8)
# ---------------------------------------------------------------------------
def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_opportunity(sig, **overrides):
    opp = {
        "id": generate_id("opportunity"),
        "title": sig.get("subject", "opportunity"),
        "source_signal": sig.get("id"),
        "source_signal_fingerprint": sig.get("fingerprint") or _signal_fingerprint(sig),
        # 从 signal 继承评分字段 (value/urgency/effort/risk 等), 避免被覆盖成 0
        "value": _f(sig.get("value")),
        "urgency": _f(sig.get("urgency")),
        "confidence": _f(sig.get("confidence")),
        "novelty": _f(sig.get("novelty")),
        "effort": _f(sig.get("effort")),
        "risk": _f(sig.get("risk")),
        "interruption_cost": _f(sig.get("interruption_cost")),
        "goal_alignment": _f(sig.get("goal_alignment"), 0.5),
        "actionable": sig.get("actionable", True),
        "no_action_possible": sig.get("no_action_possible", False),
        "reason": sig.get("evidence", []),
        "recommended_action": sig.get("recommended_action") or {"type": "monitor", "target_skill": None},
        "expires_at": sig.get("expires_at"),
    }
    for k, v in overrides.items():
        if k in opp or k in ("title", "recommended_action"):
            opp[k] = v
    return opp


# ---------------------------------------------------------------------------
# 优先级计算 (文档 §11)
# ---------------------------------------------------------------------------
def priority_score(opp):
    """计算 0-100 优先级 (加权和 + 风险/代价惩罚, 避免除法爆表)."""
    v = _f(opp.get("value"))
    u = _f(opp.get("urgency"))
    c = _f(opp.get("confidence"))
    n = _f(opp.get("novelty"))
    ga = _f(opp.get("goal_alignment"), 0.5)
    e = _f(opp.get("effort"))
    r = _f(opp.get("risk"))
    i = _f(opp.get("interruption_cost"))
    actionable = opp.get("actionable", True)

    # 价值基础分 (权重: 价值35 紧急20 置信15 新颖10 目标对齐20；价值单调递增)
    base = v * 35.0 \
         + u * 20.0 \
         + c * 15.0 \
         + n * 10.0 \
         + ga * 20.0

    # 代价/风险惩罚 (0~35分)
    penalty = (e * 0.5 + r * 0.8 + i * 0.3) * 35.0

    score = base - penalty

    # 不可行动 → 强制压低
    if not actionable:
        score *= 0.1
    # 明确无行动空间 → IGNORE 区间
    if opp.get("no_action_possible"):
        score *= 0.1

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# 决策 (文档 §16)
# ---------------------------------------------------------------------------
def decide(score, risk_type=None, has_ask_flag=False, failure_count=0):
    """基于 score + 风险门 输出决策.

    - failure_count >= 3 (连续失败) 且 score 中高 → ESCALATE (文档 §40 §26)
    - 风险类型 + 中高优先级 → ASK (文档 §8 风险优先)
    - 普通路径按分数分档
    """
    # 连续失败 → 升级 (文档 §40: 同类任务连续失败3次 → ESCALATE)
    if failure_count >= 3:
        if score >= 40:
            return "ESCALATE"
        return "QUEUE"  # 失败但低价值, 排队观察
    # 风险门: 任何风险类型都不得随意 EXECUTE (文档 §8 风险优先)
    if risk_type and score >= 40:
        return "ASK"
    if has_ask_flag:
        return "ASK" if score >= 40 else "OBSERVE"
    if score >= THRESHOLDS["prepare"]:
        return "EXECUTE"
    if score >= THRESHOLDS["suggest"]:
        return "PREPARE"
    if score >= THRESHOLDS["queue"]:
        return "SUGGEST"
    if score >= THRESHOLDS["observe"]:
        return "QUEUE"
    if score >= THRESHOLDS["ignore"]:
        return "OBSERVE"
    return "IGNORE"


# ---------------------------------------------------------------------------
# Queue (文档 §15)
# ---------------------------------------------------------------------------
QUEUE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "memory", "queue.json")


def _load_queue():
    return load_json(QUEUE_PATH, [])


def _save_queue(q):
    # v1.3 #7: atomic write (lock + reload + temp + fsync + replace)
    atomic_write_json(QUEUE_PATH, q)


def _atomic_mutate_queue(mutator):
    """P1-2/修复: Queue 的 read→modify→write 放进同一 FileLock 事务。
    mutator(q) 返回 (new_q, result)；异常则锁内回滚不写盘。"""
    with FileLock(QUEUE_PATH):
        q = _load_queue()
        new_q, result = mutator(q)
        _save_queue(new_q)
        return result


def _save_state(st, path=None):
    # v1.3 #8: State 并发写入 atomic
    atomic_write_json(path or STATE_PATH, st)


def _atomic_mutate_state(mutator, path=None):
    """P1-2/修复: State 的 read→modify→write 放进同一 FileLock 事务。
    mutator(st) 返回 (new_st, result)；异常则锁内回滚不写盘。
    path 可选(MA-1.0 per-agent state)；默认 STATE_PATH。"""
    p = path or STATE_PATH
    with FileLock(p):
        st = load_json(p, _default_state())
        new_st, result = mutator(st)
        _save_state(new_st, p)
        return result


def queue_cmd(sub, args):
    now = utcnow_iso()
    if sub == "list":
        q = _load_queue()
        return q
    if sub == "add":
        item = {
            "id": generate_id("queue"),
            "type": args.type or "opportunity",
            "priority": args.priority or DEFAULT_PRIORITY,
            "status": "queued",
            "title": args.title or "untitled",
            "created_at": now,
            "next_review_at": args.review_at or now,
            "owner": "proactive",
        }

        def _add(q):
            q.append(item)
            return q, item

        # P1-2: read→modify→save 同一锁事务
        return _atomic_mutate_queue(_add)
    if sub in ("update", "done", "dismiss"):
        target_id = args.id

        def _mut(q):
            for it in q:
                if it["id"] == target_id:
                    if sub == "update":
                        if args.status:
                            it["status"] = args.status
                        if args.priority:
                            it["priority"] = args.priority
                        it["updated_at"] = now
                    else:
                        it["status"] = "done" if sub == "done" else "dismissed"
                        it["updated_at"] = now
                    return q, it
            return q, None

        res = _atomic_mutate_queue(_mut)
        if res is None:
            return {"error": "queue item %s 不存在" % target_id}
        return res
    return {"error": "未知子命令 %s" % sub}


# ---------------------------------------------------------------------------
# State (文档 §43)
# ---------------------------------------------------------------------------
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "memory", "state.json")


def _state_path(agent_id=None):
    """MA-1.0 (规格 14.1 Agent-local State): 有 agent_id 时用 per-agent 状态文件，
    避免多 Agent 共享同一 proactive 状态相互污染；无 agent_id 时用默认全局 state.json。"""
    if agent_id:
        base = os.path.dirname(STATE_PATH)
        return os.path.join(base, "state-%s.json" % str(agent_id))
    return STATE_PATH


def _default_state():
    return {
        "last_wake_at": None,
        "attention": {"important_used": 0, "recommendation_used": 0},
        "queues": {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "p4": 0},
        "metrics": {
            "signals_today": 0, "opportunities_today": 0,
            "actions_today": 0, "successful_actions_today": 0,
            "rejected_today": 0, "false_positive_today": 0,
        },
        "current_goal": {"id": None, "alignment": 0.0},
        "active_plan": None,
        # v1.3 Anti-loop: action-level loop detection state
        "anti_loop": {
            "last_action_signature": "",
            "last_action_at": "",
            "last_result_hash": "",
            "cooldown_until": "",
            "consecutive_no_progress": 0,
            "last_decision": "",
            "last_stop_reason": "",
        },
    }


def state_cmd(sub, args):
    now = utcnow_iso()
    # MA-1.0 (规格 14.1): per-agent state 隔离
    sp = _state_path(getattr(args, "agent", None))
    if sub == "show":
        return load_json(sp, _default_state())
    if sub == "wake":
        # v1.3 Anti-loop: wake cooldown check (default 60s)
        WAKE_COOLDOWN_SEC = 60

        def _wake(st):
            last_wake = st.get("last_wake_at", "")
            cooldown_until = st.get("anti_loop", {}).get("cooldown_until", "")
            if cooldown_until and now < cooldown_until:
                return st, {"wake": "no_action", "reason": "cooldown",
                            "cooldown_until": cooldown_until}
            if last_wake:
                try:
                    from datetime import datetime as dt
                    last_dt = dt.fromisoformat(last_wake.replace("Z", "+00:00"))
                    now_dt = dt.fromisoformat(now.replace("Z", "+00:00"))
                    elapsed = (now_dt - last_dt).total_seconds()
                    if elapsed < WAKE_COOLDOWN_SEC:
                        cd = (last_dt.timestamp() + WAKE_COOLDOWN_SEC)
                        from datetime import datetime as dt2, timezone as tz
                        cd_iso = dt2.fromtimestamp(cd, tz=tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        st.setdefault("anti_loop", {})["cooldown_until"] = cd_iso
                        return st, {"wake": "no_action", "reason": "cooldown",
                                    "cooldown_until": cd_iso}
                except Exception:
                    pass
            st["last_wake_at"] = now
            st["metrics"]["signals_today"] = st["metrics"].get("signals_today", 0) + 1
            st.setdefault("anti_loop", {})["cooldown_until"] = ""
            return st, {"wake": "ok", "last_wake_at": now}

        # P1-2: read→modify→save 同一锁事务
        return _atomic_mutate_state(_wake, sp)
    if sub == "bump":
        # 计数一个指标
        key = args.key

        def _bump(st):
            if key in st["metrics"]:
                if args.delta:
                    st["metrics"][key] += args.delta
                else:
                    st["metrics"][key] = st["metrics"].get(key, 0) + 1
                return st, {"metrics": st["metrics"]}
            return st, None

        res = _atomic_mutate_state(_bump, sp)
        if res is None:
            return {"error": "未知指标 %s" % key}
        return res
    if sub == "set-goal":
        def _go(st):
            st["current_goal"] = {"id": args.goal, "alignment": args.alignment or 0.0}
            return st, st["current_goal"]
        return _atomic_mutate_state(_go, sp)
    return {"error": "未知子命令 %s" % sub}


# ---------------------------------------------------------------------------
# Evolution Candidate (文档 §26)
# ---------------------------------------------------------------------------
def evolution_candidate(problem, evidence, frequency, impact, proposed_change,
                        confidence, requires_approval=True):
    return {
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
    parser = argparse.ArgumentParser(description="Proactive Agent 纯逻辑层")
    sub = parser.add_subparsers(dest="cmd")

    p_ingest = sub.add_parser("signal", help="摄入 Signal")
    p_ingest.add_argument("--json", help="Signal JSON 或 -")
    p_ingest.add_argument("--raw", nargs="*", help="直接传字段 key=value")

    p_score = sub.add_parser("score", help="计算优先级")
    p_score.add_argument("--json", help="Opportunity JSON 或 -")

    p_decision = sub.add_parser("decision", help="输出决策")
    p_decision.add_argument("--json", help="Opportunity JSON 或 -")
    p_decision.add_argument("--score", type=float, default=None)
    p_decision.add_argument("--risk-type", default=None)

    p_filter = sub.add_parser("filter", help="Cheap Filter 测试")
    p_filter.add_argument("--json", help="Signal JSON 或 -")

    p_queue = sub.add_parser("queue", help="维护 Queue")
    p_queue.add_argument("--op", choices=["list", "add", "update", "done", "dismiss"],
                         default="list")
    p_queue.add_argument("--id")
    p_queue.add_argument("--type")
    p_queue.add_argument("--title")
    p_queue.add_argument("--priority", type=int)
    p_queue.add_argument("--status")
    p_queue.add_argument("--review-at")

    p_state = sub.add_parser("state", help="Proactive State")
    p_state.add_argument("--op", choices=["show", "wake", "bump", "set-goal"],
                         default="show")
    p_state.add_argument("--key")
    p_state.add_argument("--delta", type=int)
    p_state.add_argument("--goal")
    p_state.add_argument("--alignment", type=float)
    p_state.add_argument("--agent", default="", help="MA-1.0: per-agent state 隔离")

    p_evol = sub.add_parser("evol", help="生成 Evolution Candidate")
    p_evol.add_argument("--problem", required=True)
    p_evol.add_argument("--evidence", nargs="*", default=[])
    p_evol.add_argument("--frequency", type=int, default=1)
    p_evol.add_argument("--impact", type=float, default=0.0)
    p_evol.add_argument("--change", required=True)
    p_evol.add_argument("--confidence", type=float, default=0.0)
    p_evol.add_argument("--no-approval", action="store_true")

    sub.add_parser("noop", help="NO_ACTION 标记")

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        return

    if args.cmd == "signal":
        sig = read_stdin_or_json(args.json, "signal")
        sig = ingest_signal(sig)
        action, reasons = cheap_filter(sig)
        res = {"signal": sig, "filter": action, "reasons": reasons}
        if action == "pass":
            opp = build_opportunity(sig)
            res["opportunity"] = opp
            res["priority"] = priority_score(opp)
            # failure 类型: 用 evidence 数量 + 显式 failure_count 判断连续失败
            fc = 0
            if sig.get("type") == "failure":
                fc = int(sig.get("failure_count", 0) or 0)
                if fc <= 0:
                    fc = len(sig.get("evidence", []))
            res["decision"] = decide(res["priority"],
                                     risk_type=sig.get("risk_type"),
                                     has_ask_flag=sig.get("has_ask_flag", False),
                                     failure_count=fc)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.cmd == "score":
        opp = read_stdin_or_json(args.json, "opportunity")
        print(json.dumps({"priority": priority_score(opp)}, ensure_ascii=False))
        return

    if args.cmd == "decision":
        if args.score is not None:
            s = args.score
        else:
            opp = read_stdin_or_json(args.json, "opportunity")
            s = priority_score(opp)
        d = decide(s, risk_type=args.risk_type)
        print(json.dumps({"score": s, "decision": d}, ensure_ascii=False))
        return

    if args.cmd == "filter":
        sig = read_stdin_or_json(args.json, "signal")
        sig = ingest_signal(sig)
        action, reasons = cheap_filter(sig)
        print(json.dumps({"action": action, "reasons": reasons}, ensure_ascii=False))
        return

    if args.cmd == "queue":
        print(json.dumps(queue_cmd(args.op, args), ensure_ascii=False))
        return

    if args.cmd == "state":
        print(json.dumps(state_cmd(args.op, args), ensure_ascii=False))
        return

    if args.cmd == "evol":
        cand = evolution_candidate(
            args.problem, args.evidence, args.frequency, args.impact,
            args.change, args.confidence, requires_approval=not args.no_approval)
        print(json.dumps(cand, ensure_ascii=False, indent=2))
        return

    if args.cmd == "noop":
        print("NO_ACTION")
        return


if __name__ == "__main__":
    main()
