#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recovery.py — Self-Evolution v2.4 · Recovery 启动恢复入口

两个职责：
1. Crash Recovery Mechanism 闭环：启动时检测 APPLYING 中断的 change，按策略恢复。
2. Cross-artifact 一致性恢复：自动修复 Change=APPLIED 而 Proposal 仍停留在 APPROVED 的
   不一致状态（Proposal 应随之推进到 APPLIED）。

v2.4：恢复动作本身不做Evidence 写入/删除（恢复是被动修复，不是新事实）。
"""
import argparse
import json
import _core


def run_crash_recovery(apply=False):
    """检测 APPLYING 中断的 change，返回待处理或被恢复的列表。

    apply=False：只报告（dry-run）。
    apply=True：对 SAFE_TO_RETRY 自动重试 apply，对 ROLLBACK/VERIFY 返回供人工处理。
    """
    incomplete = _core.detect_incomplete_apply()
    results = []
    for change_id in incomplete:
        action, detail = _core.recover_apply(change_id)
        item = {"change_id": change_id, "action": action, "detail": detail}
        if apply and action == "SAFE_TO_RETRY":
            item["applied_action"] = _retry_apply(change_id)
        results.append(item)
    return results


def _retry_apply(change_id):
    """SAFE_TO_RETRY 时重新触发 apply（导入适用模块以复用 main 逻辑）。

    v1.3: apply.py 的入口是 apply_change(proposal_id,...)，重新触发需回到
    Proposal 粒度（Change 缺失时会重新建 Change Record）。这里做健壮回退：
    若 Change 有 proposal_id 且 Proposal 仍 PROPOSED/APPROVED，则复用其操作
    重新 apply；否则返回需人工介入，避免 ImportError 崩溃。
    """
    try:
        from apply import _retry_from_change
        return _retry_from_change(change_id)
    except ImportError:
        return "RETRY_MANUAL: apply 内部入口不可用，需人工确认后重新 apply"
    except Exception as e:
        return "RETRY_FAILED: {}".format(str(e))


def run_cross_artifact_consistency(apply=False):
    """跨 artifact 一致性：Change=APPLIED（不含 PROMOTED 前提）时，Proposal 若仍 APPROVED
    则自动推进为 APPLIED。

    apply=False：dry-run 报告。
    apply=True：实际修复。
    """
    fixed = []
    for change_id in _core._list_ids("change"):
        chg = _core.load_artifact("change", change_id)
        if not chg or chg.get("status") != "APPLIED":
            continue
        proposal_id = chg.get("proposal_id", "")
        prp = _core.load_artifact("proposal", proposal_id) if proposal_id else None
        if prp and prp.get("status") == "APPROVED":
            if apply:
                try:
                    _core.assert_transition(prp, "APPLIED", kind="proposal")
                except ValueError:
                    # v1.4 C1: 去 except 后暴力直改。门拒绝则记 transition_denied,
                    #   不静默改成 APPLIED(保持状态真实)。
                    prp.setdefault("history", []).append({
                        "timestamp": _core.now_iso(), "actor": "system",
                        "action": "transition_denied", "from": prp.get("status"),
                        "to": "APPLIED",
                        "reason": "recovery: 门拒绝 proposal APPLIED 跳转",
                    })
                _core._core_save_artifact("proposal", prp)
                fixed.append({"change_id": change_id, "proposal_id": proposal_id,
                              "fixed": True})
            else:
                fixed.append({"change_id": change_id, "proposal_id": proposal_id,
                              "would_fix": True})
    return fixed


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2.4 Recovery 启动恢复")
    p.add_argument("--crash", action="store_true", help="Crash Recovery 检测/恢复")
    p.add_argument("--consistency", action="store_true",
                   help="Cross-artifact 一致性（Change=APPLIED 推进 Proposal=APPLIED）")
    p.add_argument("--apply", action="store_true", help="实际执行修复（默认 dry-run）")
    p.add_argument("--all", action="store_true", help="同时跑 crash + consistency")
    args = p.parse_args()

    out = {}
    if args.all or args.crash:
        out["crash_recovery"] = run_crash_recovery(apply=args.apply)
    if args.all or args.consistency:
        out["cross_artifact"] = run_cross_artifact_consistency(apply=args.apply)
    if not (args.all or args.crash or args.consistency):
        out["crash_recovery"] = run_crash_recovery(apply=args.apply)
        out["cross_artifact"] = run_cross_artifact_consistency(apply=args.apply)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
