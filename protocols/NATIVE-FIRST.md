# Native-First and Upgrade Protocol

## Rule

Never implement an Agent OS facility before checking whether current OpenClaw Native or an official OpenClaw plugin already satisfies the semantic contract.

## Resolution order

1. OpenClaw Native
2. Official OpenClaw plugin
3. Agent OS adapter
4. Minimal Agent OS fallback

## Capability audit on every OpenClaw upgrade

1. Discover current native capabilities.
2. Diff against the previous Capability Registry snapshot.
3. Map new/changed capabilities to Agent OS semantic contracts.
4. Run overlap tests.
5. For FULL equivalence, route through the Native Adapter and mark the fallback DEPRECATED.
6. Keep one compatibility window when migration risk exists.
7. Delete the fallback after compatibility tests pass.
8. Never preserve duplicate code merely for historical ownership.

## No version coupling

Core code must not branch on release numbers when capability discovery can express the requirement. Prefer `supports("skill.propose_change")` over `openclaw >= X`.

Version hints may exist only for diagnostics/compatibility reporting.

## Change classes

- ADDITIVE_NATIVE: new OpenClaw capability; assess fallback supersession.
- BEHAVIOR_CHANGE: existing native behavior changed; update adapter/tests.
- REMOVED_NATIVE: native capability disappeared; official plugin or minimal fallback may be activated.
- CONTRACT_BREAK: semantic behavior no longer satisfies Agent OS contract; adapter isolates the break.

## Architecture change threshold

An OpenClaw release must not cause a new Agent OS Core merely because it adds a feature. The four Core model changes only if the underlying learning problem itself changes: verifying reality, deriving experience, improving future behavior, or governing learning/change.
