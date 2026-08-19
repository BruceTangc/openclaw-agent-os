# -*- coding: utf-8 -*-
"""verification-evaluation 验证实现（V0-V4 分级 + 状态判定 + retry_eligible）。

职责边界（对齐 Agent OS v1.3 契约）：
- 本模块只做「验证/评估判断」，输出 PASS/PARTIAL/FAIL/UNKNOWN + retry_eligible。
- 不执行任务、不执行 retry、不建 verification runtime。
- retry_eligible 是「失败诊断结论」（该不该重试），真正的 retry count/budget/attempt
  归 task-manager，retry/replan/routing 归 orchestrator，实际执行归 OpenClaw Runtime。
  （VER-01：Verification 不拥有自己的 Retry Runtime。）

调用方：orchestrator 的 verify_result 作为 adapter 转发到这里（ORC-02）。
"""
import json
import sys

VERIFY_LEVELS = ["V0", "V1", "V2", "V3", "V4"]
VERDICTS = ["PASS", "PARTIAL", "FAIL", "UNKNOWN", "UNAVAILABLE"]


def unavailable(reason):
    """验证器自身不可用 → UNAVAILABLE（不是 Task FAIL）。

    CHAIN-02：区分「任务失败」（FAIL）与「验证器坏了/timeout/模块缺失/JSON 损坏」
    （UNAVAILABLE）。UNAVAILABLE 交给 Evaluation / Autonomy Decision，不直接等价 FAIL，
    避免「执行成功 + 验证服务超时 → 误判 FAIL → 任务结束」。
    """
    return {
        "level": "V0",
        "verdict": "UNAVAILABLE",
        "passed": False,
        "retry_eligible": False,
        "reason": reason,
        "checks": [],
    }


def _fmt_ok(v):
    """结构校验：是否 dict、是否含必要字段。"""
    if not isinstance(v, dict):
        return False
    return True


def verify(result, level="V1"):
    """按验证等级检查结果，返回 {level, verdict, passed, checks, retry_eligible}。

    V0-V4 逐级累计，高等级必须同时满足低等级全部检查。
    """
    if level not in VERIFY_LEVELS:
        level = "V1"
    if not _fmt_ok(result):
        # 结构非法 → FAIL（不是 UNKNOWN，连可验证的对象都不是）
        return {
            "level": level,
            "verdict": "FAIL",
            "passed": False,
            "retry_eligible": False,
            "reason": "result 非 dict，无法验证",
            "checks": [{"check": "V0 tool_success", "ok": False}],
        }

    checks = []
    # V0: 工具返回成功
    checks.append({"check": "V0 tool_success", "ok": bool(result.get("tool_success"))})
    if level == "V0":
        return _render(level, checks)

    # V1: 输出格式正确
    has_output = "output" in result or "outputs" in result or "summary" in result
    checks.append({"check": "V1 format", "ok": has_output})
    if level == "V1":
        return _render(level, checks)

    # V2: 结果符合任务条件
    checks.append({"check": "V2 condition", "ok": bool(result.get("success_condition_met"))})
    if level == "V2":
        return _render(level, checks)

    # V3: 独立验证，须 method + evidence_refs + verified_by 齐全
    v3 = result.get("verification") if isinstance(result.get("verification"), dict) else result
    method = v3.get("verification_method") or v3.get("method")
    evidence_refs = v3.get("evidence_refs") or result.get("evidence_refs")
    verified_by = v3.get("verified_by") or result.get("verified_by")
    indep = bool(v3.get("independently_verified") or result.get("independently_verified"))
    has_evidence_list = isinstance(evidence_refs, (list, tuple, set)) and len(evidence_refs) > 0
    v3_ok = bool(method) and bool(verified_by) and has_evidence_list and indep
    # MA-1.0 (规格 11.3/11.4): producer/verifier 分离 —— 只透传 provenance,
    #   不改变 v3_ok 判定。producer=产生结果的 Agent, verifier=独立复核的 Agent。
    producer_agent_id = v3.get("producer_agent_id") or result.get("producer_agent_id") or ""
    verifier_agent_id = v3.get("verifier_agent_id") or result.get("verifier_agent_id") or ""
    checks.append({
        "check": "V3 independent_verified",
        "ok": v3_ok,
        "detail": {
            "method": method,
            "evidence_refs_count": len(evidence_refs) if has_evidence_list else 0,
            "verified_by": verified_by,
            "independent": indep,
            "producer_agent_id": producer_agent_id,
            "verifier_agent_id": verifier_agent_id,
        },
    })
    if level == "V3":
        return _render(level, checks, unknown="V3 缺少 method/evidence_refs/verified_by/independent 之一")

    # V4: 外部状态变化
    checks.append({"check": "V4 external_state", "ok": bool(result.get("state_changed"))})
    return _render(level, checks)


def _render(level, checks, unknown=None):
    """汇总 checks → PASS/PARTIAL/FAIL/UNKNOWN + retry_eligible。"""
    all_ok = all(c["ok"] for c in checks)
    any_ok = any(c["ok"] for c in checks)
    none_ok = not any_ok

    # 定状态（对齐契约状态定义）
    if all_ok:
        verdict = "PASS"
    elif unknown and not all_ok:
        # 独立验证无法确认 → UNKNOWN（证据不足 ≠ 失败）
        verdict = "UNKNOWN"
    elif none_ok:
        verdict = "FAIL"
    else:
        verdict = "PARTIAL"

    # retry_eligible：只有「瞬时/可修复的失败」才建议重试；
    # UNKNOWN（证据不足）→ 补证据而非盲目重试；FAIL（确定性失败）→ 诊断修复而非重试。
    # 这里只给出诊断结论，不执行 retry。
    retry_eligible = verdict == "PARTIAL"

    return {
        "level": level,
        "verdict": verdict,
        "passed": all_ok,
        "retry_eligible": retry_eligible,
        "checks": checks,
    }


def main():
    """CLI: --json <result-json> --level <level>。

    CHAIN-02：JSON 损坏/无法解析 = 验证器无法处理 = UNAVAILABLE（非 Task FAIL）。
    验证器超时/模块缺失等由调用方 adapter 自行 catch 并映射为 UNAVAILABLE。
    """
    import argparse
    p = argparse.ArgumentParser(description="verification-evaluation 验证分级判定")
    p.add_argument("--json", help="result JSON 或 -")
    p.add_argument("--level", default="V1")
    a = p.parse_args()

    raw = a.json
    if raw == "-" or raw is None:
        raw = sys.stdin.read()
    try:
        result = json.loads(raw)
    except Exception as e:
        print(json.dumps(unavailable("invalid JSON: " + str(e)),
                         ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(verify(result, a.level), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
