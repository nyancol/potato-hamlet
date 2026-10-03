# Proposal

## Why

Potato Hamlet needs player-written laws (e.g. the mayor election process) to become executable guidance in-game via the Spirit of the Hamlet, not just prose. This change is Phase 1 of two: it turns one governance text into a GFO-light ontology plus Lean-encoded first-order-logic rules plus a queryable oracle, proving the law-to-artefacts half of the constitution-to-enforcement loop. Phase 2 (`law-simulation-tui`) builds the generic TUI consumer on top of the frozen artefacts produced here.

## What Changes

- Define a **law-to-simulation framework contract**: GFO-light ontology profile, `Nat`-day time model, ECA (Event-Condition-Action + holder) metamodel with a Lean-decidable and Python-evaluable FOL subset, OWL-Lean mirror-by-name correspondence, and the Python/Lean runtime interface (snapshot JSON, verdict JSON, oracle CLI protocol).
- Build **Step 1 (B-wired) extraction harness**: `law.txt` variant in, LLM-assisted draft `ontology.ttl` + `rules.lean` out, with machine checks (`lake build`, OWL parse/consistency) and a human review gate producing frozen artefacts. Optimized for fast iteration over law flavors.
- Build the **Lean oracle for the mayor law** (4-year cycle from 2027-01-12, announce Jan 2, prepare Jan 11, polls Jan 12 9am-7pm, fallback authority = oldest person, tie-break = oldest candidate): snapshot JSON I/O, ECA conditions as Bool/Prop twins with agreement theorems, compiled `list`/`check` exe returning per-citizen pending plus violations-with-witnesses.
- Establish Lean-as-oracle discipline: Python owns state and transitions; Lean owns truth (Prop/Bool twins + agreement theorems, executable checks over snapshots).

## Capabilities

### New Capabilities

- `law-framework`: the artefact contract (ontology profile, time model, ECA metamodel + FOL subset, correspondence rules, snapshot/verdict/oracle protocol).
- `law-extraction`: the assisted law.txt-to-artefacts pipeline with checks and review gate.

### Modified Capabilities

None — greenfield project, no existing specs.

## Impact

- New Lean library surface under `potato-hamlet-lean/` (mayor oracle exe: snapshot/JSON I/O, ECA conditions as Bool + Prop twins, winner/tie-break/authority functions).
- New artefact layout `artefacts/<case>/{law.txt, ontology.ttl, rules.lean, manifest.yaml}` plus a versioned LLM prompt template for Step 1.
- Phase 2 (`law-simulation-tui`) consumes the frozen artefacts and oracle binary produced here; no Python TUI surface in this change.
- Dependencies: Lean 4 toolchain (already pinned via `lean-toolchain`), `Lean.Data.Json`, OWL parse/consistency tooling (rdflib or equivalent for checks only).
