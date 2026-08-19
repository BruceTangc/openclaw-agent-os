#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regression.py — Self-Evolution v2.3 · Regression (APPLIED → MONITORING → VALIDATED/REGRESSED)

v2.3: MONITORING/VALIDATED 状态、evolution_id 全链路。
"""
import argparse
import json
import _core

RESULTS = ["IMPROVED", "NO_CHANGE", "REGRESSED", "UNKNOWN"]

# #17 契约：Autonomy Decision 顶层词汇（归一到 #5 标准词）
PROGRESS_DECISIONS = ["CONTINUE", "COMPLETE", "CHANGE_STRATEGY", "ASK", "STOP"]


def progress_gate(change_id):
    """#17 决策器：Progress Assessment → Autonomy Decision（不直改状态）。

    职责（架构 #17）：
      - 消费 #16 检测器输出（assess_progress）
      - 比较 current vs previous progress，产出顶层决策词
      - 决策可溯源：记录 progress_signal + decision + reason + evidence 引用（#20）
      - 决策 ≠ 状态转换：#5/#13 要求决策先产出 Transition Request，再经 Transition
        Gate 落地。此函数返回决策 + transition 建议，状态变更由调用方经 #13 门执行。
    返回 (decision, transition_request, detail):
      decision ∈ PROGRESS_DECISIONS
      transition_request = {"kind": "change", "dst": "...", "reason": "..."} 或 None
    """
    signal = _core.assess_progress(change_id)
    chg = _core.load_artifact("change", change_id)
    if not chg:
        return "STOP", None, {"signal": signal, "reason": "change 不存在"}

    cur = signal.get("current_progress")
    prev = signal.get("previous_progress")
    delta = signal.get("progress_delta")
    rep = signal.get("repetition_count", 0)
    stall = signal.get("consecutive_stall_count", 0)

    # #16 L3: 优先查 Goal Loop（换动作空转、goal progress 始终为 0）。
    # 这是 L1/L2 检测不到的模式（action 每次不同但零进展），优先级最高，
    # 命中即 STOP，不进入下方 delta 决策分支。
    goal_loop = _core.detect_goal_loop(change_id)
    if goal_loop.get("is_loop"):
        decision = "STOP"
        req = {"kind": "change", "dst": "REGRESSED",
               "reason": "progress_gate: #16 L3 Goal Loop 检测到换动作空转"
                         " (consecutive_stall={}, progress={})".format(
                             goal_loop.get("consecutive_stall_count"),
                             goal_loop.get("current_progress")),
               "decision": decision}
        detail = {"signal": signal, "goal_loop": goal_loop, "decision": decision,
                  "reason": req["reason"]}
        return decision, req, detail

    # 决策链：Evaluation（达标）优先，其次 Progress（进展），最后 stall 处理。
    if cur is None:
        # L3 三态：UNKNOWN（无 Progress 信号，暂时无法测量）→ WAIT/VERIFY/ASK，
        # 不误判为 STALL/STOP。归因为测量不可用（API/验证数据/无 fingerprint），
        # 交集出给上层：信息不足需人工/补充测量推进，而非判「换动作空转」停止。
        decision = "ASK"   # UNKNOWN：信息不足，需人工/补充测量推进
        req = {"kind": "change", "dst": "MONITORING",
               "reason": "progress_gate: UNKNOWN（无 Progress 信号，无法测量）",
               "decision": decision}
    elif delta is None:
        # 首次评估：有当前进度但无基线。有进展信号则 Continue。
        decision = "CONTINUE" if cur > 0 else "ASK"
        req = {"kind": "change", "dst": "MONITORING",
               "reason": "progress_gate: 首次评估 cur={}".format(cur),
               "decision": decision}
    elif delta > 0:
        decision = "CONTINUE"
        req = {"kind": "change", "dst": "MONITORING",
               "reason": "progress_gate: 有进展 delta={:+}".format(delta),
               "decision": decision}
    elif delta == 0:
        # 停滞：连续无进展 → Change Strategy，连续停滞达阈值 → Stop。
        # #17 修复(BUG-1)：STOP 阈值挂连续停滞计数(consecutive_stall_count)，
        # 而非全局评估次数，避免长期有进展、偶发一次停滞被过早 STOP。
        stall = signal.get("consecutive_stall_count", 0)
        decision = "CHANGE_STRATEGY" if stall < _core.STALL_THRESHOLD else "STOP"
        req = {"kind": "change", "dst": "REGRESSED" if decision == "STOP" else "MONITORING",
               "reason": "progress_gate: {} delta=0 stall={}".format(decision, stall),
               "decision": decision}
    else:
        # delta < 0：进展倒退
        decision = "STOP"
        req = {"kind": "change", "dst": "REGRESSED",
               "reason": "progress_gate: 进展倒退 delta={:+}".format(delta),
               "decision": decision}

    detail = {"signal": signal, "decision": decision, "reason": req["reason"]}
    return decision, req, detail


def run_regression(change_id, result, evidence):
    if result not in RESULTS:
        return None, "result 非法: " + str(result)

    chg = _core.load_artifact("change", change_id)
    if not chg:
        return None, "change 不存在: " + change_id
    if chg.get("status") not in ("APPLIED", "MONITORING"):
        return None, "change 状态不是 APPLIED/MONITORING: " + str(chg.get("status"))

    # 幂等：同 change 已记录 regression 不重复
    for rid in _core._list_ids("regression"):
        prev = _core.load_artifact("regression", rid)
        if prev and prev.get("change_id") == change_id:
            return prev["id"], "DEDUP_EXISTING_REGRESSION"

    evo_id = chg.get("evolution_id")
    rgr = {"status": "REGRESSION", "evolution_id": evo_id,
           "change_id": change_id, "proposal_id": chg.get("proposal_id"),
           "candidate_id": chg.get("candidate_id"),
           "diagnosis_id": chg.get("diagnosis_id"),
           "result": result, "evidence": evidence,
           "recorded_at": _core.now_iso()}
    rid = _core.save_artifact("regression", rgr)
    rgr["id"] = rid

    # v2.3: 状态推进 APPLIED → MONITORING → 结果
    if chg.get("status") == "APPLIED":
        _core.assert_transition(chg, "MONITORING", kind="change")
        _core.save_artifact("change", chg)

    if result == "IMPROVED":
        _core.assert_transition(chg, "VALIDATED", kind="change")
        _core.save_artifact("change", chg)
        _core.assert_transition(chg, "PROMOTED", kind="change")
        _core.save_artifact("change", chg)
        # v1.4 C1: regression 记录状态也走统一门 (REGRESSION→PROMOTED)
        _core.assert_transition(rgr, "PROMOTED", kind="regression")
        _core.save_artifact("regression", rgr)
    elif result == "REGRESSED":
        _core.assert_transition(chg, "REGRESSED", kind="change")
        _core.save_artifact("change", chg)
        # v1.4 C1: regression 记录状态也走统一门 (REGRESSION→REGRESSED)
        _core.assert_transition(rgr, "REGRESSED", kind="regression")
        _core.save_artifact("regression", rgr)
        # v2.4: Regression 产生 evolution_event Evidence（"这次修改失败"是重要信号）
        try:
            _core.register_evolution_event("regression", change_id, reason=evidence or "",
                                           regression_id=rid)
        except ValueError as e:
            print(json.dumps({"warning": "regression evidence 未生成: {}".format(e)},
                              ensure_ascii=False))
    # NO_CHANGE / UNKNOWN: 不推进状态。但 #17 契约要求接入 Progress Gate 决策器：
    # 检测器 assess_progress → 决策器 progress_gate → 经 #13 门落地（不直改 status）。
    # 决策可溯源：record_progress_assessment 写 progress_signal + repetition_count。
    if result in ("NO_CHANGE", "UNKNOWN"):
        decision, req, detail = progress_gate(change_id)
        # 记录本次 Progress Assessment（可溯源）
        _core.record_progress_assessment(change_id, detail["signal"])
        rgr["progress_gate"] = detail
        # #17 契约：Autonomy Decision ≠ State Transition——决策经 #13 门落地为 Transition Request，
        # 不通过直改 status。仅 STOP（倒退/停滞达上限）才推进 REGRESSED，其余保持观察。
        if decision == "STOP" and req and req["dst"] == "REGRESSED":
            _core.assert_transition(chg, req["dst"], kind="change",
                                    verify_error=req["reason"],
                                    progress_signal=detail["signal"])
            _core._core_save_artifact("change", chg)
            _core.assert_transition(rgr, "REGRESSED", kind="regression")
        _core.save_artifact("regression", rgr)

    return rid, None


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2.3 Regression")
    p.add_argument("--change", required=True)
    p.add_argument("--result", required=True, choices=RESULTS)
    p.add_argument("--evidence", default="{}")
    p.add_argument("--rollback", action="store_true")
    args = p.parse_args()
    rid, err = run_regression(args.change, args.result, args.evidence)
    if err:
        print(json.dumps({"decision": "DEDUP" if "DEDUP" in err else "REJECT",
                          "reason": err}, ensure_ascii=False, indent=2))
        return
    rgr = _core.load_artifact("regression", rid)
    out = {"decision": "DEDUP_EXISTING_REGRESSION" if err else "REGRESSION_RECORDED",
           "regression_id": rid, "result": rgr.get("result"), "status": rgr.get("status"),
           "evolution_id": rgr.get("evolution_id")}
    if args.result == "IMPROVED":
        out["promotion"] = "PROMOTED"
    elif args.result == "REGRESSED":
        out["action"] = "ROLLBACK_REQUIRED"
        out["rollback_cmd"] = "python3 rollback.py --change {}".format(args.change)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
