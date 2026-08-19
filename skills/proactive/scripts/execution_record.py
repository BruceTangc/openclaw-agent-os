#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Execution Record — Protocol observability layer (V1.0)

Append-only execution record，回答"这次行为是否符合 Agent OS Protocol、从哪来到哪去"。
每条记录记录一次 action 的完整上下文，供 Anti-loop Progress Gate 判断。

用法:
  execution_record.py log --json '<record>'    # 写入一条记录
  execution_record.py check --json '<check>'   # 判断是否 no-progress
  execution_record.py query --goal <goal_id>   # 查询某 goal 的记录
  execution_record.py stats --goal <goal_id>   # 统计某 goal 的进展

不是 runtime，不是 scheduler，不是 skill。只是 append-only 的记录层。
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

# v1.3 Hardening #9: JSONL 文件锁 + append-only
_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "_lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from persistence import append_atomic  # noqa: E402

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "memory")


def _record_path():
    return os.path.join(MEMORY_DIR, "execution_records.jsonl")


def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _hash_str(s):
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def _stable_hash(data):
    """对 dict 做稳定 hash，排除 volatile fields。"""
    clean = {}
    exclude = {"timestamp", "created_at", "updated_at", "execution_id", "cycle_id"}
    for k, v in sorted(data.items()):
        if k in exclude:
            continue
        clean[k] = v
    return hashlib.sha256(
        json.dumps(clean, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def load_records(goal_id=None, limit=100):
    """读取记录，可选按 goal_id 过滤。

    v1.3 #10/#12:
      - 损坏 JSONL 行记录到 corruption/corrupt_lines，不静默跳过。
      - 历史读取失败返回 history_unavailable=True，禁止被当成"首次执行"。
    返回 dict {records, corruption, corrupt_lines, history_unavailable}。
    """
    path = _record_path()
    if not os.path.isfile(path):
        return {"records": [], "corruption": 0, "corrupt_lines": [],
                "history_unavailable": False}
    records = []
    corrupt_lines = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if goal_id and r.get("goal_id") != goal_id:
                        continue
                    records.append(r)
                except Exception:
                    corrupt_lines.append(i)
    except OSError as e:
        # 历史读取失败 → history_unavailable，禁止静默当首次
        return {"records": [], "corruption": 0, "corrupt_lines": [],
                "history_unavailable": True, "error": str(e),
                "goal_id": goal_id}
    return {"records": records[-limit:], "corruption": len(corrupt_lines),
            "corrupt_lines": corrupt_lines, "history_unavailable": False}


def histories_available(goal_id=None):
    """判断该 goal 是否有可用历史 (#12)。"""
    res = load_records(goal_id=goal_id, limit=200)
    if res.get("history_unavailable", False):
        return False
    return len(res.get("records", [])) > 0


def append_record(record):
    """追加一条记录 (v1.3 #9: 文件锁 + append-only)。

    CHAIN-03: 若 record 含 authorization 快照（planned/authorized/actual 三态），
    在写入时执行 binding 一致性校验，违例以 binding_violation 标记。

    CHAIN-03-B: 此处仅“记录与暴露”违规，不负责 Permission Runtime 层面的
    运行时阻断——阻断必须在 Permission/Runtime 边界完成；本层不自我声称阻断。
    违例不阻断追加写入，供上层追溯/安全处置。不造 Permission Runtime。

    MA-1.0 (Integration 层): 补充 Multi-Agent 身份字段默认值 + 完整性校验元数据
    ma_completeness(见 validate_ma_record)。只做创建/透传/持久化, 不参与任何
    Core 判定, 不阻断写入。legacy 单 Agent 记录标记 legacy=True, 保持兼容。
    """
    record.setdefault("execution_id", "EXE-" + _hash_str(
        json.dumps(record, sort_keys=True) + utcnow_iso()))
    record.setdefault("timestamp", utcnow_iso())
    record.setdefault("agent_id", "")
    record.setdefault("session_id", "")
    record.setdefault("operation_id", "")
    record.setdefault("correlation_id", "")
    record.setdefault("parent_task_id", "")
    # MA-1.0: 完整性校验(仅元数据, 不阻断)。供审计追溯"这条结论是谁/哪次/哪个agent产生的"。
    record["ma_completeness"] = validate_ma_record(record)
    if record.get("authorization"):
        binding = check_authorization_binding(record.get("authorization"))
        record["authorization_binding"] = binding
    append_atomic(_record_path(), record)
    return record


# ---------------------------------------------------------------------------
# Action Signature（deterministic，不依赖 LLM）
# ---------------------------------------------------------------------------
def compute_action_signature(goal_id, task_id, action_type, normalized_target):
    """hash(goal_id + task_id + action_type + normalized_target)
    相同输入 → 相同输出，不依赖 timestamp。"""
    raw = "|".join([
        str(goal_id or ""),
        str(task_id or ""),
        str(action_type or ""),
        str(normalized_target or ""),
    ])
    return _hash_str(raw)


# ---------------------------------------------------------------------------
# Authorization Binding（CHAIN-03）
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Scope containment（CHAIN-03-A）
# ---------------------------------------------------------------------------
def _split_scope_path(token):
    """路径/层级式 scope 切分为有序片段，用于前缀包含判断。

    支持形如: /workspace/project-a 、 /org/team/account 、 project-a/sub 、
    write:config:xxx 、 account:123 等。仅接受 str；非字符串返回 None（表示
    无法按层级解析，不能当 [] 用，否则非字符串会误判为相等）。
    """
    if not isinstance(token, str):
        return None
    if not token.strip():
        return []
    t = token.strip()
    # 统一把常见的层级分隔符切成片段；不区分 / \\ . :
    t = t.replace("\\", "/")
    for sep in (":", "."):
        t = t.replace(sep, "/")
    return [seg for seg in t.split("/") if seg]


def _scope_kind(v):
    """判定 scope 值的类型族，用于决定 containment 语义。

    - 'str' / 'scalar'(bool/int/float) / 'unsupported'（dict/list/set/tuple 等
      尚未实现显式 containment 的结构化 scope，以及 None）。
    None 视为 unsupported —— 含 None 的字段本身表示"未提供 scope"，由调用方
    决定；此处不参与类型相等的合并，避免 None 与任意值误判。
    """
    if isinstance(v, str):
        return "str"
    if isinstance(v, bool):
        return "scalar"
    if isinstance(v, (int, float)):
        return "scalar"
    return "unsupported"


def _scope_contains(scope, container):
    """判断 scope ⊆ container（容器包含作用域）。fail-closed：类型不支持时判 False。

    按 scope 类型决定语义：
      - str ↔ str：层级化前缀包含（/a/b/c ⊆ /a/b → True）；
        /a/b 不包含 /a/bc（边界段精确匹配）。
      - scalar ↔ scalar：仅完全相等（_scope_contains(123,123)=True，
        _scope_contains(123,456)=False）。
      - 类型不同 / 任一为 None 或 dict/list/set 等未实现 containment 的结构化
        scope：FAIL CLOSED → False（不因解析成 [] 而误判相等）。

    注意：这里的 containment 是"通用层级/标量"语义，不是 operation-set /
    domain / account 类型的集合 containment；文档不把能力写强于实现。
    """
    sk = _scope_kind(scope)
    ck = _scope_kind(container)

    # 结构化/None 类型：目前未实现显式 containment，回退到“完全相等”且 fail-closed。
    # 结构化 scope（dict/list/set）相同结构且相等 → 视为一致（没越权）；
    # 类型不同或结构不等 → False（越权/不支持一律不通过，绝不因解析成 [] 而放行）。
    if sk == "unsupported" or ck == "unsupported":
        if scope is None or container is None:
            # None 表示未提供 scope，由调用方决定；此处要求两者同为 None 或同值才一致
            return scope is None and container is None
        # 非 None 结构化 scope：仅支持“同类型且逐字段相等”，否则 fail closed
        return type(scope) is type(container) and scope == container

    if sk == "scalar" and ck == "scalar":
        return scope == container

    if sk == "str" and ck == "str":
        s = _split_scope_path(scope)
        c = _split_scope_path(container)
        # str 非空但解析后无片段（如纯分隔符）→ 不能默认放行
        if not s:
            return scope.strip() == container.strip()
        if not c:
            return False
        if s == c:
            return True
        if len(s) < len(c):
            return False
        return s[:len(c)] == c

    # 类型不同（str vs scalar / scalar vs str）→ fail closed
    return False


def check_authorization_binding(authorization):
    """校验 planned_action / authorized_action / actual_runtime_action 三态一致性。

    CHAIN-03：进入 OpenClaw Runtime 前必须保证 authorized_scope 没被 Orchestrator
    replan / Skill parameter / Tool parameter 改变。这里不造 Permission Runtime，
    只在 Execution Record 内做一致性校验；违例仅记录 binding_violation 供上层
    追溯与安全处置，不自行声称负责运行时阻断（阻断在 Permission/Runtime 边界）。

    authorization 结构（可选三态，缺省视为一致）:
      {
        "planned":   {"action": ..., "resource": ..., "scope": ...},
        "authorized":{"action": ..., "resource": ..., "scope": ...},
        "actual":    {"action": ..., "resource": ..., "scope": ...},
      }

    约束（CHAIN-03-A）:
      - authorized.action  == planned.action
      - authorized.resource == planned.resource
      - authorized.scope  ⊆ planned.scope
      - actual.action     == authorized.action
      - actual.resource   == authorized.resource
      - actual.scope      ⊆ authorized.scope

    scope 按类型做包含判断（path / resource-id / operation-set / domain /
    account），对非层级字符串回退到完全相等；不接受简单字符串== 之外
    的默认放行，避免越权通过。

    返回 {consistent: bool, binding_violation: bool, violations: [...]}
    """
    if not isinstance(authorization, dict):
        return {"consistent": True, "binding_violation": False, "violations": []}

    planned = authorization.get("planned") or {}
    authorized = authorization.get("authorized") or {}
    actual = authorization.get("actual") or {}

    violations = []
    # planned vs authorized：authorized action/resource/scope 必须落在 planned 内
    if planned and authorized:
        if authorized.get("action") and planned.get("action") \
                and authorized.get("action") != planned.get("action"):
            violations.append("authorized.action != planned.action")
        if authorized.get("resource") and planned.get("resource") \
                and authorized.get("resource") != planned.get("resource"):
            violations.append("authorized.resource != planned.resource")
        if authorized.get("scope") is not None or planned.get("scope") is not None:
            if not _scope_contains(authorized.get("scope"),
                                   planned.get("scope")):
                violations.append(
                    "authorized.scope not ⊆ planned.scope: %r vs %r"
                    % (authorized.get("scope"), planned.get("scope")))

    # authorized vs actual：actual 不得超出 authorized scope
    if authorized and actual:
        if actual.get("action") and authorized.get("action") \
                and actual.get("action") != authorized.get("action"):
            violations.append("actual.action != authorized.action")
        if actual.get("resource") and authorized.get("resource") \
                and actual.get("resource") != authorized.get("resource"):
            violations.append("actual.resource != authorized.resource")
        if actual.get("scope") is not None or authorized.get("scope") is not None:
            if not _scope_contains(actual.get("scope"),
                                   authorized.get("scope")):
                violations.append(
                    "actual.scope not ⊆ authorized.scope: %r vs %r"
                    % (actual.get("scope"), authorized.get("scope")))

    return {
        "consistent": len(violations) == 0,
        "binding_violation": len(violations) > 0,
        "violations": violations,
    }


# ---------------------------------------------------------------------------
# MA-1.0 Multi-Agent Identity/Correlation（Integration 层, 不改 Core 判定）
# ---------------------------------------------------------------------------
# Multi-Agent 执行身份字段：
#   agent_id        — 哪个 Agent 执行
#   session_id      — 哪个 OpenClaw Session
#   execution_id    — 哪一次执行 (append 时由 Core 自动生成 EXE-*)
#   task_id         — 属于哪个 Task
#   parent_task_id  — 由哪个父 Task 派生 (delegation)
#   operation_id    — 具体副作用操作的幂等身份(有具体 operation/action 则需填)
#   correlation_id  — 整个横向协作链的关联 ID
# legacy 单 Agent 记录允许缺省；Multi-Agent context 由 validate_ma_record 强制完整。
# 这些字段只做创建/透传/持久化 + 完整性校验，不参与 check_action_loop / state /
# permission / verification / DAG / self-evolution 任何 Core 判定。
MA_IDENTITY_FIELDS = ["agent_id", "session_id", "execution_id", "task_id"]
MA_REQUIRED_FIELDS = MA_IDENTITY_FIELDS + ["correlation_id"]


def _is_ma_context(record):
    """判断记录是否处于 Multi-Agent 执行上下文。

    任一关键身份字段提供了非空值即视为 Multi-Agent context：
    agent_id / session_id / correlation_id / parent_task_id 非空即可触发。
    execution_id / task_id 在单 Agent 也会有, 不能作为触发器。
    """
    for f in ("agent_id", "session_id", "correlation_id", "parent_task_id"):
        if str(record.get(f, "") or "").strip():
            return True
    return False


def validate_ma_record(record):
    """Multi-Agent Execution Record 完整性校验（MA-1.0 硬规则）。

    单 Agent legacy 记录：允许缺字段，返回 legacy=True（不强制）。
    Multi-Agent context：必须完整填充 agent_id / session_id / execution_id /
    task_id / correlation_id；operation_id 仅当存在具体操作时要求。

    返回 {valid: bool, ma: bool, missing: [field], legacy: bool}：
      - valid : 是否通过校验
      - ma    : 是否 Multi-Agent context
      - legacy: 是否当作 legacy 单 Agent 记录
    """
    rec = record or {}
    if not _is_ma_context(rec):
        # 单 Agent legacy：不强制, 兼容 v1.3 旧记录
        return {"valid": True, "ma": False, "missing": [], "legacy": True}

    missing = [f for f in MA_REQUIRED_FIELDS if not str(rec.get(f, "") or "").strip()]
    # operation_id: 仅当存在具体 side-effect 操作时要求(由调用方以 has_operation 标记)
    return {
        "valid": len(missing) == 0,
        "ma": True,
        "missing": missing,
        "legacy": False,
    }


def validate_ma_consistency(record, existing=None):
    """Multi-Agent 身份/关联一致性校验（MA-1.0 攻击防守, Integration 层）。

    在 append 前对将要写入的记录做**关联一致性**检查，识别集成攻击：
      - duplicate execution_id：本记录 execution_id 与已存在记录撞车 → 攻击 B/D
      - cross-agent：同 execution_id 却不同 agent_id / session_id → 攻击 A/B
      - cross-task：同 execution_id 却不同 task_id → 攻击 C
      - correlation 合并冲突：同 execution_id 却不同 correlation_id → 攻击 E
      - parent 伪造：同 correlation 链内 parent_task_id 指向不存在的任务 → 攻击 F

    本函数是**审计/防守 hint**（记录与暴露），不替代 Permission/Runtime 阻断
    （对齐 CHAIN-03-B）：返回 consistency 结果，由调用方决定是否写入/拒绝。
    不改任何 Core 判定逻辑。existing 为已持久化的记录列表(可选)；不提供时
    只做本记录内部的字段自洽检查。

    返回 {consistent: bool, issue: str, detail: str}：
      - consistent: 是否有冲突
      - issue     : 冲突类型(code)
      - detail    : 人读描述
    """
    rec = record or {}
    eid = str(rec.get("execution_id", "") or "").strip()
    # 单 Agent legacy 无 execution_id / 无 MA 字段 → 不适用
    if not eid or not _is_ma_context(rec):
        return {"consistent": True, "issue": "", "detail": ""}

    def _field(r, k):
        return str(r.get(k, "") or "").strip()

    # 本记录内部自洽：execution_id 无法自证，但 correlation+task+agent 关系可查历史
    for prev in (existing or []):
        prev_eid = _field(prev, "execution_id")
        if not prev_eid or prev_eid != eid:
            continue
        # 同 execution_id — 检查身份是否一致
        if _field(prev, "agent_id") and _field(rec, "agent_id") \
                and _field(prev, "agent_id") != _field(rec, "agent_id"):
            return {"consistent": False, "issue": "cross_agent",
                    "detail": "execution %s 出现两个 agent: %r vs %r"
                    % (eid, _field(prev, "agent_id"), _field(rec, "agent_id"))}
        if _field(prev, "session_id") and _field(rec, "session_id") \
                and _field(prev, "session_id") != _field(rec, "session_id"):
            return {"consistent": False, "issue": "cross_session",
                    "detail": "execution %s 出现两个 session: %r vs %r"
                    % (eid, _field(prev, "session_id"), _field(rec, "session_id"))}
        if _field(prev, "task_id") and _field(rec, "task_id") \
                and _field(prev, "task_id") != _field(rec, "task_id"):
            return {"consistent": False, "issue": "cross_task",
                    "detail": "execution %s 关联两个 task: %r vs %r"
                    % (eid, _field(prev, "task_id"), _field(rec, "task_id"))}
        if _field(prev, "correlation_id") and _field(rec, "correlation_id") \
                and _field(prev, "correlation_id") != _field(rec, "correlation_id"):
            return {"consistent": False, "issue": "correlation_conflict",
                    "detail": "execution %s 关联两个 correlation: %r vs %r"
                    % (eid, _field(prev, "correlation_id"), _field(rec, "correlation_id"))}
        # 正常：同 execution_id + 同 agent/session/task/correlation = 同一执行续写（含 crash 恢复）
        return {"consistent": True, "issue": "continuation", "detail": ""}

    return {"consistent": True, "issue": "", "detail": ""}


def check_duplicate_execution(execution_id, existing=None):
    """校验 execution_id 是否已存在（重复执行/伪造 execution_id 防守）。

    返回 (exists, prev_rec)。已存在 → 第二个记录若身份不同即异常（由
    validate_ma_consistency 进一步细分）；若完全相同(同一执行续写/恢复)则可接受。
    """
    if not execution_id or not existing:
        return False, None
    for prev in existing:
        if str(prev.get("execution_id", "") or "") == str(execution_id):
            return True, prev
    return False, None


# ---------------------------------------------------------------------------
# Progress Gate（核心 Anti-loop 判断）
# ---------------------------------------------------------------------------
def check_action_loop(current_record, previous_record=None,
                      previous_available=True):
    """判断当前 action 是否构成 no-progress loop。

    v1.3 #11: progress 维度含 result/evidence/state/artifact/goal_progress，
             任一变化即 PROGRESS。
    v1.3 #12: previous_available=False (历史读失败) → UNKNOWN，
             禁止静默当首次执行 CONTINUE。
    v1.3 #13: same action + same input + same evidence + same state + same
             strategy → no-progress counter +1。

    返回 {decision, reason, consecutive_no_progress, [history_unavailable]}。
    decision ∈ CONTINUE | WARN | NOOP | ESCALATE | UNKNOWN
    """
    if not previous_available:
        return {
            "decision": "UNKNOWN",
            "reason": "history_unavailable: 历史读取失败或无法确认",
            "consecutive_no_progress": 0,
            "history_unavailable": True,
        }

    if not previous_record:
        return {
            "decision": "CONTINUE",
            "reason": "首次执行",
            "consecutive_no_progress": 0,
        }

    same_action = (current_record.get("action_signature") ==
                   previous_record.get("action_signature"))
    same_result = (current_record.get("result_hash") ==
                   previous_record.get("result_hash"))
    same_evidence = (current_record.get("evidence_hash") ==
                     previous_record.get("evidence_hash"))
    same_state = (current_record.get("current_state") ==
                  previous_record.get("current_state"))
    same_strategy = (current_record.get("strategy") ==
                     previous_record.get("strategy"))
    same_input = (current_record.get("input_hash") ==
                  previous_record.get("input_hash"))
    # BE-3 (Action→Observation 对应): observation 变化 = 可观测结果变化, 算 progress。
    same_observation = (current_record.get("observation_hash") ==
                        previous_record.get("observation_hash"))

    prev_prog = previous_record.get("progress", {}) or {}
    cur_prog = current_record.get("progress", {}) or {}
    # v1.3 #11: 新维度
    new_artifact = cur_prog.get("new_artifact", False)
    goal_progress = cur_prog.get("goal_progress", False)
    new_state_flag = cur_prog.get("new_state", False)
    same_artifact = (prev_prog.get("new_artifact", False) == new_artifact)
    same_goal_progress = (prev_prog.get("goal_progress", False) == goal_progress)
    # BE-4 (Evidence→Verification 来源链): 验证来源独立变化也算 progress。
    new_independent_verif = (current_record.get("verification", {}) or {}).get(
        "independent_source", False)
    prev_independent_verif = (previous_record.get("verification", {}) or {}).get(
        "independent_source", False)

    if not same_action:
        return {
            "decision": "CONTINUE",
            "reason": "不同 action",
            "consecutive_no_progress": 0,
        }

    # same action — 检查是否有进展 (任一维度变化即 progress)
    has_progress = (
        not same_result or not same_evidence or not same_state
        or not same_strategy or not same_input
        or not same_observation
        or new_artifact or not same_artifact
        or goal_progress or not same_goal_progress
        or new_state_flag
        or new_independent_verif != prev_independent_verif
    )

    if has_progress:
        return {
            "decision": "CONTINUE",
            "reason": "同 action 但有新 result/evidence/state/strategy/"
                      "input/artifact/goal_progress",
            "consecutive_no_progress": 0,
        }

    # same action + 全维度无进展 → no-progress
    prev_count = prev_prog.get("no_progress", 0)
    new_count = prev_count + 1

    # BE-6 (State-loop, L2): 状态振荡检测 — 同 action 下反复在同一状态对
    #   (previous_state→current_state) 之间横跳, 即使每次 action 不同也可判定 stall。
    prev_osc = prev_prog.get("state_oscillation", 0)
    cur_state_pair = (str(previous_record.get("current_state", "")) +
                      "->" + str(current_record.get("current_state", "")))
    prev_state_pair = (prev_prog.get("cycle_signature", ""))
    state_loop = (prev_state_pair == cur_state_pair)
    new_osc = (prev_osc + 1) if state_loop else 0

    # BE-5 (Goal Progress Vector, L3): 用 stall_count 记录无进展轮次, 供上层量化。
    stall_count = prev_prog.get("stall_count", 0) + 1

    if state_loop and new_osc >= 3:
        decision = "ESCALATE"
        reason = "State-loop: 在 %s 间振荡 %d 次无进展" % (cur_state_pair, new_osc)
        new_count = new_osc
    elif new_count >= 3:
        decision = "ESCALATE"
        reason = "连续 %d 次无进展" % new_count
    elif new_count >= 2:
        decision = "NOOP"
        reason = "连续 %d 次无进展" % new_count
    elif state_loop:
        decision = "WARN"
        reason = "State-loop 第 %d 次振荡" % new_osc
        new_count = new_osc
    else:
        decision = "WARN"
        reason = "第 %d 次无进展" % new_count

    return {
        "decision": decision,
        "reason": reason,
        "consecutive_no_progress": new_count,
        "state_oscillation": new_osc,
        "stall_count": stall_count,
        "cycle_signature": cur_state_pair,
    }


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------
def cmd_log(args):
    record = json.loads(args.json) if args.json else {}
    record.setdefault("action_type", "unknown")
    record.setdefault("action_signature", "")
    record.setdefault("result_hash", "")
    record.setdefault("evidence_hash", "")
    record.setdefault("input_hash", "")
    record.setdefault("strategy", "")
    record.setdefault("previous_state", "")
    record.setdefault("current_state", "")
    record.setdefault("goal_id", "")
    record.setdefault("task_id", "")
    record.setdefault("cycle_id", "")
    record.setdefault("parent_task_id", "")
    # MA-1.0 (Multi-Agent Integration v1): Agent 身份与横向协作关联字段。
    #   agent_id        — 哪个 Agent 执行
    #   session_id      — 哪个 OpenClaw Session
    #   execution_id    — 哪一次执行 (append 时自动生成 EXE-*)
    #   operation_id    — 具体副作用操作的幂等身份(有则填)
    #   correlation_id  — 整个横向协作链的关联 ID
    # legacy 记录允许缺省(空), Multi-Agent context 由 validate_ma_record 强制完整。
    record.setdefault("agent_id", "")
    record.setdefault("session_id", "")
    record.setdefault("operation_id", "")
    record.setdefault("correlation_id", "")
    record.setdefault("attempt", 1)
    record.setdefault("retry_count", 0)
    # BE-3 (Action→Observation 对应): observation 记录动作的可观测结果。
    record.setdefault("observation", "")
    record.setdefault("observation_hash", "")
    # BE-4 (Evidence→Verification 来源链): verification 元数据(方法/来源/独立性)。
    record.setdefault("verification", {
        "method": "", "evidence_ref": "", "independent_source": False,
    })
    record.setdefault("progress", {
        "new_evidence": False,
        "new_artifact": False,
        "new_state": False,
        "goal_progress": False,
        "no_progress": 0,
        # BE-5 (Goal Progress Vector, L3): 更细的进展向量。
        "stall_count": 0,
        "cycle_signature": "",
        "last_progress_at": "",
        "progress_count": 0,
        # BE-6 (State-loop, L2): 状态振荡检测计数。
        "state_oscillation": 0,
    })
    record.setdefault("decision", "CONTINUE")
    record.setdefault("stop_reason", "")

    result = append_record(record)
    print(json.dumps({"logged": True, "execution_id": result["execution_id"]},
                     ensure_ascii=False))


def cmd_check(args):
    """判断当前 record 是否构成 no-progress loop。"""
    check = json.loads(args.json) if args.json else {}
    goal_id = check.get("goal_id", "")
    action_signature = check.get("action_signature", "")

    res = load_records(goal_id=goal_id, limit=50)
    if res.get("history_unavailable", False):
        result = check_action_loop(check, None, previous_available=False)
        print(json.dumps(result, ensure_ascii=False))
        return

    prev = None
    for r in reversed(res.get("records", [])):
        if r.get("action_signature") == action_signature:
            prev = r
            break

    result = check_action_loop(check, prev)
    if res.get("corruption", 0) > 0:
        result["corruption_warning"] = res.get("corruption")
    print(json.dumps(result, ensure_ascii=False))


def cmd_query(args):
    res = load_records(goal_id=args.goal, limit=int(args.limit or 50))
    out = {"records": res.get("records", []),
           "total": len(res.get("records", [])),
           "corruption": res.get("corruption", 0),
           "history_unavailable": res.get("history_unavailable", False)}
    print(json.dumps(out, ensure_ascii=False))


def cmd_stats(args):
    res = load_records(goal_id=args.goal, limit=200)
    records = res.get("records", [])
    if not records:
        print(json.dumps({
            "total": 0, "no_progress_runs": 0, "escalated": False,
            "history_unavailable": res.get("history_unavailable", False),
            "unverified": True,
        }, ensure_ascii=False))
        return

    no_progress = sum(1 for r in records
                      if r.get("progress", {}).get("no_progress", 0) > 0)
    escalated = any(r.get("decision") == "ESCALATE" for r in records)
    unknown = any(r.get("decision") == "UNKNOWN" for r in records)
    last_progress = max((r.get("progress", {}).get("no_progress", 0)
                         for r in records), default=0)

    print(json.dumps({
        "total": len(records),
        "no_progress_runs": no_progress,
        "last_no_progress": last_progress,
        "escalated": escalated,
        "unknown": unknown,
        "corruption": res.get("corruption", 0),
        "goal_ids": list(set(r.get("goal_id") for r in records if r.get("goal_id"))),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Execution Record (V1.0)")
    sub = parser.add_subparsers(dest="cmd")

    p_log = sub.add_parser("log", help="写入一条记录")
    p_log.add_argument("--json", required=True, help="记录 JSON")

    p_check = sub.add_parser("check", help="判断是否 no-progress loop")
    p_check.add_argument("--json", required=True, help="当前 record JSON")

    p_query = sub.add_parser("query", help="查询记录")
    p_query.add_argument("--goal", help="按 goal_id 过滤")
    p_query.add_argument("--limit", default="50")

    p_stats = sub.add_parser("stats", help="统计进展")
    p_stats.add_argument("--goal", help="按 goal_id 过滤")

    args = parser.parse_args()
    if args.cmd is None:
        parser.print_help()
        return

    handlers = {"log": cmd_log, "check": cmd_check,
                "query": cmd_query, "stats": cmd_stats}
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
