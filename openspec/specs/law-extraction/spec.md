# law-extraction

## Purpose

Turns a hamlet governance text into reviewed, machine-checked simulation artefacts quickly, so law flavors can be iterated (reword, regenerate, diff, review) before anything downstream depends on them.

## Requirements

### Requirement: Law variant input layout

Each law variant SHALL live under `artefacts/<case>/` with `law.txt` as the single source text, plus generated `ontology.ttl`, `rules.lean`, and `manifest.yaml`, plus `population.ttl` holding the individuals the law starts from. `ontology.ttl` SHALL hold only classes and properties; seeded individuals SHALL live in `population.ttl` in the same RDF serialisation, and individuals created during simulation SHALL be minted into the runtime knowledge graph. The TUI SHALL be built only against frozen (reviewed) artefact sets, never against drafts.

#### Scenario: New flavor scaffolded
- **WHEN** an author adds `artefacts/mayor-quorum/law.txt` with a quorum-validity plus 30-day-repeat clause
- **THEN** the harness generates draft artefacts under the same directory without touching the frozen mayor baseline or the TUI

#### Scenario: Seeds live outside the ontology
- **WHEN** a law starts from named citizens and named calendar points
- **THEN** `ontology.ttl` declares the classes and properties describing them and `population.ttl` holds the individuals in RDF, so the frozen ontology stays a schema and no bespoke seed-to-instance mapping is needed

### Requirement: Assisted generation with pinned prompt

The harness SHALL generate draft artefacts via a versioned prompt template pinned to the framework contract (GFO-light mapping, the framework-invariant classes with their GFO grounding, the grounded relationship vocabulary, the declared process hierarchy, ECA shape, Nat-day arithmetic, mirror-by-name rule, snapshot field naming, and act parameter and holder-role declarations), so redrafts stay structurally comparable. The prompt SHALL require the process hierarchy to be generated from the law text, and SHALL NOT ask for causal or conditional relations, which belong to the Lean conditions.

#### Scenario: Redraft diff is structural
- **WHEN** the mayor law text changes only the term length from 4 to 2 years
- **THEN** the regenerated draft diff shows changed time arithmetic and deadlines, not renamed classes or a reshaped state schema

#### Scenario: Generated artefacts satisfy the framework invariants
- **WHEN** the harness drafts a law that names only a custom process with its own vocabulary
- **THEN** the draft still declares `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint`, and `ph:CalendarSpan` with GFO grounding, and places seeded individuals in `population.ttl`

#### Scenario: Generated ontology carries a hierarchy
- **WHEN** the harness drafts a law whose text describes a process made of named stages
- **THEN** the draft declares each Process class's constituents through `ph:hasPhase` as grounded subproperties of `gfo-core:hasSituationPart`, rather than leaving the process as an unelaborated class

#### Scenario: Prompt requests are verified, not trusted
- **WHEN** a draft omits the `roleIn` and `playedBy` relations the prompt requires
- **THEN** the gate fails naming the missing relation, so an unfulfilled prompt instruction cannot reach the review gate unnoticed

### Requirement: Machine checks before human review

Drafts SHALL pass `lake build` (Lean, including Prop/Bool agreement theorems) and OWL parse plus consistency checks before reaching the human gate, with failures fed back as diagnostics. The checks SHALL verify the framework-invariant declarations and their GFO grounding, verify that every `ph:` property is grounded in GFO — by being a subproperty of a GFO property, or by declaring a GFO class as its domain or range — and that any property grounded neither way is named in a published exemption list, verify that every Process class is reachable from a declared root through `ph:hasPhase`, verify that no Process class is orphaned, verify that every manifest `eca_process` appears in the declared hierarchy, verify that every declared phase is marked by a `ph:CalendarSpan`, verify that no accepted act removes an individual from the graph, by applying each ECA in turn and confirming every prior subject survives, verify that no ordering relation appears between two declared phases, verify that every `ph:causedBy` relation has a Process subject and a `gfo-core:State` object and states a permitted dependency rather than an evaluated one, verify `population.ttl` parses as RDF and that every subject in it is typed by a declared class, verify each manifest ECA id against `oracle list` and each declared `eca_process`, `holder_role`, and parameter role against the ontology, verify that the instance graph round-trips through `check` and `apply` without divergence, and verify that `check` and `apply` remain total over clock values outside the law's calendar.

#### Scenario: Broken draft blocked
- **WHEN** a draft `rules.lean` fails to build or the `.ttl` is inconsistent
- **THEN** the harness reports the diagnostics and marks the artefact set unreviewable until regenerated or fixed

#### Scenario: Missing invariant caught, not passed vacuously
- **WHEN** a draft omits the calendar classes or declares a Process cycle class with no grounding
- **THEN** the gate fails naming the missing declaration instead of passing on the absence of instances to check

#### Scenario: Ungrounded relationship caught
- **WHEN** a draft declares a `ph:` property that is neither a subproperty of a GFO property nor given a GFO domain or range, and is not on the exemption list
- **THEN** the gate fails naming the property, since an ontology whose relationships are invisible to a reasoner cannot be checked

#### Scenario: Type grounding accepted
- **WHEN** a draft declares a `ph:` property whose domain and range are GFO classes but which is not a subproperty of any GFO property
- **THEN** the gate accepts it, because a reasoner still learns the relation's types, and the property need not appear on the exemption list

#### Scenario: Orphan Process class caught
- **WHEN** a draft declares a Process class that no root reaches and no ECA refers to
- **THEN** the gate fails naming it, so a vestigial stage cannot be frozen into an artefact set unnoticed

#### Scenario: Manifest drift caught
- **WHEN** a manifest names an ECA absent from `oracle list`, or a process class, holder role, or parameter role the ontology does not declare for that ECA
- **THEN** the gate fails naming the mismatch, so a manifest cannot drift from the oracle or the ontology

#### Scenario: Ordering relation between phases caught
- **WHEN** a draft ontology or manifest asserts that one phase follows another causally
- **THEN** the gate fails naming the relation and directs the author to the calendar bounds, since sequencing is already derivable and cannot be asserted twice

#### Scenario: Act that erases an individual caught
- **WHEN** an ECA in a draft rule removes an existing individual from the graph
- **THEN** the gate fails naming the act and the individual it removed, so erasure cannot reach a frozen artefact set

#### Scenario: Misdirected causal relation caught
- **WHEN** a draft asserts a causal relation between two Processes, or attaches a `ph:causedBy` with a State as subject
- **THEN** the gate fails naming the relation and its endpoints, directing the author to declare it with the Process as subject and the State it can be caused by as object

#### Scenario: Clock totality verified
- **WHEN** the gate runs against a compiled oracle
- **THEN** it confirms `check` and `apply` return well-formed results for day and hour values far outside the law's calendar

#### Scenario: Graph round-trip verified
- **WHEN** the gate sends the seeded instance graph through `apply` for a no-op-guard act and a fresh `check`
- **THEN** the returned graph is accepted, every subject in it is typed by a declared class, and re-checking reproduces the same verdict, so the oracle and the graph cannot silently diverge

### Requirement: Explicit review gate to frozen

No artefact set SHALL be consumable by the simulator until a human marks it reviewed, freezing the exact file versions. Post-freeze law edits SHALL require a new review.

#### Scenario: TUI refuses drafts
- **WHEN** the TUI is pointed at an artefact set that was edited after its review mark
- **THEN** it refuses to load and names the changed files
