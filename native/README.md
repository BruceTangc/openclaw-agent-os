# Native Integration Boundary

`capability-registry.json` records semantic ownership. Concrete OpenClaw API/tool/plugin names belong in adapters, not core protocols.

Adapter responsibilities:
- resolve native agent/session/task/delegation provenance
- expose memory persist/recall targets without creating an Agent OS memory DB
- submit governed evolution candidates to native Workshop/self-learning when supported
- map governance approval requirements to native approval/security facilities
- report capability support FULL/PARTIAL/NONE

Adapters MUST fail closed on ambiguous identity for scope promotion and on unavailable critical governance enforcement. They may degrade to local evidence capture when safe.

Do not branch core behavior on OpenClaw release strings.