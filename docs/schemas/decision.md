# Decision Model

A decision should conceptually contain:
- objective
- candidate action
- expected benefit
- risk
- reversibility
- confidence
- authority level    ← 委托链上生效权限的层级；由 Parent 委托 scope 与 OpenClaw native policy 取小得出，逐层只减不增（见 ACTION-PROTOCOL.md "Multi-Agent 权限委托"）
- evidence
- decision
- reason

Decision outcomes:
IGNORE / OBSERVE / QUEUE / SUGGEST / PREPARE / EXECUTE / ASK / ESCALATE
(另: NOOP≈IGNORE, INFORM≈SUGGEST, ACT≈EXECUTE, DENY 由 Permission-Security 输出)
