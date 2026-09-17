# Agent OS v2 Quick Start

Install:

```bash
openclaw skills install git:BruceTangc/openclaw-agent-os@agent-os-v2
```

Verify:

```bash
openclaw skills info agent-os
openclaw skills check
```

Then use OpenClaw normally. There is no Agent OS setup conversation.

A practical smoke test is to give the agent a task with an observable success criterion, then a correction. Expected behavior: it does not equate tool success with task success; it verifies the requested outcome; it treats the correction as high-value evidence; if OpenClaw native memory/self-learning is available it uses the native path rather than an Agent OS database; it does not globally spread an agent-specific lesson.

For multi-agent testing, delegate a task where a child can succeed but integration can fail. Expected: child PASS can coexist with delegation/user-outcome FAIL.
