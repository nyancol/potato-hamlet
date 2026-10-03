# Tasks

## 1. Framework-invariant declarations

- [x] 1.1 Bump the ontology prompt to v2 declaring `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint`, `ph:CalendarSpan`, and `ph:label` with their GFO superclasses and subproperty grounding (`ph:atDate` under `gfo-core:dateTimeValue`; `ph:age`, `ph:atHour`, `ph:dayIndex` under `gfo-core:decimalValue`), and forbidding individuals in `ontology.ttl`
- [x] 1.2 Apply the invariants to `artefacts/mayor-2027/ontology.ttl` and `artefacts/mayor-quorum/ontology.ttl`, reducing both to a TBox, and verify OWL parse plus GFO grounding passes with every framework class grounded
- [x] 1.3 Extract seeded individuals into `artefacts/<case>/population.ttl` for both cases and verify every seeded citizen carries a label and an age and that no individual remains in either `ontology.ttl`
- [x] 1.4 Add to the ontology prompt the grounded relationship vocabulary (`ph:hasPhase`, `ph:hasParticipant`, `ph:hasTime`, `ph:relates`, `ph:containsRole`, `ph:qualityOf`, `ph:causedBy`, `ph:roleIn`, `ph:playedBy`), requiring the generated ontology to declare each Process class's constituents through `ph:hasPhase` as class-level assertions
- [x] 1.5 Add to the ontology prompt an explicit prohibition on `leadsTo`, `resultsFrom`, `causes`, and `causedBy` as *ordering* relations, naming calendar bounds for sequencing and Lean conditions for causality
- [x] 1.6 Extend the prompt's stability rule to state that a redraft SHALL NOT reshape the declared process hierarchy, and verify a regenerated draft keeps the hierarchy when only a term length changes
## 2. Relationship vocabulary and the wire format

- [x] 2.1 Define the instance-triple wire format shared by `check` and `apply`, and verify it round-trips `population.ttl` through a Python RDF round trip with no loss of subject, predicate, or object
- [x] 2.2 Declare the framework relationship properties with `rdfs:subPropertyOf` grounding in both ontologies, naming `ph:roleIn` and `ph:playedBy` as `ph:` properties so the grounding rule has no unnamed escape
- [x] 2.3 Declare each Process class's constituents through `ph:hasPhase` in both ontologies, and verify OWL parse and GFO grounding pass with every declared property following its GFO counterpart
- [x] 2.4 Resolve the vestigial declarations: map `ph:DistributeBallots` to an ECA or remove it, and either populate or drop `ph:outcome`
- [x] 2.5 Instantiate the five `gfo-core:State` subclasses in both ontologies as the situations a process moves through, and verify each verdict `phase` value resolves to a declared State class by IRI
- [x] 2.6 Add a `ph:hasTime`-to-`Chronoid` lifecycle to at least one seeded process instance in `population.ttl`, with `temporallyStartedBy` absent to exercise the initialised state, and verify a consumer reports it as awaiting its trigger
- [x] 2.7 Declare `ph:causedBy` in both ontologies as a subproperty of `gfo-core:causedBy`, and declare at least one `ph:causedBy` with a Process subject and a State object, whose affected process can also be reached without the State holding, so structure and evaluation are separately observable

## 3. The graph as snapshot

- [x] 3.1 Rework `artefacts/mayor-2027/rules.lean` to derive its typed state from the instance graph instead of a bespoke JSON snapshot, and verify a full 2027 cycle still resolves end to end
- [x] 3.2 Rework `artefacts/mayor-quorum/rules.lean` the same way, representing the ongoing and void election instances as individuals of one Process class distinguished by `temporallyFinishedBy`, and verify the repeat chain still appends preserving prior instances
- [ ] 3.3 Replace positional ordering with declared ordering properties on process instances and calendar points, and verify no rule still depends on list position to find the current instance
- [ ] 3.4 Verify `apply` returns a whole graph that replaces the stored one, and that a returned subject typed by an undeclared class is rejected before any write is committed
- [x] 3.5 Support a law minting `ph:CalendarPoint` and `ph:CalendarSpan` individuals into the runtime graph during `apply`, carrying the same declared properties as seeded ones with dates computed only by Lean, and verify the quorum repeat's new election resolves a date through a minted span
- [x] 3.6 Update `scripts/snapshot_roundtrip.py`, `scripts/test_oracle.py`, `scripts/test_quorum.py`, and `scripts/test_conformance.py` to the graph wire format and verify all three suites still pass

## 4. Act parameter and holder-role declarations

- [x] 4.1 Bump the manifest prompt to v2 adding `holder_role`, `params[]` (name, role, source drawn from `selected`/`choices`), and a `readings` block, and verify a regenerated draft carries them
- [x] 4.2 Declare `holder_role` and `params` for every ECA in both manifests using Role classes the ontology declares as participants of that ECA's Process, and verify every ECA's parameters are readable from the manifest alone
- [x] 4.3 Remove the hardcoded parameter table from `scripts/test_conformance.py` so acts are derived from declared parameters plus verdict choices, and verify the suite still drives every pending act to a clean apply

## 5. Verdict result channel

- [x] 5.1 Replace `wouldWin` with a generic `readings` list in both rule sets, carrying a law-chosen id, a kind from `decimal`/`ref`/`flag`, and a value, with `ref` naming the ontology class, and verify a law with no result emits no placeholder entry
- [x] 5.2 Add parameter slots to `pending` in both rule sets carrying the choices available at that instant, and verify a pending vote entry names the candidates selectable by the acting citizen
- [ ] 5.3 Add the process instance IRI to each `pending` entry in both rule sets, and verify a duty resolves to the instance it belongs to in both the flat and cycle-history shapes
- [ ] 5.4 Verify a duty on a multi-instance process type takes a parameter sourced from `choices` over the open instances, and that an act naming a chosen instance is accepted while one naming an unknown instance is rejected with a named guard
- [x] 5.5 Give violations a structured witness of `refs` and named `counts`, replacing the flattened `witnessCitizen`/`witnessCandidate` fields, and verify the quorum failure reports voted and total as counts rather than only inside `detail`
- [ ] 5.6 Declare a `readings` block (id, class, label, template) in both manifests covering every reading the oracle emits, and verify no emitted reading lacks a declaration

## 6. Review gate

- [x] 6.1 Assert the framework-invariant class declarations and their GFO grounding in `scripts/check.py`, and verify a law omitting `ph:CalendarPoint` now fails the gate where it previously passed vacuously
- [x] 6.2 Assert `population.ttl` parses as RDF with every subject typed by a declared class and every seeded citizen carrying label and age, and that `ontology.ttl` declares no individuals
- [x] 6.3 Assert every framework relationship property is grounded in GFO — by subproperty, or by a GFO domain/range — with a published exemption list for anything grounded neither way, and verify an ontology declaring an ungrounded, unexempted relationship fails naming it
- [x] 6.4 Assert every Process class is reachable from a declared root through `ph:hasPhase`, and verify `ph:DistributeBallots` in its current state would have been caught
- [x] 6.5 Assert no Process class is orphaned — referenced by no root, no phase, and no manifest `eca_process` — and verify a law that declares an unreferenced Process fails
- [x] 6.6 Assert every declared phase is marked by a `ph:CalendarSpan` carrying `ph:marksPhase`, and verify a phase with no span fails naming it
- [x] 6.7 Assert no ordering relation appears between two declared phases, with the diagnostic directing the author to the calendar bounds, and verify a planted phase-to-phase ordering triple fails
- [x] 6.8 Assert every `ph:causedBy` has a Process subject and a `gfo-core:State` object, rejecting a Process-to-Process or reverse-direction relation, and verify both a planted Process-to-Process triple and a reversed one fail
- [x] 6.9 Cross-validate manifest ECA ids against `oracle list` and `eca_process`/`holder_role`/`params[].role` against the ontology, and verify a manifest naming a role the ontology does not declare is refused with the mismatch named
- [x] 6.10 Add a clock-totality check running `check` and `apply` against the compiled oracle over day and hour values far outside the law's calendar, and verify both oracles return well-formed results
- [x] 6.11 Add a graph round-trip check sending the seeded graph through `apply` and a fresh `check`, verifying every returned subject is declared-typed and that re-checking reproduces the same verdict

## 7. Cancellation semantics

- [x] 7.1 Apply every ECA of both laws in turn and assert subject monotonicity: no accepted act removes an individual from the graph, and every subject present before an act is still present after it, failing with the act and the removed individual named
- [x] 7.2 Verify a process instance finished with an outcome that does not count its contributions retains every individual it accumulated, and that recording non-count is the only lever available over a past fact
- [x] 7.3 Verify a process terminating at a moment inside one of its calendar spans records that finish bound on its `Chronoid` with no new vocabulary, and that the finished instance reads identically to one ending on a calendar point
  - Every clause verified except the WHEN as worded: a finish at day 12 hour 14 (not a declared calendar point) against day 10 hour 19 gives a bound on the Chronoid, a plain `gfo-light:TimeBoundary` carrying both `ph:dayIndex` and `ph:atHour`, no undeclared predicate, and a structurally identical graph. No shipped law can finish *inside* a span -- both endings are guarded behind polls closing, and every span ends at a polls-close point -- so the WHEN is recorded as an artefact gap under the scenario in `specs/law-framework/spec.md` rather than asserted as tested. See 3.5, which delivers the minting the scenario's own motivating law shape would need.

## 8. Freeze, docs, and validation

- [ ] 8.1 Rebuild both oracles and re-freeze both artefact sets, and verify `scripts/freeze.py --verify` passes for each case
- [ ] 8.2 Verify `scripts/test_oracle.py`, `scripts/test_quorum.py`, and `scripts/test_conformance.py` still pass, confirming the work touched no rule semantics beyond the wire format
- [ ] 8.3 Rewrite the protocol and verdict sections of `artefacts/README.md` against the compiled oracle, covering the graph wire format, `readings`, the structured witness, the relationship vocabulary, and that sequencing lives in the calendar while `ph:causedBy` states a permitted dependency the Lean guard evaluates, and verify every documented field name matches actual output including the optional `check [file]` argument
- [ ] 8.4 Run `openspec validate framework-invariants-and-verdict-contract --type change --strict` and verify the planning artifacts are complete and consistent
