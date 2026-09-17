# Native Integration Boundary

Agent OS v2 RC3 is a prompt/instruction Skill, not an executable adapter runtime. `capability-registry.json` is therefore a declarative ownership/boundary registry; it is **not** proof that a capability exists in the running OpenClaw installation.

During an eligible turn, use only native capabilities that OpenClaw actually exposes. If identity, memory, Workshop/self-learning, approval, sandbox, task, delegation, or other capability availability cannot be established, do not claim it ran: degrade conservatively and use `UNKNOWN` where appropriate.

Instruction-level binding responsibilities:
- interpret exposed native agent/session/task/delegation provenance;
- use exposed native memory persist/recall without creating an Agent OS memory database;
- hand governed evolution candidates to native Workshop/self-learning only when that facility is actually available;
- inherit native approval/security controls rather than implementing a permission runtime;
- never infer lifecycle-wide visibility from Skill eligibility.

A future executable adapter/plugin is justified only if OpenClaw requires a lifecycle hook that a Skill cannot receive. Such an adapter must remain thin and must not recreate sessions, tasks, memory, scheduling, multi-agent routing, security, or Workshop.

Do not branch core semantics on OpenClaw release strings. Prefer capability evidence from the running environment and fail closed when critical governance or identity information is ambiguous.
