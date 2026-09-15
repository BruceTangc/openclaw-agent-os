# Agent OS v2 Implementation Status

## Complete in architecture layer
- one-Skill v2 entrypoint
- four core protocols
- multi-agent learning protocol
- stable contracts and JSON schemas
- capability registry and native adapter boundary
- OpenClaw capability ownership matrix
- native-first / supersession protocol
- v1.3 migration map
- A1-A8 acceptance specification
- dependency-free static architecture gate + CI workflow

## Intentionally not duplicated
No Agent OS runtime, scheduler, task DB, memory DB, context engine, agent router/orchestrator, communication bus, permission runtime or skill mutation runtime is introduced.

## Remaining before stable v2 release
These require execution against an installed OpenClaw runtime rather than repository-only architecture work:
1. bind adapter to the concrete OpenClaw APIs/events available in the target installation;
2. run A1-A8 end-to-end with real main/root, permanent specialist and ephemeral subagent sessions;
3. validate native Memory/USER writeback and Workshop proposal/apply behavior;
4. validate scope isolation across at least two permanent agents;
5. run native-supersession simulation against adapter implementation;
6. only after PASS, retire v1.3 modules and promote v2 to stable/main.

Do not claim runtime acceptance before these E2E tests have actually run.
