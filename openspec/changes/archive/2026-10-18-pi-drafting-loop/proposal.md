# Proposal

## Why

The clarification loop's contracts are specified and proven headlessly, but the product loop itself does not exist yet. `law-extraction` (as amended by `law-drafting-clarification-loop`) requires generation to be iterative and driven by a pi session — today there is no session command, no schema-bound report tool, and no question UI, so every draft is still produced by hand-pasting rendered prompts. The loop is specified but unrunnable.

## What Changes

- **A `/draft-law` session command owns the loop as code.** Render, extract, validate the report, run the gate over the world fixture; while the report is non-empty, put the steps to the author as questions and re-extract with the answers. Terminate only on an empty report plus a passing gate.
- **A `report_ungroundable_steps` tool binds the project-owned schema** (`schemas/clarification-report.schema.json` via `outputSchema`), returning drafts plus `structuredContent`. Free-text output is not a handoff.
- **Headless `check`/`build`/`freeze` wrapper tools** so the session calls the repo's own gate rather than reimplementing it.
- **A drafting skill holding guidance only** (capability-vs-kind judgment, what good grounding looks like) — it advises passes, it never drives iteration.
- **A settle backstop**: an `agent_before_settle` guard that refuses to settle while a report is non-empty or invalid, or while an asked step is being re-asked.
- **`pi -p` writes-and-exits**: with no UI, write drafts plus the strict report and exit non-zero, never inventing answers.
- **Credential-gated e2e**: the real command loop is tested end-to-end only when a credential exists (skipped otherwise, per pi's own convention); the always-on floor stays the credential-free Python driver plus fake.
- **Handoff hardening (live-session findings).** A keyed drill run proved the loop guides good decisions but the handoff plumbing failed: the report tool returned `content` as a plain string while the host renderer consumes content blocks, so a valid converged handoff crashed after executing. The tool now returns blocks, quotes per-draft sha256 ack receipts, and echoes an optional caller `passId` so redelivery never opens a second question round — drafts stay inline (self-contained handoff), hashes ride alongside.
- **Prompt errata reconciliation (live-session findings).** Three `prompts/onto-v2.md` lines drifted from reviewed evidence: the at-least-functional list demands `ph:status` the frozen law omits while passing; the `ph:hasTime` line says `gfo-core:timeOf` while the frozen ontology deliberately subproperties `gfo-core:hasTime` (timeOf is the inverse); modality adjudication (should-vs-may) and the per-pass file list are under-specified. Reconciled in favor of the gate plus the frozen set.

## Capabilities

### New Capabilities

- `pi-drafting`: the pi-side drafting loop — session command owning iteration, schema-bound report tool, gate wrapper tools, question UI, no-progress continuation guard, `pi -p` writes-and-exits behavior, and the credential-gated e2e testing rule.

### Modified Capabilities

None. `law-extraction` already requires pi-driven iteration; this change builds the side of that contract that lives in pi. No requirement text changes.

## Impact

- New in-repo `pi/` package directory (extension sources + skill), installed project-locally via `pi install ./pi` and trusted through `.pi/settings.json`. Moves atomically with `prompts/` and `schemas/` — no cross-repo pinning.
- No changes to `scripts/`, `schemas/`, `framework/`, or gate behavior. Surgical edits to four `prompts/onto-v2.md` lines only (status list, hasTime grounding, modality rubric, per-pass file list), reconciled to what the gate enforces and the frozen set demonstrates; `check.py` is read as the source of truth and changes only if the gate is found to under-enforce.
- Requires a pi model credential at *use* time (like any pi session); CI without one still proves everything the repo owns.
