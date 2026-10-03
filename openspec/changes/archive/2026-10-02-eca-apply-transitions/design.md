# Design

## Context

See proposal.md (Why) for motivation. Current state: both artefact sets ship a compiled oracle speaking `list`/`check` over cold-spawn stdio (`potato-hamlet-lean/OracleMain.lean`); `rules.lean` holds conditions, holders, and verdicts but no transition function (`repeatFresh` in the quorum rules is the only pure `Snapshot → Snapshot` function, and nothing calls it). Constraints carried forward: Nat-day time, mirror-by-name, Prop/Bool twins, stateless cold-spawn CLI, freeze covers `rules.lean`, `check` stays advisory.

## Goals / Non-Goals

**Goals:**
- Action semantics single-sourced in Lean, executable through the existing oracle binary shape.
- Rejection reasons double as guide messages (no separate error catalog).
- Property-testable transitions (`#eval` traces + small theorems) without the TUI.

**Non-Goals:**
- Lean-as-stepper for sequencing (clock advance, act selection, multi-act scripts stay in the driver).
- Changing `check` verdicts or the snapshot schema; the envelope reuses both.
- Warm/long-lived oracle protocol; `apply` is cold-spawn like `check`.

## Decisions

1. **`Act` inductive + `FromJson`, one `apply` dispatch returning `Except String Snapshot`.** Per-ECA functions (`applyAnnounce` … `applyProclaim`, `repeatAfterVoid` generalizing `repeatFresh`) guard with the same `?` conditions `check` uses, so precondition truth has one source. Alternative (Boolean success flag) rejected: the `String` error is the guide's block explanation for free.
2. **Envelope `{"act": ..., "snapshot": ...}` on stdin for the `apply` verb.** Single-stdin cold-spawn keeps the protocol uniform with `check` (no argv-vs-stdin split, no two-file plumbing). Alternative (act as argv + snapshot on stdin) rejected: envelopes compose and log as one JSON line.
3. **`apply` enforces, `check` advises, driver owns custody.** The driver (Phase 2 TUI now, scripts today) holds the stored snapshot, sends acts, and stores returned snapshots; it never branches on rule logic. Alternative (Python mirrors transitions, Lean cross-checks) rejected per the confirmed direction: dual implementation drifts silently.
4. **No Lean-side sequencing.** No "run full election" function; each `apply` is one act. Multi-act playbooks are driver scripts calling the binary repeatedly. Alternative (script interpreter in Lean) rejected: sequencing policy (who clicks what when) belongs to the guide layer.
5. **Transition properties as theorems where cheap** (e.g. `applyVote` appends exactly one box entry, touches nothing else; `applyPrepare` yields `AllDistributed`; double `announce` errors). Full functional-correctness proofs per transition deferred — agreement-theorem discipline stays at the condition level for this change.

## Risks / Trade-offs

- [Risk] `apply` and `pendingOf` disagree (act allowed but never listed pending, or vice versa) → Mitigation: conformance test per ECA (pending act applies clean; non-pending act rejects) in `test_oracle.py`.
- [Risk] Envelope doubles per-act subprocess cost → Mitigation: same cold-spawn budget as `check`; prototype snapshots are small; batching deferred.
- [Risk] Re-freeze churn (both sets change `rules.lean`) → Mitigation: single re-freeze at the end; freeze covers the new sections automatically.
- [Trade-off] `Except String` errors are unstructured → Accepted; structured witness-on-rejection (e.g. which guard with bindings) is a later refinement if the guide needs it.

## Migration Plan

Greenfield extension, no live users. Order: `Act`/`apply` in both `rules.lean` → `cmdApply` in `OracleMain.lean` → rebuild both oracles → extend `test_oracle.py`/`test_quorum.py` with apply traces → update `artefacts/README.md` → re-freeze both sets. Rollback: previous oracle binaries keep serving `list`/`check`; `apply` callers fail loudly on old binaries (unknown verb, exit 2).

## Open Questions

None.
