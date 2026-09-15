# Agent OS v2 — executable OpenClaw E2E

This directory is the executable runtime harness. `tests/acceptance-v2.md` remains the normative Runtime Acceptance Specification; it is not itself executable.

## Truth boundary

The harness drives a **real installed OpenClaw CLI**. It does not implement an Agent OS runtime, mock OpenClaw, or turn static CI into fake runtime proof.

A scenario result is one of:
- `PASS`: the configured command ran and the scenario's observable assertions passed.
- `FAIL`: real OpenClaw ran but an observable assertion failed.
- `BLOCKED`: the required executable/capability was unavailable or timed out.

The default runtime adapter is:

```bash
openclaw agent --message "<scenario prompt>" --json
```

If the installed OpenClaw build requires a specific agent/session/CLI shape, override only the driver command, not scenario semantics:

```bash
export OPENCLAW_E2E_COMMAND='openclaw agent --agent main --message {prompt} --json'
python tests/e2e/run.py --scenario A9
```

PowerShell:

```powershell
$env:OPENCLAW_E2E_COMMAND='openclaw agent --agent main --message {prompt} --json'
python tests/e2e/run.py --scenario A9
```

Run all scenarios:

```bash
python -m pip install jsonschema
python tests/e2e/run.py --model-label strong
```

Run the required weak/strong model matrix separately by pointing OpenClaw/the driver at the desired model and preserving a distinct `--model-label`:

```bash
python tests/e2e/run.py --model-label weak
python tests/e2e/run.py --model-label strong
```

Results are written under `tests/e2e/results/*.json` with raw stdout/stderr as evidence. Do not commit credentials or sensitive trajectories; sanitize before publishing results.

## Important limitation

The first harness version uses deterministic observable assertions over real OpenClaw output. It deliberately does **not** accept the tested agent's self-declared `PASS` as sufficient proof. Some behavioral scenarios ultimately need stronger environment fixtures or an independent evaluator; until those exist, a passing textual assertion is evidence for that scenario run, not proof of universal model behavior.

A17 is an environment eligibility check. A34 executes real JSON Schema validation. A1–A16 and A18–A33 are runtime behavior probes. Native memory/subagent/Workshop scenarios should be strengthened with concrete fixture adapters as OpenClaw exposes stable machine interfaces; do not invent private APIs in this repository.