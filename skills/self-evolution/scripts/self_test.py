#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-Evolution v2 完整回归测试（隔离 workspace，不碰真实数据）。"""
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

# 测试用目标（隔离，不碰真实文件）
TARGET_SKILL = os.path.join(WS, "evotest-proj", "quotation", "skill.md")
TARGET_TOOL = os.path.join(WS, "evotest-proj", "tool.sh")
os.makedirs(os.path.dirname(TARGET_SKILL), exist_ok=True)
open(TARGET_SKILL, "w").close()
open(TARGET_TOOL, "w").close()

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
    else: FAIL += 1
    RESULTS.append("{} {} -> {}".format(tag, " ".join(args[:2]), out[:80]))
    return data


# ---------- 1. 成功晋升路径 ----------
D = run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill",
    "target": TARGET_SKILL,
    "pattern_key": "missing_artifact_check",
    "problem": "报价单缺 artifact existence verification 连续3次",
    "evidence_refs": ["E1", "E2", "E3"],
    "recurrence": 3, "sessions": 2, "independent_sources": 2,
    "systemic": True, "confidence": 0.85})], "CANDIDATE_CREATED")
CAND = D.get("candidate_id")
assert CAND, "no candidate id"

D = run(["diagnose.py", "--candidate", CAND, "--root_cause", "workflow_gap",
         "--valid", "--reproducible", "--confidence", "0.8", "--level", "G3",
         "--target", TARGET_SKILL], "DIAGNOSED")
DGN = D.get("diagnosis_id")

D = run(["propose.py", "--candidate", CAND, "--diagnosis", DGN, "--scope", "skill",
         "--level", "G3", "--targets", TARGET_SKILL,
         "--change", "在文件生成后增加 artifact existence verification",
         "--expected_metric", "verification >= 0.9"], "PROPOSAL_CREATED")
PRP = D.get("proposal_id")

D = run(["apply.py", "--proposal", PRP, "--approve", "--approver", "main",
         "--reason", "G3 confirmed"], "APPLIED")
CHG = D.get("change_id")

D = run(["regression.py", "--change", CHG, "--result", "IMPROVED",
         "--evidence", '{"verification":"passed"}'], "REGRESSION_RECORDED")
RGR = D.get("regression_id")
assert D.get("promotion") == "PROMOTED", "success promotion failed"

# 2. Evidence Chain 可追溯
D = run(["_core.py", "--chain", RGR], expect_decision=None)
chain = D if isinstance(D, dict) else {}
if chain.get("regression") and chain.get("candidate"):
    PASS += 1; RESULTS.append("PASS chain_traceability")
else:
    FAIL += 1; RESULTS.append("FAIL chain_traceability " + json.dumps(chain)[:80])

# 3. 幂等 Discover
run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill",
    "target": TARGET_SKILL,
    "pattern_key": "missing_artifact_check",
    "problem": "再次", "recurrence": 5, "sessions": 3,
    "evidence_refs": ["E9"], "confidence": 0.9})], "DEDUP_EXISTING")

# 4. 外因拦截
run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill", "target": "api.md",
    "pattern_key": "api_down", "problem": "API 挂",
    "tags": "api network timeout", "recurrence": 3, "sessions": 2,
    "evidence_refs": ["E"], "confidence": 0.7})], "IGNORE")

# 5. 保护目标
C2 = run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "global", "target": "AGENTS.md",
    "pattern_key": "chg_agents", "problem": "改AGENTS",
    "recurrence": 3, "sessions": 2, "independent_sources": 2,
    "systemic": True, "confidence": 0.8})], "CANDIDATE_CREATED").get("candidate_id")
r = subprocess.run([sys.executable, "diagnose.py", "--candidate", C2,
                    "--root_cause", "instruction_gap", "--valid", "--reproducible",
                    "--confidence", "0.8", "--level", "G5", "--target", "AGENTS.md"],
                   capture_output=True, text=True, cwd=SCRIPT,
                   env={**os.environ})
if "受保护" in (r.stderr + r.stdout):
    PASS += 1; RESULTS.append("PASS protected_target_reject")
else:
    FAIL += 1; RESULTS.append("FAIL protected_target_reject " + (r.stderr + r.stdout)[:80])

# 6. G5 强制人工审批
C3 = run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "protocol", "target": "docs/PROTOCOL.md",
    "pattern_key": "fix_protocol", "problem": "协议措辞",
    "recurrence": 3, "sessions": 2, "independent_sources": 2,
    "systemic": True, "confidence": 0.8})], "CANDIDATE_CREATED").get("candidate_id")
D3 = run(["diagnose.py", "--candidate", C3, "--root_cause", "workflow_gap",
          "--valid", "--reproducible", "--confidence", "0.8", "--level", "G5",
          "--target", "docs/PROTOCOL.md"], "DIAGNOSED").get("diagnosis_id")
P3 = run(["propose.py", "--candidate", C3, "--diagnosis", D3, "--scope", "protocol",
          "--level", "G5", "--targets", "docs/PROTOCOL.md",
          "--change", "改协议措辞", "--expected_metric", "明确"],
         "PROPOSAL_CREATED").get("proposal_id")
# 不带 approve → 拒绝
D = run(["apply.py", "--proposal", P3, "--approver", "main", "--reason", "no flag"], "REJECT")
if D and "G5" in str(D.get("reason", "")):
    PASS += 1; RESULTS.append("PASS g5_human_approve_reject_default")
else:
    FAIL += 1; RESULTS.append("FAIL g5_human_approve_reject_default " + json.dumps(D)[:60])

# 7. 失败 → Rollback
C4 = run(["discover.py", "--evidence", json.dumps({
    "class": "user_feedback", "scope": "skill",
    "target": TARGET_TOOL, "pattern_key": "add_review",
    "problem": "用户多次要求加 review", "evidence_refs": ["u1", "u2", "u3"],
    "recurrence": 3, "sessions": 2, "independent_sources": 2,
    "systemic": True, "confidence": 0.8})], "CANDIDATE_CREATED").get("candidate_id")
D4 = run(["diagnose.py", "--candidate", C4, "--root_cause", "workflow_gap",
          "--valid", "--reproducible", "--confidence", "0.8", "--level", "G3",
          "--target", TARGET_TOOL], "DIAGNOSED").get("diagnosis_id")
P4 = run(["propose.py", "--candidate", C4, "--diagnosis", D4, "--scope", "skill",
          "--level", "G3", "--targets", TARGET_TOOL,
          "--change", "加 review 步骤", "--expected_metric", "review done"],
         "PROPOSAL_CREATED").get("proposal_id")
H4 = run(["apply.py", "--proposal", P4, "--approve", "--approver", "main",
          "--reason", "ok"], "APPLIED").get("change_id")
R4 = run(["regression.py", "--change", H4, "--result", "REGRESSED",
          "--evidence", '{"degraded":true}'], "REGRESSION_RECORDED").get("regression_id")
D = run(["rollback.py", "--change", H4, "--reason", "degraded", "--regression", R4],
        "ROLLED_BACK")
if D and D.get("state") == "ROLLED_BACK":
    PASS += 1; RESULTS.append("PASS rollback_end_state")
else:
    FAIL += 1; RESULTS.append("FAIL rollback_end_state " + json.dumps(D)[:60])

# 非法状态跳转：CANDIDATE 不能直接 APPROVED（无入口，apply 需 proposal）
# 通过 assert_transition 单测
import _core
try:
    _core.assert_transition({"status": "CANDIDATE"}, "APPLIED")
    FAIL += 1; RESULTS.append("FAIL illegal_transition")
except ValueError:
    PASS += 1; RESULTS.append("PASS illegal_transition")

shutil.rmtree(WS, ignore_errors=True)
print("\n===== REGRESSION SUMMARY =====")
print("PASS: {}\tFAIL: {}".format(PASS, FAIL))
print("\n".join(RESULTS))
sys.exit(0 if FAIL == 0 else 1)
