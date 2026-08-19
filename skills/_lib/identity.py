#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
identity.py — Agent OS 统一 Identity / Traceability (C2 / Phase 1 Foundation)

【背景】此前 goal_id/task_id/execution_id/action_id/observation_id/evidence_id/
verification_id 散落在 orchestration / task_manager / self-evolution /
execution_record 各自 dict 里, 缺统一链。导致无法回答冻结方案的核心问题:

    "哪个 Agent, 在哪个 OpenClaw Session 中, 为哪个 Goal 执行哪个 Task,
     进行了哪一次 Execution, 调用了什么 Action, 得到什么 Observation,
     产生什么 Evidence, 谁 Verification, 最后为什么改变状态?"

本模块提供统一 TraceContext —— 一条不可变的可追溯链(reference 链)。各模块
在写 record 时调用 chain 挂载 id, 读取时用 chain 校验完整性。

【链式字段】(冻结方案 Commit 3 / 原则 #5 全部自主执行可追溯到 Goal/Task/Execution)
    goal_id → task_id → execution_id → action_id → observation_id
           → evidence_id → verification_id
    + agent_id / session_id (宿主上下文)

【两种用法】
  1. 挂载链: trace = make_trace(goal_id)=... ; trace.step("task", ...) 逐级补全
  2. 校验链: verify_trace(dict) 返回 {complete, missing, chain}

【Code = Enforcement】
  不信任调用方手填的 id; 用 deterministic_id (SHA256 canonical) 或 generate_id
  生成真实 id, 并校验父链存在。缺父链 → identity 链断裂 → 记 partial。
"""

import os
import sys

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from id_utils import generate_id, deterministic_id
except Exception:  # pragma: no cover
    def generate_id(prefix):
        import uuid
        return "{0}_{1}".format(str(prefix).strip("_"), uuid.uuid4().hex)

    def deterministic_id(prefix, obj):
        import hashlib
        import json
        s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "{0}_{1}".format(str(prefix).strip("_"),
                                hashlib.sha256(s.encode()).hexdigest()[:16])


# 链式字段顺序 (父 → 子)
CHAIN_ORDER = [
    "goal_id", "task_id", "execution_id", "action_id",
    "observation_id", "evidence_id", "verification_id",
]
# 宿主上下文
HOST_IDS = ["agent_id", "session_id"]


class IdentityError(Exception):
    """Identity 链异常 (父链缺失/链条断裂)。"""


def make_trace(prefix="goal", objective=None, seed=None):
    """创建一个新的可追溯链头 (goal_id), 返回带 .step 的 TraceBuilder。
    objective 参与 deterministic id (同目标可复现)。"""
    if seed is not None or objective is not None:
        gid = deterministic_id("goal", {"objective": objective, "seed": seed})
    else:
        gid = generate_id("goal")
    tb = {
        "goal_id": gid,
        "agent_id": "",
        "session_id": "",
        "task_id": "",
        "execution_id": "",
        "action_id": "",
        "observation_id": "",
        "evidence_id": "",
        "verification_id": "",
    }
    return TraceBuilder(tb)


class TraceBuilder(object):
    """链式建造器: .agent(...).session(...).task(...).execution(...).action(...)."""

    def __init__(self, trace):
        self.trace = trace

    def agent(self, agent_id):
        self.trace["agent_id"] = agent_id or ""
        return self

    def session(self, session_id):
        self.trace["session_id"] = session_id or ""
        return self

    def task(self, task_id=None, objective=None):
        if not task_id:
            task_id = deterministic_id("task", {"goal_id": self.trace["goal_id"],
                                                "objective": objective})
        self.trace["task_id"] = task_id
        return self

    def execution(self, execution_id=None, action_type=None, target=None):
        # CRITICAL fix (C-1): 每次执行必须有唯一 id。同 goal/target 的多次执行
        # (重试/幂等) 若用 deterministic hash 会生成相同 execution_id, 两条不同
        # 执行不可区分。execution/action/observation 层是"每次发生的实例",
        # 必须用 UUID; 确定性哈希仅用于可去重层 (goal/task 同目标可复现)。
        if not execution_id:
            execution_id = generate_id("execution")
        self.trace["execution_id"] = execution_id
        return self

    def action(self, action_id=None, action_type=None, target=None):
        if not action_id:
            action_id = generate_id("action")
        self.trace["action_id"] = action_id
        return self

    def observation(self, observation_id=None, obs=None):
        if not observation_id:
            observation_id = generate_id("obs")
        self.trace["observation_id"] = observation_id
        return self

    def evidence(self, evidence_id=None, evidence=None):
        if not evidence_id:
            evidence_id = deterministic_id("evidence", {"observation_id": self.trace["observation_id"],
                                                        "evidence": evidence})
        self.trace["evidence_id"] = evidence_id
        return self

    def verification(self, verification_id=None, verified_by=None, method=None):
        if not verification_id:
            verification_id = deterministic_id("verification",
                                               {"evidence_id": self.trace["evidence_id"],
                                                "verified_by": verified_by, "method": method})
        self.trace["verification_id"] = verification_id
        return self

    def build(self):
        """返回完整 trace dict。"""
        return dict(self.trace)


def attach_trace(record, trace):
    """把 trace 的链字段写入 record。返回 record。

    MAJOR fix (C-2/C-3): 不再"不覆盖"静默接受过期/错误 id —— 若 record 已有子
    id 且与新 trace 对应父 id 不一致, 说明 record 是在更早 goal/task 下写入的,
    是真实断裂。改为检测冲突并落 _identity_conflict, 不静默掩盖。
    """
    conflicts = []
    for k in CHAIN_ORDER + HOST_IDS:
        existing = record.get(k)
        incoming = trace.get(k)
        if existing and incoming and existing != incoming:
            conflicts.append(k)
    if conflicts:
        record["_identity_conflict"] = sorted(
            set(record.get("_identity_conflict", [])) | set(conflicts))
    # 只填缺失字段 (冲突的不覆盖, 但已标记)
    for k in CHAIN_ORDER + HOST_IDS:
        v = trace.get(k)
        if v and not record.get(k):
            record[k] = v
    return record


def verify_trace(trace):
    """校验链完整性。返回 {complete, missing, present, agent_id, session_id}。

    MAJOR fix (C-2/C-3, 空洞检测算法): 区分三种形态, 避免误报/漏报:
      1. 完整链   = 从 goal_id 到末端的连续全链 → complete=True
      2. 短链     = 从某中间层开始的连续片段 (纯计算节点只产 evidence 不持
                   全链) → 允许, complete=False 但 missing=[] (不误报)
      3. 断裂     = 非空字段索引不连续(中间空洞) → 报 missing (不掩盖)

    算法: 对 CHAIN_ORDER 中非空的字段收集索引, 若任意相邻非空索引间有空洞
    (差值>1 且两者之间出现过 CHAIN_ORDER 同层级被跳过), 则该空洞是断裂。
    前缀缺失 (最小非空索引>0) 视为短链, 不算断裂。
    """
    present = [f for f in CHAIN_ORDER if trace.get(f)]
    missing = []
    if present:
        idxs = sorted(CHAIN_ORDER.index(f) for f in present)
        # 断裂 = 非空索引序列内部有空洞 (非连续)
        for a, b in zip(idxs, idxs[1:]):
            if b - a > 1:
                # 空洞出现在 a 和 b 之间, 标记被跳过的层
                skipped = [CHAIN_ORDER[i] for i in range(a + 1, b)]
                missing.extend("%s(被跳过)" % s for s in skipped)
    complete = (len(present) == len(CHAIN_ORDER)) and not missing
    return {
        "complete": complete,
        "missing": sorted(set(missing)),
        "present": present,
        "agent_id": trace.get("agent_id", ""),
        "session_id": trace.get("session_id", ""),
    }


def trace_to_string(trace):
    """人类可读: 哪个 Agent 在哪个 Session 为哪个 Goal 执行哪个 Task 哪次
    Execution 哪个 Action, 得到 Observation, 产生 Evidence, 谁 Verification。"""
    def _s(k):
        v = trace.get(k, "")
        return v or "-"
    out = []
    if _s("agent_id") != "-":
        out.append("Agent=%s" % _s("agent_id"))
    if _s("session_id") != "-":
        out.append("Session=%s" % _s("session_id"))
    out.append("Goal=%s" % _s("goal_id"))
    if _s("task_id") != "-":
        out.append("Task=%s" % _s("task_id"))
    if _s("execution_id") != "-":
        out.append("Execution=%s" % _s("execution_id"))
    if _s("action_id") != "-":
        out.append("Action=%s" % _s("action_id"))
    if _s("observation_id") != "-":
        out.append("Obs=%s" % _s("observation_id"))
    if _s("evidence_id") != "-":
        out.append("Evidence=%s" % _s("evidence_id"))
    if _s("verification_id") != "-":
        out.append("Verify=%s" % _s("verification_id"))
    return " | ".join(out)
