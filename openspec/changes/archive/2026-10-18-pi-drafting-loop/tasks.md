# Tasks

The product loop as code the repo owns: every rule lands with its test beside it, and the credential-free suite stays green throughout.

## 1. Scaffold the in-repo package

- [x] 1.1 Create `pi/` with the extension entry point plus install docs, `pi install ./pi` project-locally, and verify pi lists the package and `/draft-law` appears as a command
- [x] 1.2 Record trust via `.pi/settings.json` and verify a clean checkout installs without manual approval steps beyond the documented one

## 2. The report tool and the gate wrappers

- [x] 2.1 Ship `report_ungroundable_steps` bound to `schemas/clarification-report.schema.json` via `outputSchema`, returning drafts plus `structuredContent`, and verify a scripted call delivers structured data the validator accepts while prose-only output does not parse as a report
- [x] 2.2 Ship `check`/`build`/`freeze` wrapper tools that exec the repo scripts, distinguishing execution failure (tool error) from gate refusal (named finding), and verify a wrapper run against `mayor-2027` reports the gate's verdict verbatim
- [x] 2.3 Document both tools' contracts alongside `docs/clarification-loop-pi-contract.md` and verify the documented call shapes run as written

## 3. The `/draft-law` command loop

- [x] 3.1 Build the pass skeleton — render via `redraft.py --json`, extract via the model plus report tool, validate in-process, run the gate wrapper over the world fixture — and verify one pass against `mayor-2027` produces drafts plus a validated report with no credential beyond the model itself
- [x] 3.2 Add the question round: while the report is non-empty present each fresh step via the session UI, keep the asked-set, feed answers back as fresh-pass context, and verify a scripted two-pass run asks once per step and converges when the report empties
- [x] 3.3 Enforce convergence in code: terminate only on empty report plus passing gate, refuse invalid reports by re-extracting, and verify a run fed a prose-only pass re-extracts instead of terminating
- [x] 3.4 Add the no-progress guard plus pass budget: never re-ask an asked step, record the stall and stop non-zero, and verify a scripted stalled run stops with each step asked exactly once

## 4. Skill, settle backstop, and headless behavior

- [x] 4.1 Ship `skills/drafting.md` with guidance only (capability-vs-kind judgment, what good grounding looks like, the positive threshold) and verify it contains no loop-driving instructions
- [x] 4.2 Add the `agent_before_settle` backstop refusing to settle on a non-empty or invalid report or a re-asked step, and verify a session bypassing the command cannot present an unconverged draft as complete
- [x] 4.3 Branch `pi -p` on UI presence: write drafts plus the strict report and exit non-zero while entries remain, never inventing answers, and verify exit codes on an unanswered versus a converged scripted run

## 5. Prove the whole loop

- [x] 5.1 Drive `/draft-law` against `mayor-2027` with scripted answers to a converged, gate-passing draft, and verify the draft passes the repo gate
- [x] 5.2 Drive a credential-gated end-to-end test of the real command (scripted answers, real model; skips with no key) and verify it runs in a keyed environment and skips cleanly without one
- [x] 5.3 Run the full credential-free suite (`test_clarification_loop.py`, `test_shared_vocabulary.py`, gate checks) and verify everything still passes with the package installed

## 6. Handoff hardening and prompt reconciliation (live-session findings)

- [x] 6.1 Return content blocks from `executeReport` (never a bare string), fix the local result interface to match the host's blocks shape, and extend the self-test to assert the exact content shape the harness renderer consumes — then verify the self-test is green
- [x] 6.2 Quote one sha256 per delivered draft in result details and content text, and verify the self-test recomputes each hash against the delivered bytes
- [x] 6.3 Accept an optional caller `passId` in the report tool and echo it in details and content; track the last consumed passId in loop-state with a redelivery helper, and verify a repeated `passId` is logged as a duplicate receipt that opens no second question round
- [x] 6.4 Reconcile the four `prompts/onto-v2.md` errata to gate-plus-frozen-set evidence (drop `ph:status` from the at-least-functional list; `gfo-core:hasTime` for `ph:hasTime`; one-line should-vs-may rubric; per-pass file list with optional `populationTtl`), change `check.py` only if the gate is found to under-enforce, and verify the frozen `mayor-2027` set plus the full credential-free suite still pass
- [x] 6.5 Re-prove the handoff live on the installed host (1.3.0): credential-gated e2e green with a clean handoff and no renderer crash, host version recorded alongside
