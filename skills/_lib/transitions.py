#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1.4 C1 — 统一 State Transition 中央门 (全局强制)

【背景 I-015 / ChatGPT round-3 #1~#3】
此前各状态机 (Task / Proposal / Change / Candidate) 各自持有跳转表 + 直改
obj["status"]=...，导致状态机"部分强制"——仍有入口能绕过合法性校验，"状态机=建议"
而非"状态机=强制约束"。

本模块提供唯一的状态变更入口 transition()，任何状态变化必须经过它：
  1. 查合法跳转表，非法跳转一律 raise (全局强制)
  2. 状态-事实不变量校验 (#3)：进入终态/执行态必须携带对应事实字段
     - COMPLETED → completed_at 必须已设置
     - FAILED    → failed_at  必须已设置
     - RUNNING   → started_at 必须已设置
  3. 记录 transition event (who/when/from/to/reason) 到 obj["history"]
  4. 更新 status + updated_at

【架构边界】
- 本模块不持有 Runtime / Scheduler / Event Bus/新 Memory
- 只收敛"状态如何变"，不改变"状态代表什么"
- kind 覆盖: task / proposal / change / candidate / execution

【用法】
  from transitions import transition, transition_allowed, register_gate
  transition(obj, "COMPLETED", kind="task", actor="orchestrator", reason="...")
  非法跳转/缺失事实字段 → raise ValueError (调用方负责捕获/落盘)

为向后兼容 _core.assert_transition，保留 assert_transition 兼容别名。
"""

import time
from datetime import datetime, timezone


def _utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 每类状态机的合法跳转表 (transition matrix)
#   - 与 _core.py TRANSITIONS/TRANSITIONS_PROPOSAL/TRANSITIONS_CHANGE 对齐
#   - 与 task_manager VALID_TRANSITIONS 对齐
# ---------------------------------------------------------------------------
_GATES = {}

# --- Task (align: task_manager.VALID_TRANSITIONS) ---
_TASK_STATES = [
    "INBOX", "PLANNED", "READY", "RUNNING",
    "WAITING", "BLOCKED", "PAUSED", "RETRYING", "FAILED",
    "COMPLETED", "REVIEW", "ARCHIVED", "CANCELLED",
]
_TASK_TRANSITIONS = {
    "INBOX": {"PLANNED", "READY", "CANCELLED"},
    "PLANNED": {"READY", "INBOX", "CANCELLED"},
    "READY": {"RUNNING", "WAITING", "BLOCKED", "PAUSED", "CANCELLED", "RETRYING"},
    "RUNNING": {"COMPLETED", "WAITING", "BLOCKED", "PAUSED", "RETRYING", "FAILED", "CANCELLED"},
    "WAITING": {"READY", "BLOCKED", "CANCELLED"},
    "BLOCKED": {"READY", "CANCELLED"},
    "PAUSED": {"READY", "CANCELLED"},
    "RETRYING": {"READY", "RUNNING", "FAILED", "CANCELLED"},
    "FAILED": {"READY", "CANCELLED"},
    "COMPLETED": {"REVIEW", "ARCHIVED"},
    "REVIEW": {"ARCHIVED", "READY", "CANCELLED"},
    "ARCHIVED": set(),
    "CANCELLED": set(),
}

# --- Proposal (align: _core.TRANSITIONS_PROPOSAL) ---
_PROPOSAL_TRANSITIONS = {
    "PROPOSED": {"APPROVED", "REJECTED"},
    "APPROVED": {"APPROVED", "APPLIED", "REJECTED"},  # APPROVED→APPROVED idempotent no-op
    "APPLIED": {"MONITORING"},
    "MONITORING": {"VALIDATED", "REGRESSED"},
    "VALIDATED": {"PROMOTED"},
    "REJECTED": set(),
    "PROMOTED": set(),
    "REGRESSED": {"ROLLED_BACK"},
    "ROLLED_BACK": set(),
}

# --- Change (align: _core.TRANSITIONS_CHANGE) ---
_CHANGE_TRANSITIONS = {
    "SNAPSHOTTED": {"APPLYING"},
    "APPLYING": {"APPLIED", "APPLY_FAILED"},
    "APPLIED": {"MONITORING", "ROLLED_BACK"},   # AE-4: 回滚可直接从 APPLIED 走状态机
    "MONITORING": {"VALIDATED", "REGRESSED"},
    "VALIDATED": {"PROMOTED"},
    "APPLY_FAILED": set(),
    "REGRESSED": {"ROLLED_BACK"},
    "ROLLED_BACK": set(),
    "PROMOTED": set(),
}

# --- Candidate (align: _core.TRANSITIONS) ---
_CANDIDATE_TRANSITIONS = {
    "CANDIDATE": {"DIAGNOSED", "REJECTED"},
    "DIAGNOSED": {"PROPOSED", "UNRESOLVED"},
    "PROPOSED": {"APPROVED", "REJECTED"},
    "APPROVED": {"SNAPSHOTTED"},
    "SNAPSHOTTED": {"APPLYING"},
    "APPLYING": {"APPLIED", "APPLY_FAILED"},
    "APPLIED": {"MONITORING"},
    "MONITORING": {"VALIDATED", "REGRESSED"},
    "VALIDATED": {"PROMOTED"},
    "PROMOTED": set(),
    "REJECTED": set(),
    "UNRESOLVED": set(),
    "APPLY_FAILED": set(),
    "REGRESSED": {"ROLLED_BACK"},
    "ROLLED_BACK": set(),
}

# --- Permission (授权记录生命周期; 见冻结方案 #7 执行护栏) ---
# REQUESTED → APPROVED → EXPIRED/REVOKED/CONSUMED；CONSUMED = 一次性授权已用
_PERMISSION_TRANSITIONS = {
    "REQUESTED": {"APPROVED", "REJECTED", "EXPIRED", "REVOKED"},
    "APPROVED": {"CONSUMED", "EXPIRED", "REVOKED"},
    "REJECTED": set(),
    "EXPIRED": set(),
    "REVOKED": set(),
    "CONSUMED": set(),
}


# --- Execution (decision 驱动的轻状态机; 见 C1 #2 状态=事实推导) ---
_EXECUTION_STATES = ["CONTINUE", "WARN", "NOOP", "ESCALATE", "UNKNOWN"]
# Execution 的 decision 由 check_action_loop 推导，不落传统 state 跳转表；
# 这里登记合法集合用以 validate 非法值。

# --- Regression (记录镜像状态; 跟随 change 状态机的结果) ---
_REGRESSION_STATES = ["REGRESSION", "PROMOTED", "REGRESSED"]
_REGRESSION_TRANSITIONS = {
    "REGRESSION": {"PROMOTED", "REGRESSED"},
    "PROMOTED": set(),
    "REGRESSED": set(),
}

_GATES["task"] = (_TASK_STATES, _TASK_TRANSITIONS)
def _all_states(transitions):
    """收集跳转表中出现的全部状态（keys + values 并集）。"""
    out = set()
    for src, dsts in transitions.items():
        out.add(src)
        out.update(dsts)
    return sorted(out)


_GATES["proposal"] = (_all_states(_PROPOSAL_TRANSITIONS), _PROPOSAL_TRANSITIONS)
_GATES["change"] = (_all_states(_CHANGE_TRANSITIONS), _CHANGE_TRANSITIONS)
_GATES["candidate"] = (_all_states(_CANDIDATE_TRANSITIONS), _CANDIDATE_TRANSITIONS)
_GATES["execution"] = (_EXECUTION_STATES, {"_": set()})
_GATES["regression"] = (_REGRESSION_STATES, _REGRESSION_TRANSITIONS)
_GATES["permission"] = (_all_states(_PERMISSION_TRANSITIONS), _PERMISSION_TRANSITIONS)


def register_gate(kind, states, transitions):
    """注册/覆盖某个 kind 的跳转表 (测试/未来扩展用)。"""
    _GATES[kind] = (list(states), dict(transitions))
    return kind


def _gate(kind):
    if kind not in _GATES:
        raise ValueError("未注册的 state machine kind: %r" % (kind,))
    return _GATES[kind]


def valid_states(kind):
    return _gate(kind)[0]


def transition_allowed(src, dst, kind="candidate"):
    """src 是否可合法跳到 dst (src==dst 视为幂等 no-op)。"""
    if src == dst:
        return True
    states, tbl = _gate(kind)
    return dst in tbl.get(src, set())


# --- 状态-事实不变量 (#3) ---
# 进入某状态必须已携带的事实字段。key=目标状态, value=required field list。
_INVARIANTS = {
    "task": {
        "COMPLETED": ["completed_at"],
        "FAILED": ["failed_at"],
        "RUNNING": ["started_at"],
    },
    "proposal": {},
    "change": {},
    "candidate": {},
    "execution": {},
}


def register_invariants(kind, table):
    """为某 kind 注册状态-事实不变量表。"""
    base = dict(_INVARIANTS.get(kind, {}))
    base.update(table)
    _INVARIANTS[kind] = base


def _check_invariants(kind, dst, obj):
    """进入 dst 状态时校验必需事实字段。缺失则 raise ValueError。"""
    inv = _INVARIANTS.get(kind, {}).get(dst)
    if not inv:
        return True
    missing = [f for f in inv if not obj.get(f)]
    if missing:
        raise ValueError(
            "状态不变量违反: %s -> %s 缺少必需事实字段 %s"
            % (kind, dst, missing))


def transition(obj, to, kind="candidate", actor="system", reason="",
               force=False, **extra):
    """统一状态变更门。全局唯一合法入口。

    Args:
        obj: 状态对象 (dict), 须含 "status" 字段。
        to: 目标状态字符串。
        kind: 状态机类型 (task/proposal/change/candidate/execution)。
        actor: 谁发起的转换 (audit)。
        reason: 转换原因 (audit)。
        force: True 时跳过跳转合法性校验 (仅用于建数据迁移/恢复, 正常流程禁止)。
            仍会做事实不变量校验。
        **extra: 附加字段 (如 completed_at=...)，会在转换前写入 obj。
    Returns:
        obj (原地更新后返回)。
    Raises:
        ValueError: 未注册 kind / 非法目标状态 / 非法跳转 / 缺事实字段。
    """
    # 0) 目标状态合法性
    states, _tbl = _gate(kind)
    src = obj.get("status") or states[0]
    if to not in states:
        raise ValueError("非法目标状态 %r (kind=%s, 合法: %s)"
                         % (to, kind, states))

    # 1) 携带 extra 事实字段
    if extra:
        obj.update(extra)

    # 2) 跳转合法性 (幂等 src==dst 放行; force 跳过)
    if not force and not transition_allowed(src, to, kind):
        raise ValueError("非法状态跳转 %s -> %s (%s)" % (src, to, kind))

    # 3) 状态-事实不变量 (#3)
    _check_invariants(kind, to, obj)

    # 4) 记录 transition event (audit trail)
    hist = obj.setdefault("history", [])
    if isinstance(hist, list):
        hist.append({
            "timestamp": _utcnow_iso(),
            "actor": actor,
            "action": "transition",
            "from": src,
            "to": to,
            "reason": reason,
        })

    # 5) 更新状态 + 时间戳
    obj["status"] = to
    obj["updated_at"] = _utcnow_iso()
    return obj


def assert_transition(record, dst, kind="candidate", actor="system", reason=""):
    """_core.assert_transition 的兼容别名——统一收敛到中央门。

    保留原签名 (record, dst, kind)，新增 actor/reason 可选，默认 system。
    原 _core.assert_transition 只做跳转校验 + 更新 status/updated_at；
    本别名额外加事实不变量校验 + audit 事件，语义超集，向后兼容。
    """
    return transition(record, dst, kind=kind, actor=actor, reason=reason)
