#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Permission Security 最小确定性脚本 (L0-L4 分类器)

把 v1.1 政策层的 L0-L4 分级落地为可调用的确定性接口，供
orchestrator/proactive 在执行前调用：

  --classify <action>         返回 {level, requires_approval, reversibility}
  --check <json>              完整授权检查 (action+resource+side_effect)

L0 Observe:  read/search/analyze            → auto
L1 Prepare:  draft/reversible local change  → auto if in scope
L2 External: message/email/publish/business → confirm unless authorized
L3 High:     delete/payment/permission/sensitive export/dangerous host → approval
L4 Prohibited: bypass security/credential theft/unauthorized destructive → deny

原则 (SKILL.md): Never weaken or bypass native controls.
OpenClaw 原生 policy/approval 仍为最终拦截层, 本脚本仅做决策层分类。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# ---- 中央门 (C2 Permission 状态机) ----
# 授权记录生命周期走 skills/_lib/transitions.py 中央门 (kind="permission")。
# CRITICAL fix (C-2): 不硬编码绝对路径 —— 换机/容器路径不同会 import 失败
# → 状态机静默降级、状态强制失效。改为从本文件相对推导到 _lib/:
#   permission.py 位于 skills/permission-security/scripts/permission.py
#   scripts -> permission-security(1) -> skills(2) -> 故向上两层到 skills/, 再 _lib
_LIB = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 os.pardir, os.pardir, "_lib"))
try:
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from transitions import transition as _perm_transition, valid_states as _perm_states
except Exception:  # pragma: no cover - 中央门不可用时降级为无状态判定
    _perm_transition = None
    _perm_states = None

# A-3 fix: 授权决策审计留痕 (复用 persistence.py atomic_write + JSONL)。
# 不把"谁批准"当 Agent OS 的持久化责任 —— 批准动作由 OpenClaw Native Approval
# 承接 (架构 #14); Agent OS 只落盘"决策了什么、依据什么"(架构 #19/#22)。
_AUDIT_PATH = os.getenv("AGENTOS_PERM_AUDIT",
    os.path.join(os.path.expanduser("~/.openclaw/workspace"),
                 ".agent-os", "permissions", "audit.jsonl"))
_append_atomic = None
try:
    from persistence import append_atomic as _append_atomic
    from persistence import atomic_write_json as _atomic_write_json
except Exception:  # pragma: no cover - 审计不可用时降级为仅内存决策
    _append_atomic = None


def _audit(entry):
    """授权决策审计留痕 (append-only JSONL)。失败不阻断决策 (决策层降级)。"""
    if _append_atomic is None:
        return False
    try:
        _append_atomic(_AUDIT_PATH, entry)
        return True
    except Exception:
        return False


# 授权记录默认状态：创建即 REQUESTED（未审批）
PERMISSION_REQUIRES_STATE = True  # C2: check() 强制校验授权记录状态

# L0-L4 动作分类
ACTION_LEVELS = {
    # L0 Observe
    "read": 0, "search": 0, "analyze": 0, "observe": 0, "inspect": 0,
    "list": 0, "query": 0, "summarize": 0,
    # L1 Prepare
    "draft": 1, "create_draft": 1, "plan": 1, "compute": 1,
    "write_temp": 1, "create_temp": 1, "edit_local": 1, "reversible_change": 1,
    # L2 External impact
    "send": 2, "message": 2, "email": 2, "reply": 2, "post": 2,
    "publish": 2, "business_change": 2, "update_record": 2, "api_call": 2,
    # L3 High impact
    "delete": 3, "remove": 3, "payment": 3, "transfer": 3, "transfer_money": 3,
    "order": 3, "trade": 3,
    "grant": 3, "revoke": 3, "change_permission": 3, "export_sensitive": 3,
    "dangerous_host_op": 3, "modify_production": 3, "merge": 3, "push": 3,
    # L4 Prohibited
    "bypass_security": 4, "credential_theft": 4, "unauthorized_destructive": 4,
    "exfiltrate": 4, "privilege_escalation": 4,
}

# 资源敏感度加成
RESOURCE_BONUS = {
    "public": 0, "internal": 0, "workspace": 0, "project": 0,
    "private": 1, "personal": 1,
    "sensitive": 2, "financial": 3, "credential": 4, "secret": 4,
    "production": 2, "database": 2,
}

REQUIRES_APPROVAL = {0: False, 1: False, 2: True, 3: True, 4: True}
REVERSIBILITY = {0: "reversible", 1: "reversible", 2: "partially_reversible",
                 3: "irreversible_or_high_impact", 4: "irreversible"}
DEFAULT_DENY = {0: False, 1: False, 2: False, 3: False, 4: True}


def _perm_record(req):
    """从 req 构造/定位授权记录。兼容两种形态:
    - req["authorization"] 是 dict 且含 status → 已进状态机(有记录)
    - 否则视为"未审批", 不启状态强制但也不信任其放行。

    A-1 fix (fail-closed): 只要提供了 authorization dict 却缺 status,
    说明授权来源不完整/未走状态机 —— 不得退回旧布尔判定放行 (那会成为
    绕过面: 去掉 status 即可绕过 CONSUMED/REVOKED)。返回 (record, has_state),
    其中 has_state=False 时 check() 将把 authorized 视为不可用。
    """
    authz = req.get("authorization")
    if isinstance(authz, dict) and authz.get("status"):
        return authz, True
    if isinstance(authz, dict) and not authz.get("status"):
        # 有 authorization 容器但无状态 → 不完整个授权, 状态强制视为"未批准"
        return authz, True
    return None, False


def _perm_status_ok(record):
    """授权记录必须处于 APPROVED 且未消费/吊销/过期才视为有效。"""
    if record is None:
        return True, None  # 无授权记录 → 交现有布尔判定 (整体未被授权依赖)
    st = record.get("status")
    if st == "APPROVED":
        return True, None
    if st is None or st == "":
        # fail-closed: 有 authorization 容器但无 status → 视为未审批, 不信任
        return False, "authorization 无 status (fail-closed: 视为未审批)"
    reason = {
        "REQUESTED": "授权待审批 (REQUESTED)",
        "REJECTED": "授权已拒绝 (REJECTED)",
        "EXPIRED": "授权已过期 (EXPIRED)",
        "REVOKED": "授权已吊销 (REVOKED)",
        "CONSUMED": "一次性授权已消费 (CONSUMED)",
    }.get(st, "授权状态异常 (%s)" % st)
    return False, reason


def request_permission(req):
    """创建授权记录 (REQUESTED)。返回记录或 None(降级)。

    A-2 fix: 支持一次性授权 + Action fingerprint 绑定 (架构 #15)。
    - req["one_time"]=True → 标记一次性: 执行一次后即用尽 (CONSUMED)
    - req["fingerprint"] 或 req["action_fingerprint"] → 授权绑定到具体 Action,
      Action 变化 (指纹不同) 时必须重新判断, 不能"Task批准就什么都能做"
    """
    rec = {
        "status": "REQUESTED",
        "action": req.get("action"),
        "scope": req.get("scope") or req.get("requested_scope"),
        "one_time": bool(req.get("one_time", False)),
        "fingerprint": req.get("fingerprint") or req.get("action_fingerprint") or "",
        "requested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "history": [],
    }
    return rec


def _permission_transition(rec, to, actor="system", reason=""):
    """经中央门变更授权记录状态；门不可用时退化直接写(仍记录)。"""
    if _perm_transition is not None:
        _perm_transition(rec, to, kind="permission", actor=actor, reason=reason)
    else:
        rec["status"] = to
        rec.setdefault("history", []).append({
            "event": "transition", "to": to, "actor": actor, "reason": reason,
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return rec


def approve_permission(rec, actor="system", reason="approval"):
    """REQUESTED→APPROVED。"""
    return _permission_transition(rec, "APPROVED", actor=actor, reason=reason)


def reject_permission(rec, actor="system", reason="rejected"):
    return _permission_transition(rec, "REJECTED", actor=actor, reason=reason)


def consume_permission(rec, actor="execution", reason="consumed"):
    """APPROVED→CONSUMED (一次性授权已执行)。"""
    return _permission_transition(rec, "CONSUMED", actor=actor, reason=reason)


def revoke_permission(rec, actor="system", reason="revoked"):
    return _permission_transition(rec, "REVOKED", actor=actor, reason=reason)


def expire_permission(rec, actor="system", reason="expired"):
    return _permission_transition(rec, "EXPIRED", actor=actor, reason=reason)


def classify(action, resource_type="internal", side_effect="NONE", scope=None):
    """返回 L0-L4 分类结果."""
    a = action.lower()
    level = ACTION_LEVELS.get(a)

    if level is None:
        # 未知动作 → 按资源敏感度猜测, 保守起见不低于 L1
        res_bonus = RESOURCE_BONUS.get(resource_type.lower(), 0)
        level = max(1, min(3, res_bonus))
        unknown = True
    else:
        unknown = False
        # 资源敏感度加成: L1 动作 + 敏感资源 → L2; L2 + 财务/凭证 → L3
        res_bonus = RESOURCE_BONUS.get(resource_type.lower(), 0)
        if res_bonus >= 3 and level <= 2:
            level = max(level, 2 if res_bonus == 3 else 3)
        elif res_bonus == 2 and level <= 1:
            level = 2

    # 外部副作用 → 至少 L2
    if str(side_effect).upper() in ("EXTERNAL", "PUBLIC", "FINANCIAL") and level < 2:
        level = 2

    # 无 scope 的中高风险 → 提示
    no_scope = (not scope) and level >= 2

    return {
        "action": a,
        "level": "L{}".format(level),
        "requires_approval": REQUIRES_APPROVAL[level],
        "reversibility": REVERSIBILITY[level],
        "default_deny": DEFAULT_DENY[level] or no_scope,
        "unknown_action": unknown,
        "no_scope_warning": no_scope,
    }


def check(req):
    """完整授权检查: req = {action, resource_type, side_effect, scope, authorized}

    PHASE 1 P0 fail-closed: 输入缺失/异常 → deny, 不默认放行。
    """
    action = req.get("action")
    if not action or not isinstance(action, str) or not action.strip():
        return {
            "decision": "deny", "level": "R?",
            "reason": "fail-closed: empty/missing action",
            "requires_approval": True,
            "reversibility": "unknown",
            "native_policy_final": True,
        }
    resource_type = (req.get("resource") or {}).get("type", "internal") \
        if isinstance(req.get("resource"), dict) else req.get("resource_type", "internal")
    side_effect = req.get("external_side_effect", req.get("side_effect", "NONE"))
    scope = req.get("scope")
    authorized = req.get("authorized", False)  # 是否已有授权/审批
    # P1-9 (#29/#30): authorization 结构化元数据 + requested scope ≤ authorized scope
    authorization = req.get("authorization") if isinstance(req.get("authorization"), dict) else {}
    auth_scope = authorization.get("scope") or req.get("authorized_scope")
    auth_source = authorization.get("source") or req.get("authorization_source")
    auth_expiry = authorization.get("expiry") or req.get("authorization_expiry")
    requested_scope = req.get("requested_scope") or scope

    cls = classify(action, resource_type, side_effect, scope)
    level = int(cls["level"][1])

    # P1-9 (#30): requested scope ≤ authorized scope 才视为已授权；越界则需重新确认。
    scope_ok = True
    scope_problem = None
    if requested_scope and auth_scope:
        # 简单层级比较：从具体到通用。authorized=GLOBAL > PROJECT > AGENT > TASK > 具体ID
        order = {"TASK": 1, "AGENT": 2, "PROJECT": 3, "GLOBAL": 4, "USER": 4}
        r = str(requested_scope).upper()
        a = str(auth_scope).upper()
        if r in order and a in order and order[r] > order[a]:
            scope_ok = False
            scope_problem = "requested scope %s 超出 authorized scope %s" % (r, a)
        elif r not in order and a not in order and r != a:
            # 具体ID级别：要求精确匹配或 authorized 为更宽的 TASK/AGENT
            if r != a:
                scope_ok = False
                scope_problem = "requested scope %s 与 authorized scope %s 不匹配" % (r, a)
    auth_valid = bool(authorized) and bool(authorization or auth_scope or auth_expiry or auth_source)
    # C2 (Permission 状态机): 若授权记录已进状态机，状态必须 APPROVED 才视为有效。
    perm_rec, perm_has_state = _perm_record(req)
    perm_status_ok = True
    perm_status_problem = None
    if perm_has_state:
        perm_status_ok, perm_status_problem = _perm_status_ok(perm_rec)
        if not perm_status_ok:
            auth_valid = False

    # A-2 fix (架构 #15): Permission 绑定 Action。授权记录若带 fingerprint,
    # 则本次 req 的 action_fingerprint 必须匹配, 否则视为"Action 已变化",
    # 授权失效须重新判断 —— 不能 Task/授权批准了就什么都能做。
    fp_problem = None
    if perm_has_state and perm_rec and perm_rec.get("fingerprint"):
        req_fp = req.get("action_fingerprint") or req.get("fingerprint") or ""
        if req_fp and perm_rec["fingerprint"] != req_fp:
            fp_problem = "授权绑定 fingerprint 不匹配: Action 已变化, 须重新判断"
            auth_valid = False
    # A-2: 一次性授权 (one_time) 语义 —— 已 CONSUMED 必须重新判断
    one_time = perm_has_state and bool(perm_rec and perm_rec.get("one_time"))
    already_consumed = perm_has_state and perm_status_ok is False \
        and bool(perm_rec and perm_rec.get("status") == "CONSUMED")
    # PERM-01/修复: expiry 必须真正参与授权决策。过期授权视为无效，
    #   需重新确认(ask)，绝不静默 allow。
    expired = False
    expiry_problem = None
    if auth_expiry:
        try:
            _exp = str(auth_expiry).strip()
            # 统一为 UTC aware datetime 比较，避免 naive/aware 冲突(P2 收敛)。
            if _exp.endswith("Z"):
                _exp = _exp[:-1] + "+00:00"
            elif _exp.endswith("z"):
                _exp = _exp[:-1] + "+00:00"
            elif len(_exp) == 19 and " " in _exp:
                _exp = _exp.replace(" ", "T")
            _exp_dt = datetime.fromisoformat(_exp)
            if _exp_dt.tzinfo is None:
                # naive expiry(无时区)按 UTC 理解，保持确定性。
                _exp_dt = _exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= _exp_dt:
                expired = True
                expiry_problem = "authorization 已过期: expiry=" + str(auth_expiry)
        except ValueError:
            # 无法解析的 expiry 在安全上按“视为有效但提醒”；避免误拦截合法授权。
            expiry_problem = "authorization expiry 无法解析: " + str(auth_expiry)
    if expired:
        auth_valid = False
    authorized_effective = auth_valid and scope_ok

    # 决策
    if level == 4:
        decision = "deny"
        reason = "L4 Prohibited: 禁止操作"
    elif level == 3:
        decision = "allow" if authorized_effective else "ask"
        reason = "L3 High impact: 需显式审批" if not authorized_effective else \
            ("L3 已授权" if scope_ok else "L3 authorized 但 " + scope_problem)
    elif level == 2:
        decision = "allow" if authorized_effective else "ask"
        reason = "L2 External impact: 需确认" if not authorized_effective else \
            ("L2 已授权" if scope_ok else "L2 authorized 但 " + scope_problem)
    elif level == 1:
        if cls["no_scope_warning"]:
            decision = "ask"
            reason = "L1 但无明确 Scope, 需确认"
        else:
            decision = "allow"
            reason = "L1 Prepare: 可逆本地操作"
    else:
        decision = "allow"
        reason = "L0 Observe: 只读操作"

    # PHASE 1: unknown action → 不进 allow (至少 ask; L0/L1 未知默认 deny)
    if cls["unknown_action"] and decision == "allow":
        decision = "ask" if level >= 1 else "deny"
        reason = "未知动作, 保守处理: " + reason

    # A-2/A-3: 一次性授权语义: 若本次是 one_time 且允许, 返回 consumed 标记,
    # 由执行层成功后调 consume_permission 落 CONSUMED (Action 用尽须重新判断)。
    fp_bound = perm_has_state and bool(perm_rec and perm_rec.get("fingerprint"))
    one_time_effective = one_time and decision == "allow"

    # A-3 fix: 决策审计留痕 (append-only JSONL)。记录"谁、何时、允许了什么"。
    decision_made = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": action,
        "level": cls["level"],
        "decision": decision,
        "reason": reason,
        "authorized_flag": bool(authorized),
        "status": perm_rec.get("status") if perm_has_state else None,
        "one_time": one_time,
        "fp_bound": fp_bound,
        "fp_problem": fp_problem,
        "scope_ok": scope_ok,
        "expired": expired,
    }
    _audit(decision_made)

    return {
        "decision": decision,
        "level": cls["level"],
        "reason": reason,
        "requires_approval": cls["requires_approval"],
        "reversibility": cls["reversibility"],
        "authorization": {
            "valid": auth_valid,
            "expired": expired,
            "expiry_problem": expiry_problem,
            "scope_ok": scope_ok,
            "scope_problem": scope_problem,
            "source": auth_source,
            "scope": auth_scope,
            "expiry": auth_expiry,
            "status_ok": perm_status_ok,
            "status_problem": perm_status_problem,
            "fp_bound": fp_bound,
            "fp_problem": fp_problem,
            "one_time": one_time,
            "one_time_consumed": one_time_effective,
            "already_consumed": bool(already_consumed),
        },
        "native_policy_final": True,  # OpenClaw 原生 policy 仍是最终拦截
    }


def main():
    parser = argparse.ArgumentParser(description="Permission Security L0-L4 分类器")
    sub = parser.add_subparsers(dest="cmd")

    pc = sub.add_parser("classify", help="动作分类")
    pc.add_argument("action", help="动作名 (read/send/delete/...)")
    pc.add_argument("--resource-type", default="internal")
    pc.add_argument("--side-effect", default="NONE")
    pc.add_argument("--scope")

    pk = sub.add_parser("check", help="完整授权检查")
    pk.add_argument("--json", required=True, help="request JSON 或 -")

    args = parser.parse_args()
    if args.cmd is None:
        parser.print_help()
        return

    if args.cmd == "classify":
        print(json.dumps(classify(args.action, args.resource_type,
                                  args.side_effect, args.scope),
                         ensure_ascii=False, indent=2))
    elif args.cmd == "check":
        if args.json == "-":
            req = json.load(sys.stdin)
        else:
            req = json.loads(args.json)
        print(json.dumps(check(req), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()