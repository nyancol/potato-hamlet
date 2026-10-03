# Design

## Context

See proposal.md (Why) for motivation. Current state: greenfield repo with an empty Python package (`src/potato_hamlet/`), a skeleton Lean 4 project (`potato-hamlet-lean/`, toolchain v4.34.1), Textual not yet added, no OWL tooling, no artefact layout. Explore-mode decisions constrain the approach: B-wired pipeline with a review gate between Step 1 and Step 2, Nat-day time, obligations as Lean-only predicates, mirror-by-name OWL-Lean correspondence, Lean-as-oracle with Python owning state.

## Goals / Non-Goals

**Goals:**
- One framework contract that makes "new law runs on unmodified TUI" testable (contract defined here, TUI built in Phase 2).
- Fast law-flavor iteration: edit `law.txt`, regenerate, diff, review.
- Oracle verdicts carry witnesses so a future guide can explain blocks, not just failures.
- A compiled mayor oracle exe that answers `list`/`check` over snapshot JSON.

**Non-Goals:**
- Full auto-translation (no-human C pipeline); human review gate stays.
- Lean-as-stepper (Lean computing next state); transitions stay in Python (Phase 2 consumer) for this approach.
- Real calendar dates, timezones, or GFO `Chronoid` arithmetic; Nat days only.
- The Textual TUI itself; that is Phase 2 (`law-simulation-tui`).
- Spirit as actor: the guide observes and advises, never decides or acts.
- Multiplayer/networked simulation; single-user local simulation.

## Decisions

1. **Subprocess oracle over Lean-export or dual implementation.** TUI shells out to the compiled per-law oracle binary with snapshot JSON, reads verdict JSON. Alternative (parse Lean in Python) rejected as brittle; alternative (export ECA JSON ahead of time) rejected because it duplicates rule truth and can drift. Mitigates drift by keeping one executable source of rule truth.
2. **Prop/Bool twins + agreement theorems per FOL rule.** Each rule has a `Prop` (the logic) and a `Bool` (the executable check) with a proved equivalence, so `lake build` certifies what the oracle answers. Alternative (Bool only) rejected: loses the FOL statement the ontology work grounds.
3. **Mirror-by-name + IRI identity.** Lean type names equal OWL class short names; snapshot ids equal full OWL individual IRIs. No codegen bridge in this change. Alternative (URI fields only where needed) folded in: `uri`-style id is exactly the snapshot id convention.
4. **`manifest.yaml` hand/LLM-written for prototype, oracle `list` for discovery.** Manifest carries display names and oracle binary path for the Phase 2 consumer; oracle answers truth. Alternative (Lean-export manifest from day one) deferred as non-goal codegen.
5. **Cold-spawn oracle per check.** Each `check` spawns the compiled oracle binary fresh (snapshot JSON in, verdict JSON out, process exits). Keeps the oracle stateless and the protocol trivial to test. Alternative (warm long-lived stdin/stdout process) rejected for the prototype: faster per tick but needs message framing and error recovery. Async single-worker client remains a Phase 2 concern on top of cold-spawn.
6. **Framework docs live with artefacts, not in code.** `artefacts/<case>/` layout plus versioned prompt template under repo; contract text in `specs/law-framework` after archive.
7. **Oracle advises, humans decide.** The oracle reads snapshots and reports (phase, pending per holder, failed conditions with witnesses, would-win counts); it never applies a transition and names no verdict final. Winner/count outputs read as "shows X would win" until the owning citizen performs the proclaim act. Alternative (oracle auto-advances or proclaims) rejected: the Spirit guides players, it makes no decisions in the process.
8. **Quorum-repeat second flavor (locked).** The second flavor is `artefacts/mayor-quorum/`: baseline mayor text plus "the election is valid only if at least half of the citizens cast a vote; otherwise a new election is held 30 days later." The repeat recomputes all prep dates relative to the new election date (announce at E-10, prepare at E-1, polls 9am-7pm on E-day) and reruns the full prep cycle (nomination, ballot creation/distribution) with a reset registry and ballot set. This stresses aggregation (quorum counting) plus relative-date recurrence. Alternative (lottery tie-break) deferred to a later flavor.

## Risks / Trade-offs

- [Risk] FOL subset too small for real laws ("fair", "reasonable") → Mitigation: quorum/tie-break flavors in prototype explicitly probe the ceiling; out-of-subset rules fail loudly at review, not silently.
- [Risk] Manifest drifts from Lean truth → Mitigation: review gate checks ECA id match between manifest and oracle `list`; TUI refuses mismatched sets.
- [Risk] Per-tick subprocess latency → Mitigation: compiled binary (not `lake env lean`), small snapshots (<50 citizens in prototype); cold-spawn measured first, warm protocol only if a later change proves it necessary.
- [Risk] LLM redrafts rename classes, inflating review cost → Mitigation: prompt pins naming + ECA shape; diff review is structural by construction.
- [Risk] OWL open-world vs Lean closed-world mismatch (missing ballot vs unknown) → Mitigation: explicit closure at snapshot build (snapshot enumerates the full finite population); documented in framework spec.
- [Trade-off] Python transitions duplicate Lean action semantics → Accepted for prototype; oracle checks preconditions so illegal moves are rejected even though `apply` lives in Python.

## Migration Plan

Greenfield: no migration. Rollout order: framework contract text → Step 1 harness + mayor baseline artefacts frozen → oracle exe builds. Phase 2 (`law-simulation-tui`) then loads the frozen sets. Rollback is artefact-level: unfreeze by deleting the review mark; consumers refuse unfrozen sets.

## Open Questions

None.
