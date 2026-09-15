# Evolution Protocol v2

Evolution decides whether accumulated experience justifies a future behavior change. It does not edit skills directly.

## Pipeline
Verified Experience -> repeated/generalizable Pattern -> Hypothesis -> Expected Improvement -> EvolutionCandidate -> Governance -> native OpenClaw learning/Workshop.

A serialized `EvolutionCandidate` follows `docs/CONTRACTS-V2.md` and `schemas/evolution-candidate.schema.json`: target, supporting experience IDs, pattern, hypothesis, expected improvement, proposed change, confidence, risk and status. Reversibility and the post-application verification plan are mandatory governance/application considerations, but are not serialized candidate fields in protocol v2.0.

Targets: AGENT, TEAM, SKILL, WORKFLOW, SHARED_PROTOCOL.

One failure is normally evidence, not a global rule. Prefer the narrowest target/scope that explains the evidence. After native application, regression/outcome verification must generate new evidence. A failed improvement is itself experience.

Actual mutation/application belongs to OpenClaw native Workshop/self-learning/approval facilities when available. If the required native capability is not exposed, keep the candidate unapplied rather than claiming mutation occurred.
