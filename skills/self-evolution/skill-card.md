## Description: <br>
Self-Evolution (v2) gives OpenClaw Agent OS an Evidence-driven, verifiable, rollback-able evolution controller. It consumes Agent OS Evolution Evidence (Verification/Evaluation/User Feedback/Observation), forms Candidates (recurrence>=3 & sessions>=2), Diagnoses root cause, Proposes minimal changes, gates via Governance, Snapshots before Apply, and Judges via Regression before Promotion/Rollback. <br>

## Publisher: <br>
[brucetangc](https://clawhub.ai/user/brucetangc) <br>

### License/Terms of Use: <br>
MIT-0 <br>

## Use Case: <br>
Operators use this skill when they want an agent to safely and verifiably improve its own behavior over time from repeated, real evidence — not from single failures or noise. <br>

### Deployment Geography for Use: <br>
Global <br>

## What It Is NOT: <br>
- Not a parallel Agent Runtime, Scheduler, Event Bus, or Memory Runtime.
- Not a knowledge graph / vector DB / TF-IDF / PageRank store.
- Not a replacement for Agent OS Verification/Evaluation/Execution Record.

## Known Risks and Mitigations: <br>
Risk: Self-modification could degrade behavior or touch sensitive files. <br>
Mitigation: Regression judges every change (IMPROVED/NO_CHANGE/REGRESSED/UNKNOWN); REGRESSED auto-triggers Rollback from a pre-Apply Snapshot; Regression failure never auto-becomes a new Candidate (anti-loop). <br>
Risk: Permission/Security/Runtime files could be changed. <br>
Mitigation: Protected targets (Permission/Security/Credentials/Secrets/Auth/Approval Rules/Runtime/Infrastructure/Global Authority/AGENTS.md/SOUL.md) are hard-blocked even with explicit --approve; G5/G6 require mandatory human approval. <br>
Risk: Automatic cycles reduce user control. <br>
Mitigation: Default small effective changes; G3+ require review; G5/G6 require human; only IMPROVED promotes. <br>

## Reference(s): <br>
- [Agent OS](https://github.com/BruceTangc/openclaw-agent-os) <br>
- references/evolution-model.md · candidate-policy.md · governance.md · regression-policy.md <br>

## Skill Output: <br>
**Output Type(s):** [text, json] <br>
**Output Format:** JSON status records + governance artifacts under `.agent-os/evolution/` <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** May apply targeted, governed file changes (with Snapshot + Regression + Rollback). <br>

## Skill Version(s): <br>
2.0.0 <br>

## Ethical Considerations: <br>
Users should review proposed changes before Apply, ensure G5/G6 human approval, and verify that Evolution operates under their organization's safety, security, and compliance requirements. <br>
