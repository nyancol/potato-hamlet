# Proposal

## Why

Phase 2 builds the one generic TUI, and this rewrite exists because the original plan predates two breaking changes to the artefact contract and would produce a consumer that contradicts the durable specs.

The original `law-simulation-tui` artifacts were written on 2026-09-27. `eca-apply-transitions` was archived on 2026-10-02 and stated that `apply` is the single enforcing path and that drivers "SHALL NOT implement rule semantics themselves" — its own Impact section named this change as the downstream consumer to fix. Yet this change's `design.md` still lists "Lean-as-stepper; transitions stay in Python" as a non-goal, its `tasks.md` still says "Implement Python-side action application", and its spec delta says the TUI applies transitions "in Python". Applying it as written would put two specs in direct contradiction over who owns transitions, and would reimplement guards that Lean already enforces.

The second breakage is larger. `election-cycle-history` made the knowledge graph the snapshot and declared that a vote act in a new law would need graph-shaped handling; `framework-invariants-and-verdict-contract` then fixed the clock, the verdict's result channel, and the witness shape, all of which this change's spec predates. Its requirement to load "ontology individuals + labels" also predates the split of the ontology into a frozen schema plus a separate seed, so the loader it describes no longer matches the artefact layout.

Beyond correcting the drift, the framework work settled questions this change needs answers to: how the guide renders a process tree when phases overlap, how it displays several processes unfolding at once and lets a citizen act in the context of one or the other, and where the line falls between what the guide derives from the artefacts and what it asks Lean.

## What Changes

- Build the generic TUI against the current artefact contract: the knowledge graph as snapshot, `apply` as the only transition path, the graph-as-snapshot round trip, and the split of `ontology.ttl` (frozen schema) from `population.ttl` (seed instances).
- Drive the display from three sources kept deliberately separate: the declared process hierarchy and calendar bounds for what the law says will happen, the Lean verdict for what is true now, and the graph for what has happened. The guide derives no phase and no authority rule of its own.
- Render the process tree, including phases that overlap rather than a linear step sequence, and report each phase's window from its calendar span without computing dates.
- Display every process instance that is initialised, ongoing, or finished, so concurrent processes are visible at once, and let the user act in the context of a chosen process when the selected citizen holds duties on more than one.
- Send every transition to `oracle apply` on the citizen's explicit confirmation and adopt the returned graph wholesale, appending a log entry. The guide never applies a transition, advances a phase, or proclaims a result on its own.
- Use the manifest's declared parameters, holder roles, modalities, and reading templates to render duties, so a law needing an unfamiliar act is displayable without code change, and use the verdict's structured witnesses to explain blocks.
- Prove the law-swap claim by loading `mayor-quorum` into the unmodified TUI binary, exercising the repeat election that exists only in that flavour.

**Deliberately not changed:** no `tick` verb and no per-law code. The guide writes the clock, which is the one write it owns, and everything else goes through `apply`.

## Capabilities

### New Capabilities

- `law-simulation`: the generic TUI guide that loads any conforming artefact set and walks a citizen through the lifecycle of every process it unfolds.

### Modified Capabilities

None — `law-framework`, `law-extraction`, and `process-lifecycle-vocabulary` are prerequisites whose requirements this change consumes without changing. The `law-simulation` spec this change previously proposed is replaced rather than amended, since its requirements were written against the superseded contract.

## Impact

- New Python package surface under `src/potato_hamlet/`: Textual application, artefact loader with freeze-mark and ECA-id refusal, graph-backed runtime pool, async single-worker oracle client, and the display layer driven by declared parameters and reading templates.
- New runtime dependencies: Textual, and an RDF toolkit for reading `ontology.ttl` and `population.ttl`.
- Consumes, does not produce: frozen `artefacts/<case>/` sets and the compiled oracle binary. No `rules.lean` change and no oracle rebuild.
- Depends on `framework-invariants-and-verdict-contract` and `process-lifecycle-vocabulary` both landing first.
- Replaces the artifacts previously in this change directory; the September `design.md`, `tasks.md`, and spec delta are superseded and should not be applied.