# Design

## Context

See proposal.md (Why) for motivation; see `specs/law-simulation/spec.md` for the normative requirements, and the two prerequisite changes for the artefact contract this consumes. Three properties of that contract shape the approach.

The knowledge graph is the snapshot. `check` and `apply` take typed instance triples and `apply` returns the whole graph to replace wholesale, so the TUI never holds a parallel state object and never reads a bespoke JSON schema per law. Identity is one IRI space across the seed, the graph, and the verdict.

Sequencing and causality are in different places. The ontology's declared `ph:hasPhase` hierarchy says what a process is made of, calendar `Chronoid` bounds say when each part runs, and Lean's ECA conditions say what triggers what. No artefact carries a causal relation. This means the guide can render structure and schedule from the artefacts but can never render truth from them.

Holders are read, never computed. `pending` names the citizen and the process instance for each duty, and the manifest declares each ECA's `holder_role` and parameters. Nothing in the framework says who holds a duty when no office is filled — each law decides in Lean — so the guide has no fallback rule to implement and no way to get it wrong.

## Goals / Non-Goals

**Goals:**
- One binary runs any conforming artefact set, proven by law swap rather than asserted.
- Show every process unfolding, concurrently, with its phases, windows, and progress.
- Keep the boundary between what the guide reads and what it asks Lean unambiguous.
- Never leave the user unsure why something is blocked.

**Non-Goals:**
- Deriving phase, authority, or readiness. Those are verdict readings.
- Editing law artefacts, or any authoring surface.
- Multiplayer or networked simulation. Single-user, local.
- Auto-playing lawful moves on a citizen's behalf.

## Decisions

**1. Three display sources, never mixed.** Structure comes from the declared hierarchy; schedule comes from calendar bounds; currency comes from the verdict; history comes from the graph. The tempting shortcut is to compute "is this window open" in the guide by comparing a span's bounds to the clock, since all the inputs are present. Rejected: the moment the guide derives phase it is a second source for a fact Lean owns, which is the divergence the graph-as-snapshot decision removed. The guide may *display* bounds and the oracle's phase; it may not reconcile them. Where they appear to disagree, that is a bug to surface, not to resolve.

**2. Render a tree, not a stepper.** The obvious TUI shape is a wizard: step 1 of 6, now step 2. It is wrong here, because phases overlap — the nomination window covers days 0 through 10 while announce is day 0 and prepare is day 9, so nomination is concurrent with both. A linear stepper would have to either misrepresent the law or flatten concurrency into an arbitrary order. The guide therefore shows each process as a container with its phases listed, each carrying its window from the calendar span and its own status, letting concurrency be visible as concurrency. *Alternative considered:* a timeline or Gantt view as the primary display. Rejected as the default — good as an on-demand view, wrong as the spine, since the user's question is usually "what can this person do now" rather than "when does everything happen".

**3. Show all live processes, and make the process a selection.** With the election and a budget period unfolding at once, one citizen can hold a duty on each. The requirement to group duties under processes means the process becomes something the user selects, alongside the citizen: selecting a citizen shows every duty they hold, each tagged with its process, and selecting a process narrows to that one. This is what lets a person act "in the context of" a process rather than against an undifferentiated list. *Alternative considered:* auto-selecting the most urgent process. Rejected — choosing what is most urgent is a judgement, and a judgement about whose duty matters is exactly what the guide must not make.

**4. Every transition goes through `apply`, and the graph is adopted wholesale.** The guide sends an act on explicit confirmation and replaces its graph with what comes back, refusing to commit if any returned subject is undeclared. This is the corrected reading of the superseded plan, which had Python apply transitions. The practical consequence is that the guide's only local mutation is the clock. *Alternative considered:* a local optimistic update followed by reconciliation. Rejected — it reintroduces a second state representation and a divergence path, and the actions are infrequent enough that waiting on a subprocess is not felt.

**5. Async single-worker client, no clock round trip.** Cold-spawning a ~122 MB binary is expensive, so checks and acts run off the UI thread through one worker with coalescing, and clock advance stays local because advancing time is a simulation control rather than a rule. The boundary is worth stating as a rule the code can be checked against: the guide writes the clock, and nothing else. *Alternative considered:* an `oracle tick` verb for symmetry. Rejected — the clock is the most frequent interaction in the app, and putting it behind a subprocess makes the core interaction feel broken.

**6. The manifest drives every widget.** Each ECA declares its `holder_role`, its parameters with a `source` of `selected` or `choices`, its modality, and its message; each reading declares a template. The guide builds its UI from those declarations, so a law with a new act is displayable without code. `choices` is what makes multi-instance processes workable: the pending entry names the process instance, and any parameter sourced from `choices` renders as a picker whose options come from the verdict. *Alternative considered:* inferring widgets from ECA ids and parameter names, which is what `scripts/test_conformance.py` does today. Rejected — that is per-law code, and the whole point of the manifest declarations is that it no longer is.

**7. Blocks are explained, not just reported.** A verdict's structured witness gives the individuals under `refs` and the counts under `counts`, so the guide can say "blocked: 1 of 40 ballots undelivered — Cara's ballot for Bob" or "quorum failed: 3 of 7 voted" rather than a bare condition name. Where a witness resolves to graph individuals, their labels come from the graph by IRI, which is the same lookup path as everywhere else. *Alternative considered:* passing Lean's `detail` string through. Rejected as insufficient on its own — it is a display string, and the guide should not be the thing that parses English to recover counts.

**8. Accept that two laws are not yet enough.** Multi-process display is the requirement most likely to be under-tested, since both shipped laws declare one process type. The honest position is to state the requirement now, implement against the declarations, and treat the second law as the test. A display that looks right with one process and quietly drops the grouping when a second appears is the failure mode to watch for.

## Risks / Trade-offs

- **[Risk] The guide looks correct with one process and breaks with two**, since grouping duties by process instance has no coverage until a second law exists. → Mitigation: build the grouping from the declared and verdict-attributed data rather than inferring it, and treat the second law as a required test rather than a follow-up.
- **[Risk] Whole-graph round trips make every check grow with the graph**, so a long session degrades. → Mitigation: one in-flight check with coalescing keeps the UI responsive regardless, and the artefact-side cost is a deliberate deferral owned by the prerequisite change.
- **[Risk] Declared windows and oracle phase can disagree**, and the guide has been told not to reconcile them. → Mitigation: surface the disagreement explicitly as a display warning instead of silently picking one, so a contract bug is visible rather than papered over.
- **[Risk] Freezing the artefact set is a load-time gate, and a stale set would make the guide speak from unreviewed rules.** → Mitigation: refuse to load on a freeze mismatch or an ECA-id mismatch against `oracle list`, naming the offending files.
- **[Trade-off] No clock verb means the guide owns one piece of state.** Accepted: it is a single framework-fixed field, and keeping it out of the subprocess keeps the most frequent interaction responsive.
- **[Trade-off] Three display sources is more plumbing than one.** Accepted deliberately — collapsing them would recreate the two-representation problem the prerequisite changes exist to remove.

## Migration Plan

Greenfield consumer. No data migration and no compatibility shim, since nothing outside this change consumes the TUI. Rollback is binary-level: the previous build keeps working against unchanged frozen sets.

## Open Questions

- Whether an undeclared or partially-loaded artefact set should be offerable in a read-only "inspect the law" mode, where no `apply` is possible and the guide shows only the declared structure and calendar. It would make authoring considerably easier and cannot violate the no-decisions rule, but it introduces a mode where the guide displays a plan with no truth behind it.
- Whether to persist the graph between sessions, and in what form. The graph is the whole state, so a session save is the state; whether the seed plus a log of acts reconstructs it exactly, or whether the graph itself must be saved, depends on whether `apply` is deterministic, which no requirement currently states.