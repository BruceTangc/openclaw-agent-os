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
import sys
from datetime import datetime

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
    # PERM-01/修复: expiry 必须真正参与授权决策。过期授权视为无效，
    #   需重新确认(ask)，绝不静默 allow。
    expired = False
    expiry_problem = None
    if auth_expiry:
        try:
            _exp = str(auth_expiry).strip().rstrip("Z").replace("Z", "")
            # 兼容带 offset 的 ISO 与纯日期两种格式
            if _exp.endswith("Z") is False and len(_exp) == 19:
                _exp = _exp.replace(" ", "T")
            _exp_dt = datetime.fromisoformat(_exp)
            if datetime.now() >= _exp_dt:
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