# State Model

Canonical semantic states:
- planned
- ready
- active
- waiting
- blocked
- completed
- failed
- cancelled

Rules:
- `completed` requires verification for consequential work.
- `failed` requires evidence of failure.
- `blocked` means progress requires an external dependency/decision.
- `waiting` means work is intentionally paused for a known condition.
