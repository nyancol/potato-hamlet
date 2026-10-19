# Tasks

## 1. Foundation and dependencies

- [x] 1.1 Add Textual and an RDF toolkit to `pyproject.toml`, and verify a minimal application boots with `python -m potato_hamlet`
- [x] 1.2 Implement artefact-set loading that reads `ontology.ttl` as schema, `population.ttl` as seed, and `manifest.yaml` as display declarations, and verify loading the mayor set yields labelled citizens, roles, and the declared process hierarchy
- [x] 1.3 Implement freeze-mark verification and ECA-id agreement against the oracle's `list`, and verify an edited set is refused with the offending files named

## 2. Graph custody and the oracle client

- [x] 2.1 Implement the runtime knowledge graph loaded from the seed, with label resolution by IRI and a single pool for seeded and minted individuals, and verify every subject resolves a label by IRI
- [x] 2.2 Implement the async single-worker oracle client taking the whole graph and returning verdict or rejection, with one in-flight check and coalescing, and verify the interface stays responsive while a check is in flight
- [x] 2.3 Implement `apply` handling that sends the act envelope, adopts the returned graph wholesale, and refuses to commit any subject typed by an undeclared class, and verify both the clean path and the refusal path
- [x] 2.4 Implement clock advance as the only local state change, and verify the next check reflects the advanced position with no oracle call for the advance itself

## 3. Structure, schedule, and process display

- [x] 3.1 Render the declared process hierarchy from `ph:hasPhase` and each phase's window from its calendar span, and verify the mayor election renders as a tree with day windows read from the artefacts
- [x] 3.2 Render overlapping phases as concurrent with no imposed ordering, and verify the nomination window and announce both show as running on day 0
- [x] 3.3 Display the oracle's `phase` as a reading only, and verify that a disagreement between a declared window and the oracle's phase is surfaced as a warning rather than resolved
- [x] 3.4 Display every process instance distinguished as initialised, ongoing, or finished-with-outcome, and verify a seeded process with no start bound is reported as awaiting its trigger
- [x] 3.5 Implement process selection alongside citizen selection, and verify two concurrently unfolding processes both display and that selecting one narrows the guide to it

## 4. Duties, acting, and blocks

- [x] 4.1 Build the pending-duty list from the verdict with each duty tagged by its process instance, and verify a citizen owing duties on two processes sees them attributed separately
- [x] 4.2 Build every actionable control from the manifest's declared `holder_role`, parameters, modality, label, and message, rendering a `choices` parameter as a picker fed by the verdict, and verify an act the TUI has never seen is still offered
- [x] 4.3 Implement explicit confirmation for acting, append a log entry per applied act, and verify no transition occurs without a confirmed user action
- [x] 4.4 Render block explanations from the verdict's structured `refs` and `counts`, resolving identities to labels through the graph, and verify an undelivered ballot and a failed quorum each report names and figures without parsing the display string
- [x] 4.5 Verify an act the oracle rejects reports its named reason and leaves the graph unchanged

## 5. Guidance discipline

- [x] 5.1 Verify a would-win reading is reported as advisory with the proclaim duty still pending, and that no office changes before the authority confirms the proclaim act
- [x] 5.2 Verify the guide reads duty holders from the verdict and implements no fallback-authority rule of its own, including when no office is filled
- [x] 5.3 Verify the guide makes no priority recommendation when a citizen owes duties on several processes

## 6. Law-swap acceptance

- [x] 6.1 Load `artefacts/mayor-quorum` into the unmodified TUI binary and verify the `repeat` ECA renders and plays, exercising a void cycle followed by a scheduled repeat with no TUI code change
- [x] 6.2 Play a full guided cycle on the mayor baseline from announce through proclaim, and verify the log shows a lawful cycle with the winner proclaimed by oldest-on-tie
- [x] 6.3 Run `openspec validate law-simulation-tui --type change --strict` and verify the planning artifacts are complete and consistent