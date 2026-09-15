# Agent OS v2 Repository Instructions

Keep Agent OS as one OpenClaw Skill and an adaptive learning layer, not a parallel runtime. OpenClaw owns runtime, sessions, tasks, multi-agent routing, subagents, memory, context, tools, approvals, automation and Workshop application. Agent OS owns Verification, Experience, Evolution and Governance semantics.

Changes must preserve zero-config installation, native-first behavior, multi-agent scope isolation, `Tool success != User outcome success`, and safe degradation when native capabilities are absent.

Run `python scripts/validate_v2.py` for repository static validation.
