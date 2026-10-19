# Design

## Context

See proposal.md for motivation. The current state constraining the approach:

- **Contracts exist and are proven.** `law-drafting-clarification-loop` (complete) shipped the report schema, the strict validator, the prompt contract in all three prompt files, and the headless driver plus deterministic fake (`scripts/clarification_driver.py`, 12/12 green). The pi side binds to these; it invents no new handoff.
- **Pi's extension API covers every integration point.** Verified against pi 1.1.0 docs: `registerCommand()` for `/draft-law`, `registerTool()` with `outputSchema` + `structuredContent` for the report tool, `turn_end` / `agent_before_settle` continuation guards (the docs warn verbatim: "Guard continuation conditions because an unconditional continuation can loop"), `ctx.ui` / `ctx.hasUI` for the UI/no-UI split, and skills for instruction-only guidance ("use an extension when a workflow needs tools, commands, event handlers ... rather than instructions alone").
- **In-repo placement is decided.** The package lives in `pi/` and moves atomically with `prompts/` and `schemas/`; `pi install ./pi` project-locally plus `.pi/settings.json` trust.

## Goals / Non-Goals

**Goals:**

- The product loop runs as code the repo owns, checkable to the same standard as the headless driver.
- Every loop rule in `docs/clarification-loop-pi-contract.md` has a concrete owner in the package.

**Non-Goals:**

- No model or credential management (pi-side configuration, deliberately undecided as in the prior change).
- No changes to the schema, validator, gate behavior, framework, or headless driver — the package calls them. The only prompt edits are the four errata lines decision 11 names, reconciled to gate-plus-frozen-set evidence; `check.py` changes only if the gate is found to under-enforce.
- No second report shape: `structuredContent` carries exactly what the validator accepts.

## Decisions

**1. `/draft-law` owns the loop (Option A).** The command owns the loop as code,
with validator-plus-gate as the exit condition, but the mechanism splits by
mode — found during implementation, not assumed up front. pi -p executes the
input and exits: queued messages never pump without the interactive event
loop (probed: three delivery modes, zero entries processed). So interactive
runs kick off in the handler and consume passes in agent_end (pi's own
plan-mode pattern: sendMessage({triggerTurn}) + react), while headless runs
execute synchronously inside the handler with nested streamSimple calls
declaring the report tool and executing its calls in-handler via the same
executeReport. Both paths share one decision core and one handoff shape —
the tool call, strict-validated — never parsed prose. *Alternative B
(skill-driven conversation):* rejected — convergence would be model
self-declared, the failure mode the loop exists to prevent. *Alternative C
(conversational loop + settle guard only):* rejected as the primary
mechanism — the guard fires at settle-time only, leaving the middle of the
loop unowned. The command mirrors `clarification_driver.py` pass-for-pass,
which is what makes decision 8 ("empty report means the same thing in CI
and in-session") literally true.

**2. The skill holds guidance only.** Capability-vs-kind judgment and what good grounding looks like live in `skills/drafting.md`; the skill advises passes and never drives iteration. This follows pi's own extension-vs-skill split.

**3. Fresh-pass context for answers.** Each re-extraction renders the prompts anew with the accumulated answers appended as context, mirroring the driver. *Alternative (accumulate conversation):* rejected — stale grounding lingers in-context and bloats long loops; a self-contained pass is re-runnable and matches what CI proves.

**4. Settle guard as backstop, not driver.** An `agent_before_settle` handler refuses to settle while a report is non-empty or invalid, or while an asked step is being re-asked. It exists so a conversational detour mid-loop cannot present a draft as complete even if the command's own flow is bypassed.

**5. Plain directory package, no npm deps.** `pi/` holds extension sources plus the skill; installed via `pi install ./pi` project-locally. *Alternative (full npm package):* rejected — the package shells out to repo scripts and needs no dependencies; packaging ceremony would buy nothing.

**6. `pi -p` branches on UI presence.** With `ctx.hasUI` false, the command writes drafts plus the strict report and exits non-zero, never inventing answers. Same rule as the driver's 3.2, same exit semantics.

**7. Testing split: contracts always, e2e when keyed.** The credential-free Python suite stays the always-on floor; `pi -p` end-to-end runs of the real command (scripted answers, real model) run only with a credential and skip otherwise — pi's own `test.sh` convention.

**8. Tool results return content blocks, pinned by self-test.** A keyed drill proved `executeReport` returning a bare string crashes the host renderer (`content.some is not a function`) after the handoff already validated and executed — jiti never typechecks, so the mismatch was invisible until a live run. The fix is blocks-shaped content matching the gate tools' convention, plus a self-test asserting the exact shape the harness renderer consumes (not just details/structuredContent). The drill ran on host 1.3.0 while the package was written against 1.1.0 docs; the e2e re-proves the handoff on the installed host, and the host version is recorded alongside.

**9. Inline drafts plus hash acks (no by-ref).** The drill showed a model condensing the 60KB Lean rather than risk a typo'd paste — a real integrity smell. *Alternative (path + sha256 references, tool reads files):* rejected — the handoff stops being self-contained, report and files can diverge, and the Python driver would have to mirror the convention. Instead drafts stay inline and each result quotes a sha256 per draft, so receipt and integrity are confirmable distinctly from render success.

**10. passId echo for idempotent receipts.** The tool accepts an optional caller `passId` and echoes it in details and content. *Alternative (separate validate_handoff dry-run tool):* rejected — heavier surface for the same need. The driver records the last consumed passId in loop-state (node-importable, unit-tested); a redelivered passId is logged as a duplicate receipt and opens no second question round, so diagnostics traffic can never masquerade as passes.

**11. Prompt errata reconciled to gate-plus-frozen-set.** Three `prompts/onto-v2.md` lines vs reviewed evidence: (a) the at-least-functional list demands `ph:status`, which the frozen `mayor-2027` omits while passing and `check.py` never mentions — soften the prompt line, gate is the source of truth; (b) the `ph:hasTime` line says `gfo-core:timeOf`, while the frozen ontology (ll. 62–95, with rationale) deliberately subproperties `gfo-core:hasTime`, timeOf being the inverse — fix the prompt line; (c) add a one-line modality rubric (should-vs-may) and state the per-pass file list (`populationTtl` optional, unauthored passes omit it). *Alternative (tighten the gate to the prompt):* rejected — the frozen set passing is the evidence; the prompt was stale.

## Risks / Trade-offs

- **[Risk] The model never converges.** A law whose steps resist grounding loops through the pass budget. → Mitigation: a max-pass budget plus the no-progress guard stop the run non-zero with drafts plus report written, exactly like the driver — a stalled loop is evidence, not a hang.
- **[Risk] Shell-out failures look like gate findings.** The wrapper tools exec repo scripts; a crash (missing `uv`, broken env) must not read as "gate refused". → Mitigation: wrappers distinguish execution failure (tool error, stop) from gate refusal (named finding, reported); the validator runs in-process where possible.
- **[Risk] Skeleton drift between the two drivers.** The TS command and the Python driver mirror the same rules. → Mitigation: both stay thin over the shared enforcers (schema, validator, gate); a rule too clever to mirror in either is pulled down into the enforcers instead.
- **[Risk] Question fatigue on under-covered laws.** A law far from the shared vocabulary asks a lot. → Mitigation: owned by the prompts (positive threshold, 4.3's nothing-asked check), not by this package; the package asks exactly what the report contains, no more.
- **[Trade-off] E2e coverage depends on a key holder.** CI without a credential proves contracts but never the real command wiring. Accepted: pi's own convention, and the wiring is thin by construction.
- **[Risk] Host renderer drift across pi versions.** The package was written against 1.1.0 docs and first ran live on 1.3.0, where the string-content crash surfaced. → Mitigation: the self-test pins the result shape the harness consumes, and the credential-gated e2e re-proves a clean handoff on the installed host with the version recorded; a host upgrade that breaks e2e is a signal to re-pin, not to redesign.

## Migration Plan

Additive only, plus four surgical prompt-line edits: new `pi/` directory, new `.pi/settings.json` trust entry, install docs. Rollback is removing the directory plus reverting the prompt lines. Verify by: `pi install ./pi` from a clean checkout, `/draft-law` converging `mayor-2027` with scripted answers, `pi -p` exiting non-zero on an unanswered run, and the credential-free suite still green.

## Open Questions

None that change specs, approach, or tasks. Model choice and credential holder stay pi-side configuration, as previously deferred.
