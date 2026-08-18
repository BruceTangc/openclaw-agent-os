#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-Evolution v2.1 完整回归测试（隔离 workspace，不碰真实数据）。

覆盖 v2.1 硬化：
  - Evidence-driven Discover（读 Store 自算统计，不信任调用者声称）
  - Apply 真正执行结构化 patch + 越界 REJECT + 失败回滚
  - workspace-relative Snapshot / Rollback（真实文件内容还原）
  - 状态机 / 幂等 / 外因拦截 / 保护目标 / G5 审批门 / Evidence Chain
"""
import json
import os
import subprocess
import sys
import tempfile
import shutil

WS = tempfile.mkdtemp(prefix="evoreg_")
os.environ["OPENCLAW_WORKSPACE"] = WS
os.makedirs(os.path.join(WS, "memory"), exist_ok=True)
SCRIPT = os.path.dirname(os.path.abspath(__file__))

# 测试用目标（隔离，真实文件，带实际内容）
TARGET_SKILL_REL = "skills/quotation/skill.md"
TARGET_SKILL = os.path.join(WS, TARGET_SKILL_REL)
os.makedirs(os.path.dirname(TARGET_SKILL), exist_ok=True)
SKILL_CONTENT = "# Quotation skill\n\n生成报价文件\n\n结束\n"
open(TARGET_SKILL, "w", encoding="utf-8").write(SKILL_CONTENT)

PASS = 0
FAIL = 0
RESULTS = []


def run(args, expect_decision=None, **env):
    global PASS, FAIL
    cmd = [sys.executable] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           cwd=SCRIPT, env={**os.environ, **env})
    except Exception as e:
        FAIL += 1; RESULTS.append("EXC {} -> {}".format(args[0], e)); return None
    out = (r.stdout or "").strip()
    try:
        data = json.loads(out) if out else {}
    except Exception:
        data = {}
    ok = True
    if expect_decision and data.get("decision") != expect_decision:
        ok = False
    if r.returncode != 0 and not expect_decision:
        ok = False
    tag = "PASS" if ok else "FAIL"
    if ok: PASS += 1
    else:
        FAIL += 1
        if r.stderr and r.stderr.strip():
            print("QUICK-STDERR {} -> {}".format(" ".join(args[:2]), r.stderr[-500:]), file=sys.stderr)
    RESULTS.append("{} {} -> {}".format(tag, " ".join(args[:2]), out[:70]))
    return data


def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; RESULTS.append("PASS " + name)
    else: FAIL += 1; RESULTS.append("FAIL " + name)
    return cond


# ---------- 0. 登记 Evidence（前 2 条低于阈值，应 IGNORE）----------
# 隔离：先登记 2 条（1条不达标，2条仍不达标），第 3 条才达到 recurrence>=3 & sessions>=2
for i in range(2):
    run(["discover.py", "--evidence", json.dumps({
        "class": "verification", "scope": "skill", "target": TARGET_SKILL_REL,
        "pattern_key": "missing_artifact_check",
        "problem": "报价单缺 artifact existence verification",
        "session": "session-{}".format(i), "source": "verification",
        "verified": True, "systemic": True, "confidence": 0.85})], "IGNORE")

# ---------- 1. Evidence-driven：第 3 条达到阈值 → CANDIDATE_CREATED（自算统计）----------
D = run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill", "target": TARGET_SKILL_REL,
    "pattern_key": "missing_artifact_check",
    "problem": "第三次记录", "session": "session-2", "source": "verification",
    "verified": True, "systemic": True, "confidence": 0.85})], "CANDIDATE_CREATED")
CAND = D.get("candidate_id")
assert CAND, "no candidate via evidence-driven"
check("evidencedriven_recurrence", D.get("stats", {}).get("recurrence", 0) >= 3)
check("evidencedriven_sessions", D.get("stats", {}).get("sessions", 0) >= 2)

# ---------- 2. Diagnose ----------
D = run(["diagnose.py", "--candidate", CAND, "--root_cause", "workflow_gap",
         "--valid", "--reproducible", "--confidence", "0.8", "--level", "G3",
         "--target", TARGET_SKILL_REL], "DIAGNOSED")
DGN = D.get("diagnosis_id")

# ---------- 3. Propose（结构化 operations）----------
OPS = json.dumps([{"op": "replace", "file": TARGET_SKILL_REL,
                   "anchor": "生成报价文件", "content": "生成报价文件\n\n生成后检查 artifact 是否存在"}])
D = run(["propose.py", "--candidate", CAND, "--diagnosis", DGN, "--scope", "skill",
         "--level", "G3", "--targets", TARGET_SKILL_REL, "--operations", OPS,
         "--change", "文件生成后增加 artifact existence verification",
         "--expected_metric", "verification >= 0.9"], "PROPOSAL_CREATED")
PRP = D.get("proposal_id")

# ---------- 4. Apply：真实执行 patch，文件内容应变化 ----------
before = open(TARGET_SKILL, encoding="utf-8").read()
D = run(["apply.py", "--proposal", PRP, "--approve", "--approver", "main",
         "--reason", "G3 confirmed"], "APPLIED")
CHG = D.get("change_id")
after = open(TARGET_SKILL, encoding="utf-8").read()
check("apply_actually_wrote_file", after != before and "artifact 是否存在" in after)

# ---------- 5. Regression IMPROVED → Promotion ----------
D = run(["regression.py", "--change", CHG, "--result", "IMPROVED",
         "--evidence", '{"verification":"passed"}'], "REGRESSION_RECORDED")
RGR = D.get("regression_id")
check("promotion_on_improved", D.get("promotion") == "PROMOTED")

# ---------- 6. Evidence Chain 可追溯 ----------
D = run(["_core.py", "--chain", RGR], expect_decision=None)
chain = D if isinstance(D, dict) else {}
check("chain_traceability", bool(chain.get("regression") and chain.get("candidate")))

# ---------- 7. 幂等 Discover（同 pattern 已有候选）----------
D = run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill", "target": TARGET_SKILL_REL,
    "pattern_key": "missing_artifact_check", "problem": "又一条",
    "session": "s-x", "verified": True, "systemic": True})], "DEDUP_EXISTING")
check("idempotent_dedup", D and D.get("decision") == "DEDUP_EXISTING")

# ---------- 8. 外因拦截（API 挂）----------
run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill", "target": "api.md",
    "pattern_key": "api_down", "problem": "API 挂", "tags": "api network timeout",
    "session": "s", "verified": False})], "IGNORE")

# ---------- 9. Apply 越界 REJECT：operations 指向 targets 外文件 ----------
C2 = run(["discover.py", "--candidate", json.dumps({
    "scope": "skill", "target": "skills/quotation/other.md",
    "pattern_key": "add_review", "problem": "加 review"})], "CANDIDATE_CREATED").get("candidate_id")
D2 = run(["diagnose.py", "--candidate", C2, "--root_cause", "workflow_gap",
          "--valid", "--reproducible", "--confidence", "0.8", "--level", "G3",
          "--target", "skills/quotation/other.md"], "DIAGNOSED").get("diagnosis_id")
OPS2 = json.dumps([{"op": "replace", "file": "skills/quotation/other.md",
                    "anchor": "x", "content": "y"}])
# 越界：operations file 是 targets 外的文件
OPS_BAD = json.dumps([{"op": "replace", "file": "skills/unrelated.md",
                       "anchor": "x", "content": "y"}])
P2 = run(["propose.py", "--candidate", C2, "--diagnosis", D2, "--scope", "skill",
          "--level", "G3", "--targets", "skills/quotation/other.md",
          "--operations", OPS_BAD, "--change", "越界", "--expected_metric", "x"],
         None)
check("propose_out_of_scope_rejected", P2 and P2.get("decision") == "REJECT")

# ---------- 10. 保护目标：AGENTS.md ----------
C3 = run(["discover.py", "--candidate", json.dumps({
    "scope": "global", "target": "AGENTS.md", "pattern_key": "chg_agents",
    "problem": "改AGENTS"})], "CANDIDATE_CREATED").get("candidate_id")
r = subprocess.run([sys.executable, "diagnose.py", "--candidate", C3,
                    "--root_cause", "instruction_gap", "--valid", "--reproducible",
                    "--confidence", "0.8", "--level", "G5", "--target", "AGENTS.md"],
                   capture_output=True, text=True, cwd=SCRIPT, env={**os.environ})
check("protected_target_reject", "受保护" in (r.stderr + r.stdout))

# ---------- 11. G5 强制人工审批 ----------
C4 = run(["discover.py", "--candidate", json.dumps({
    "scope": "protocol", "target": "docs/PROTOCOL.md", "pattern_key": "fix_protocol",
    "problem": "协议措辞"})], "CANDIDATE_CREATED").get("candidate_id")
D4 = run(["diagnose.py", "--candidate", C4, "--root_cause", "workflow_gap",
          "--valid", "--reproducible", "--confidence", "0.8", "--level", "G5",
          "--target", "docs/PROTOCOL.md"], "DIAGNOSED").get("diagnosis_id")
P4 = run(["propose.py", "--candidate", C4, "--diagnosis", D4, "--scope", "protocol",
          "--level", "G5", "--targets", "docs/PROTOCOL.md",
          "--operations", json.dumps([{"op": "append", "file": "docs/PROTOCOL.md",
                                       "content": "x"}]),
          "--change", "改协议", "--expected_metric", "明确"],
         "PROPOSAL_CREATED").get("proposal_id")
D = run(["apply.py", "--proposal", P4, "--approver", "main", "--reason", "no flag"], "REJECT")
check("g5_human_approve_reject_default", D and "G5" in str(D.get("reason", "")))

# ---------- 12. 失败 → Rollback：真实文件内容还原 ----------
C5 = run(["discover.py", "--candidate", json.dumps({
    "scope": "skill", "target": TARGET_SKILL_REL, "pattern_key": "add_review_step",
    "problem": "加 review 步骤"})], "CANDIDATE_CREATED").get("candidate_id")
D5 = run(["diagnose.py", "--candidate", C5, "--root_cause", "workflow_gap",
          "--valid", "--reproducible", "--confidence", "0.8", "--level", "G3",
          "--target", TARGET_SKILL_REL], "DIAGNOSED").get("diagnosis_id")
P5 = run(["propose.py", "--candidate", C5, "--diagnosis", D5, "--scope", "skill",
          "--level", "G3", "--targets", TARGET_SKILL_REL,
          "--operations", json.dumps([{"op": "append", "file": TARGET_SKILL_REL,
                                       "content": "\n# review step"}]),
          "--change", "加 review 步骤", "--expected_metric", "review done"],
         "PROPOSAL_CREATED").get("proposal_id")
# 记录本次 apply 前的内容（rollback 应恢复到 apply 前一刻的 snapshot，即此内容）
PRE_APPLY = open(TARGET_SKILL, encoding="utf-8").read()
H5 = run(["apply.py", "--proposal", P5, "--approve", "--approver", "main",
          "--reason", "ok"], "APPLIED").get("change_id")
mid = open(TARGET_SKILL, encoding="utf-8").read()
check("apply_wrote_before_rollback", "# review step" in mid)
R5 = run(["regression.py", "--change", H5, "--result", "REGRESSED",
          "--evidence", '{"degraded":true}'], "REGRESSION_RECORDED").get("regression_id")
D = run(["rollback.py", "--change", H5, "--reason", "degraded", "--regression", R5],
        "ROLLED_BACK")
final = open(TARGET_SKILL, encoding="utf-8").read()
check("rollback_end_state", D and D.get("state") == "ROLLED_BACK")
check("rollback_content_restored", final == PRE_APPLY and "# review step" not in final)

# ---------- 13. 非法状态跳转 ----------
import _core
try:
    _core.assert_transition({"status": "CANDIDATE"}, "APPLIED")
    check("illegal_transition", False)
except ValueError:
    check("illegal_transition", True)

shutil.rmtree(WS, ignore_errors=True)
print("\n===== REGRESSION SUMMARY (v2.1) =====")
print("PASS: {}\tFAIL: {}".format(PASS, FAIL))
print("\n".join(RESULTS))
sys.exit(0 if FAIL == 0 else 1)
