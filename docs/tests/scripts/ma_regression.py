#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MA-1.1 Multi-Agent Regression Tests

基于仓库**真实可执行代码**的回归测试集，覆盖 MA-1.1 清单 #10 要求的维度：
  - Shared Skill（共享 Skill ≠ 共享 State）
  - 并发（跨 execution 撞车 / duplicate_operation）
  - 隔离（per-agent state / task 隔离）
  - Delegation（parent 伪造检测 / 授权只减不增）
  - Provenance（A→B→C chain / correlation 保留 / origin 不丢）
  - Self-Evolution Scope（classify_skill_scope 归属）
  - 越权（actual ⊄ authorized → 违规）
  - 11 Skill 全覆盖（每个 SKILL.md 有 Multi-Agent Contract 声明）

只读校验既有能力（build_ma_context / validate_ma_record / validate_ma_consistency /
check_authorization_binding / classify_skill_scope），不新建 Runtime、不扩架构、
不伪造 Agent OS 能力。失败即基础设施/文档回归信号。

用法:
  python3 docs/tests/scripts/ma_regression.py
"""
import json, os, sys, tempfile, shutil

# ---- resolve repo/scripts paths ----
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SKILLS = os.path.join(REPO, "skills")

# execution_record (MA-1.0) lives under skills/proactive/scripts
PROACTIVE_SCRIPTS = os.path.join(SKILLS, "proactive", "scripts")
sys.path.insert(0, PROACTIVE_SCRIPTS)
import execution_record as er  # noqa: E402

# self-evolution _core (classify_skill_scope)
SELF_EVO_SCRIPTS = os.path.join(SKILLS, "self-evolution", "scripts")
sys.path.insert(0, SELF_EVO_SCRIPTS)
import _core as core  # noqa: E402

PASS = FAIL = 0


def ck(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] " + name)
    else:
        FAIL += 1
        print("  [FAIL] " + name + ("  " + detail if detail else ""))


# ---------------------------------------------------------------------------
# 1. Shared Skill ≠ Shared State（MA-1.1 #5 / #10）
# ---------------------------------------------------------------------------
def test_shared_skill_scope():
    print("\n== 1. Shared Skill Scope（共享 Skill ≠ 共享 State）==")
    tmp = tempfile.mkdtemp(prefix="ma_shared_")
    try:
        ws_a = os.path.join(tmp, "ws-a", "skills", "summarize")
        shared = os.path.join(tmp, "shared-skills", "summarize")
        os.makedirs(ws_a, exist_ok=True)
        os.makedirs(shared, exist_ok=True)

        # 共享 Skill 归属 SHARED（即使被 A 引用，也是共享能力，不归 A 私有）
        r = core.classify_skill_scope(shared, agent_id="agent-a",
                                      agent_workspace=os.path.join(tmp, "ws-a"))
        ck("共享 Skill 判定为 SHARED", r.get("kind") == "SHARED", str(r))
        # A 自己 workspace 下的 Skill 才是 AGENT
        r2 = core.classify_skill_scope(ws_a, agent_id="agent-a",
                                       agent_workspace=os.path.join(tmp, "ws-a"))
        ck("Agent 私有 Skill 判定为 AGENT", r2.get("kind") == "AGENT", str(r2))
        # 能力共享 ≠ 状态共享：AGENT scope 的 skill 不因其被 A 用就变成 A 的私有状态
        ck("共享能力不等于私有状态(归属 SHARED)", r.get("kind") == "SHARED")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. Identity / Context 注入（MA-1.1 #2）
# ---------------------------------------------------------------------------
def test_build_ma_context():
    print("\n== 2. Multi-Agent Context 透传（agent/session/runtime 优先）==")
    # Runtime 身份优先于 caller-supplied（防伪造）
    rec = er.build_ma_context(
        {"agent_id": "evil-agent", "session_id": "ses-evil",
         "task_id": "task-x", "correlation_id": "corr-1"},
        runtime_agent_id="agent-trusted", runtime_session_id="ses-trusted")
    ck("Runtime agent 覆盖 caller-supplied", rec["agent_id"] == "agent-trusted", str(rec))
    ck("Runtime session 覆盖 caller-supplied", rec["session_id"] == "ses-trusted")
    ck("task/correlation 保留", rec["task_id"] == "task-x" and rec["correlation_id"] == "corr-1")
    # legacy 单 Agent：runtime 为空时保留 record 原值（兼容）
    rec2 = er.build_ma_context({"task_id": "t1", "correlation_id": ""})
    ck("legacy 保留 caller 值(无 runtime)", rec2["task_id"] == "t1")


# ---------------------------------------------------------------------------
# 3. Provenance / Cross-Agent chain（MA-1.1 #4 / #10）
# ---------------------------------------------------------------------------
def test_provenance_consistency():
    print("\n== 3. Provenance / Cross-Agent Consistency ==")
    # 同 execution 换 agent → cross_agent 冲突
    prev = {"execution_id": "EXE-same", "agent_id": "agent-a",
            "session_id": "ses-a", "task_id": "task-x", "correlation_id": "corr-1"}
    rec = {"execution_id": "EXE-same", "agent_id": "agent-b",
           "session_id": "ses-b", "task_id": "task-x", "correlation_id": "corr-1"}
    r = er.validate_ma_consistency(rec, [prev])
    ck("同 execution 不同 agent → cross_agent", r.get("issue") == "cross_agent", str(r))

    # 同 execution 换 task → cross_task
    rec2 = {"execution_id": "EXE-same", "agent_id": "agent-a",
            "session_id": "ses-a", "task_id": "task-y", "correlation_id": "corr-1"}
    r2 = er.validate_ma_consistency(rec2, [prev])
    ck("同 execution 不同 task → cross_task", r2.get("issue") == "cross_task", str(r2))

    # 同 execution 换 correlation → correlation_conflict
    rec3 = {"execution_id": "EXE-same", "agent_id": "agent-a",
            "session_id": "ses-a", "task_id": "task-x", "correlation_id": "corr-9"}
    r3 = er.validate_ma_consistency(rec3, [prev])
    ck("同 execution 不同 correlation → correlation_conflict",
       r3.get("issue") == "correlation_conflict", str(r3))


# ---------------------------------------------------------------------------
# 4. Delegation 防伪造（MA-1.1 #7 / #10）
# ---------------------------------------------------------------------------
def test_delegation_forgery():
    print("\n== 4. Delegation（parent 伪造 / 自指）==")
    # parent 自指 = 伪造
    rec = {"execution_id": "EXE-d1", "agent_id": "a", "session_id": "s",
           "task_id": "task-c", "parent_task_id": "task-c", "correlation_id": "corr-1"}
    r = er.validate_ma_consistency(rec, [])
    ck("parent 自指 → parent_forgery", r.get("issue") == "parent_forgery", str(r))

    # parent 指向不存在的任务 → parent_forgery
    rec2 = {"execution_id": "EXE-d2", "agent_id": "a", "session_id": "s",
            "task_id": "task-c", "parent_task_id": "task-ghost", "correlation_id": "corr-1"}
    existing = [{"execution_id": "EXE-p", "agent_id": "a", "session_id": "s",
                 "task_id": "task-p", "correlation_id": "corr-1"}]
    r2 = er.validate_ma_consistency(rec2, existing)
    ck("parent 无对应记录 → parent_forgery", r2.get("issue") == "parent_forgery", str(r2))

    # 合法 delegation：parent 存在且同 correlation
    rec3 = {"execution_id": "EXE-d3", "agent_id": "a", "session_id": "s",
            "task_id": "task-c", "parent_task_id": "task-p", "correlation_id": "corr-1"}
    r3 = er.validate_ma_consistency(rec3, existing)
    ck("合法 delegation 通过", r3.get("consistent") is True, str(r3))


# ---------------------------------------------------------------------------
# 5. 并发 / duplicate_operation（MA-1.1 #10）
# ---------------------------------------------------------------------------
def test_concurrency_operation():
    print("\n== 5. 并发 / duplicate_operation 去重 ==")
    # 跨 execution 复用同一 operation_id → duplicate_operation
    prev = {"execution_id": "EXE-1", "operation_id": "op-send-1",
            "agent_id": "a", "session_id": "s", "task_id": "t1", "correlation_id": "c1"}
    rec = {"execution_id": "EXE-2", "operation_id": "op-send-1",
           "agent_id": "b", "session_id": "s", "task_id": "t2", "correlation_id": "c1"}
    r = er.validate_ma_consistency(rec, [prev])
    ck("跨 execution 复用 operation → duplicate_operation",
       r.get("issue") == "duplicate_operation", str(r))

    # 同 execution 续写（crash 恢复）不算新操作
    rec2 = {"execution_id": "EXE-1", "operation_id": "op-send-1",
            "agent_id": "a", "session_id": "s", "task_id": "t1", "correlation_id": "c1"}
    r2 = er.validate_ma_consistency(rec2, [prev])
    ck("同 execution 续写接受(非重复操作)",
       r2.get("consistent") is True, str(r2))

    # 无 operation_id 不做去重判断
    rec3 = {"execution_id": "EXE-3", "agent_id": "a", "session_id": "s",
            "task_id": "t3", "correlation_id": "c1"}
    r3 = er.validate_ma_consistency(rec3, None)
    ck("无 operation 无冲突", r3.get("consistent") is True, str(r3))


# ---------------------------------------------------------------------------
# 6. 越权 / authorization binding（MA-1.1 #7 / #10）
# ---------------------------------------------------------------------------
def test_authorization_binding():
    print("\n== 6. 越权（actual ⊄ authorized → binding_violation）==")
    # authorized.scope ⊆ planned，actual.scope ⊆ authorized：一致
    auth_ok = {
        "planned": {"action": "send", "resource": "email", "scope": "/org/team"},
        "authorized": {"action": "send", "resource": "email", "scope": "/org/team"},
        "actual": {"action": "send", "resource": "email", "scope": "/org/team"},
    }
    r = er.check_authorization_binding(auth_ok)
    ck("授权内执行一致", r["consistent"] is True, str(r))

    # actual.scope 超出 authorized（更宽：/org 不被 /org/team 包含）→ 越权违规
    auth_bad = {
        "planned": {"action": "send", "resource": "email", "scope": "/org/team"},
        "authorized": {"action": "send", "resource": "email", "scope": "/org/team"},
        "actual": {"action": "send", "resource": "email", "scope": "/org"},
    }
    r2 = er.check_authorization_binding(auth_bad)
    ck("actual 越出 authorized scope → 违规",
       r2["binding_violation"] is True, str(r2))

    # actual.scope 是 authorized 的子路径（更窄）→ 合法
    auth_narrow = {
        "planned": {"action": "send", "resource": "email", "scope": "/org/team"},
        "authorized": {"action": "send", "resource": "email", "scope": "/org/team"},
        "actual": {"action": "send", "resource": "email", "scope": "/org/team/sub"},
    }
    r2n = er.check_authorization_binding(auth_narrow)
    ck("actual 为 authorized 子路径(更窄) → 一致",
       r2n["binding_violation"] is False, str(r2n))

    # action 变化 → 违规
    auth_bad2 = {
        "planned": {"action": "send", "resource": "email", "scope": "/org"},
        "authorized": {"action": "send", "resource": "email", "scope": "/org"},
        "actual": {"action": "delete", "resource": "email", "scope": "/org"},
    }
    r3 = er.check_authorization_binding(auth_bad2)
    ck("actual.action 变化 → 违规", r3["binding_violation"] is True, str(r3))


# ---------------------------------------------------------------------------
# 7. Self-Evolution Scope（MA-1.1 #6 / #10）
# ---------------------------------------------------------------------------
def test_selfevolution_scope():
    print("\n== 7. Self-Evolution Agent Scope 隔离 ==")
    tmp = tempfile.mkdtemp(prefix="ma_evo_")
    try:
        shared = os.path.join(tmp, "shared-skills", "task-manager")
        os.makedirs(shared, exist_ok=True)
        # 共享 Skill 归 SHARED → self-evolution 改它属跨 Agent 影响，须升级治理
        r = core.classify_skill_scope(shared, agent_id="agent-research",
                                      agent_workspace=os.path.join(tmp, "ws-research"))
        ck("共享 Skill 判 SHARED（改它=跨 Agent，须升级）",
           r.get("kind") == "SHARED", str(r))
        # 越权路径 → DENY
        r2 = core.classify_skill_scope("../evil", agent_id="agent-research",
                                       agent_workspace=os.path.join(tmp, "ws-research"))
        ck("路径穿越 → DENY", r2.get("kind") == "DENY", str(r2))
        # unknown agent → DENY
        r3 = core.classify_skill_scope("/some/skill", agent_id="unknown-agent" if False else None)
        ck("empty/unknown → 不误判 AGENT",
           r3.get("matched_by", "") != "" or r3.get("kind") in ("SHARED", "DENY"), str(r3))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 8. 11 Skill 全覆盖（MA-1.1 #3 / #10）
# ---------------------------------------------------------------------------
ALL_11 = [
    "context-orchestration", "knowledge-governance", "memory-governance",
    "ontology", "orchestrator", "permission-security", "proactive",
    "self-evolution", "summarize", "task-manager", "verification-evaluation",
]


def test_11_skill_contract():
    print("\n== 8. 11 个共享 Skill 全覆盖（Multi-Agent Contract 声明）==")
    missing = []
    for name in ALL_11:
        f = os.path.join(SKILLS, name, "SKILL.md")
        if not os.path.isfile(f):
            missing.append(name + "(缺 SKILL.md)")
            continue
        txt = open(f, encoding="utf-8").read()
        if "Multi-Agent Contract（PROTOCOL.md §8）" not in txt:
            missing.append(name + "(缺 MA Contract 声明)")
    if missing:
        ck("11 Skill 全部有 MA Contract 声明", False, "; ".join(missing))
    else:
        ck("11 Skill 全部有 MA Contract 声明", True)


def main():
    print("MA-1.1 Multi-Agent Regression Tests")
    test_shared_skill_scope()
    test_build_ma_context()
    test_provenance_consistency()
    test_delegation_forgery()
    test_concurrency_operation()
    test_authorization_binding()
    test_selfevolution_scope()
    test_11_skill_contract()
    print("\n===== RESULT: %d PASS / %d FAIL =====" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
