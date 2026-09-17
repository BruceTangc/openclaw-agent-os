# Native-First and Upgrade Protocol

## Rule

Never implement an Agent OS facility before checking whether current OpenClaw Native or an official OpenClaw plugin already satisfies the semantic contract.

## Resolution order

1. OpenClaw Native
2. Official OpenClaw plugin
3. Thin Agent OS adapter, only when an actual integration surface exists
4. Minimal Agent OS fallback, only when unavoidable

RC3 is a prompt/instruction Skill. It has no independent runtime capability detector and no executable Native Adapter. `native/capability-registry.json` is therefore a declarative ownership/boundary registry, not proof that a capability is available in a particular turn.

## Capability audit on every OpenClaw upgrade

1. Inspect current official OpenClaw capabilities and the capabilities actually exposed to the Skill.
2. Diff semantic ownership/expectations against the Capability Registry.
3. Map new/changed capabilities to Agent OS semantic contracts.
4. Run overlap and acceptance tests appropriate to the changed capability.
5. For FULL native equivalence, instruct/delegate through the exposed native facility; deprecate any real Agent OS fallback that exists.
6. Keep one compatibility window only when an actual fallback/adapter exists and migration risk justifies it.
7. Delete a real fallback after compatibility tests pass.
8. Never preserve duplicate code merely for historical ownership.

If availability cannot be established from the current OpenClaw environment, treat it as unavailable/UNKNOWN for that operation. Never infer runtime availability merely from this repository's registry.

## No version coupling

Do not choose behavior solely from release numbers when exposed capability/context can establish the requirement. Version hints may exist only for diagnostics and compatibility reporting.

Because RC3 has no executable capability-discovery API of its own, examples such as `supports("...")` are conceptual contracts, not APIs supplied by Agent OS.

## Change classes

- ADDITIVE_NATIVE: new OpenClaw capability; assess whether any Agent OS fallback/adapter is still needed.
- BEHAVIOR_CHANGE: existing native behavior changed; update instructions/contracts/tests and any real adapter.
- REMOVED_NATIVE: native capability disappeared; prefer an official plugin; add a minimal fallback only if the semantic requirement cannot safely degrade.
- CONTRACT_BREAK: native behavior no longer satisfies an Agent OS semantic contract; isolate the mismatch in the thinnest available integration layer.

## Architecture change threshold

An OpenClaw release must not cause a new Agent OS Core merely because it adds a feature. The four Core model changes only if the underlying learning problem itself changes: verifying reality, deriving experience, improving future behavior, or governing learning/change.
