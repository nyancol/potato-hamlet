# Spec Delta

## MODIFIED Requirements

### Requirement: Law variant input layout

Each law variant SHALL live under `artefacts/<case>/` with `law.txt` as the single source text, plus generated `ontology.ttl`, `rules.lean`, and `manifest.yaml`, plus `population.ttl` holding the individuals the law starts from. `ontology.ttl` SHALL hold only classes and properties; seeded individuals SHALL live in `population.ttl` in the same RDF serialisation, and individuals created during simulation SHALL be minted into the runtime knowledge graph. `population.ttl` describes what the law permits and not how the oracle works out a moment: it SHALL NOT carry a value whose purpose is to let a consumer reproduce a computation the oracle owns, and SHALL NOT state what an interval is measured from. The TUI SHALL be built only against frozen (reviewed) artefact sets, never against drafts.

#### Scenario: New flavor scaffolded
- **WHEN** an author adds `artefacts/mayor-quorum/law.txt` with a quorum-validity plus 30-day-repeat clause
- **THEN** the harness generates draft artefacts under the same directory without touching the frozen mayor baseline or the TUI

#### Scenario: Seeds live outside the ontology
- **WHEN** a law starts from named citizens and named calendar points
- **THEN** `ontology.ttl` declares the classes and properties describing them and `population.ttl` holds the individuals in RDF, so the frozen ontology stays a schema and no bespoke seed-to-instance mapping is needed

#### Scenario: A seed states no method
- **WHEN** a law fixes an interval such as a repeat delay
- **THEN** `population.ttl` records the interval once as `ph:gapDays` on the calendar node bounding the phase, and says nothing about how the resulting moment is derived, because that computation belongs to the oracle and reproducing it in the seed would make the seed a second source for it

#### Scenario: A seed value the oracle never reads is rejected
- **WHEN** a draft seeds a property that duplicates a constant the oracle holds in its own rules, such as an interval kept on a process instance
- **THEN** the review gate fails naming the property and the individual, since a value no condition consults is a description of nothing the law permits

### Requirement: Machine checks before human review

Drafts SHALL pass `lake build` (Lean, including Prop/Bool agreement theorems) and OWL parse plus consistency checks before reaching the human gate, with failures fed back as diagnostics. The checks SHALL verify the framework-invariant declarations and their GFO grounding, verify that every `ph:` property is grounded in GFO — by being a subproperty of a GFO property, or by declaring a GFO class as its domain or range — and that any property grounded neither way is named in a published exemption list, verify that every Process class is reachable from a declared root through `ph:hasPhase`, verify that no Process class is orphaned, verify that every manifest `eca_process` appears in the declared hierarchy, verify that every declared phase is marked by a `ph:CalendarSpan`, verify that no accepted act removes an individual from the graph, by applying each ECA in turn and confirming every prior subject survives, verify that no ordering relation appears between two declared phases, verify that every `ph:causedBy` relation has a Process subject and a `gfo-core:State` object and states a permitted dependency rather than an evaluated one, verify `population.ttl` parses as RDF and that every subject in it is typed by a declared class, verify each manifest ECA id against `oracle list` and each declared `eca_process`, `holder_role`, and parameter role against the ontology, verify that the instance graph round-trips through `check` and `apply` without divergence, and verify that `check` and `apply` remain total over clock values outside the law's calendar.

The checks SHALL also verify the runtime contract the graph now carries. They SHALL verify that `ph:atHour` and `ph:dayIndex` are grounded on `gfo-light:TimeBoundary` and that no individual outside that category carries either, so a law cannot keep a second copy of the present on a process instance. They SHALL verify that every property the oracle re-encodes is declared `owl:FunctionalProperty`, and that after each accepted act no subject holds two values for a declared functional property, so an accumulation cannot be mistaken for a re-encoding. They SHALL verify that a minted IRI is not already present encoding a different fact, and that no individual of one Process class is written under another occurrence's IRI. They SHALL verify that the clock is the only individual carrying the current position, and that a law does not write it. They SHALL verify seed parity: driving a walk and collecting every property any guard reads, a seeded individual carrying a `ph:` property outside that set fails, since a value no condition consults duplicates the oracle's own arithmetic rather than describing what the law permits. They SHALL verify transformation acts: an ECA declaring the individuals it acts on is checked against the graph for each state it is offered in, an act whose declared input is absent is refused naming it, and a Role individual is checked to relate both a `ph:roleIn` and a `ph:playedBy`, with no individual holding the same Role twice in one situation. An individual acquiring a new class mid-run is a failure, since meaning is a relation and not a change of type. They SHALL verify totality of the graph: after a walk of accepted acts, every verdict is reproducible from the returned graph alone, so nothing a law decides lives only inside the oracle. And they SHALL verify that the clock is treated as monotone, by setting it to an earlier moment after a period has closed and confirming the period does not reopen and no act is admitted into a finished process.

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

#### Scenario: A second copy of the present caught
- **WHEN** a draft carries `ph:dayIndex` or `ph:atHour` on an individual that is not a `gfo-light:TimeBoundary`
- **THEN** the gate fails naming the subject and the property, since a consumer would otherwise have to know which of several positions is the current one

#### Scenario: Missing functional declaration caught
- **WHEN** a draft re-encodes a property on every act without declaring it `owl:FunctionalProperty`
- **THEN** the gate fails naming the property, because a reader could not tell a re-encoding from a second value

#### Scenario: Accumulation caught
- **WHEN** after an accepted act a subject holds two values for a declared functional property
- **THEN** the gate fails naming the subject and the property, so a bound or a flag can never be read as whichever value was written last

#### Scenario: IRI collision caught
- **WHEN** a draft brings a fact into existence under an IRI that is already present encoding a different fact
- **THEN** the gate fails naming the IRI and the individual already there, since every type check passes on a collision and only the freshness rule catches it

#### Scenario: A law that writes the clock caught
- **WHEN** a law's `apply` returns a `ph:Clock` whose position differs from the one sent
- **THEN** the gate fails, since advancing time has exactly one writer and an act must be able neither to move nor to erase the clock

#### Scenario: Totality of the graph verified
- **WHEN** the gate walks a law's accepted acts and then reproduces every verdict from the returned graph alone
- **THEN** each verdict matches, so no fact a condition reads is reachable only from inside the oracle

#### Scenario: Clock monotonicity verified
- **WHEN** the gate sets the clock back to a moment before a period a law has closed and re-runs `check` and `apply`
- **THEN** the period does not reopen and no act is admitted into the finished process, so totality is not mistaken for licence to contradict a recorded moment

#### Scenario: Unread seed value caught
- **WHEN** a draft's `population.ttl` carries a property that its guards never consult
- **THEN** the gate fails naming the property and the individual, so a value that duplicates the oracle's own arithmetic cannot be frozen in beside it

#### Scenario: An act acting on nothing caught
- **WHEN** a draft's action transforms individuals it does not declare as its inputs, so the graph need not contain them
- **THEN** the gate fails naming the act, because an act that can proceed without its inputs present is an act that creates what it should have found

#### Scenario: A role without both ends caught
- **WHEN** a draft's `apply` returns a Role individual that relates to a context but not to the individual holding it, or the same individual holds one Role twice in one situation
- **THEN** the gate fails naming the individual, since a meaning is only readable as a relation between a holder and a situation

#### Scenario: A type changing mid-run caught
- **WHEN** an individual's declared class differs between its first and its later appearance in a walk
- **THEN** the gate fails naming the individual, because meaning is a relation and a class that changes with progress makes the graph unreadable at a fixed point

#### Scenario: The transformation check reports before it fails
- **WHEN** a frozen law's action still creates individuals it does not declare as inputs, because it predates the requirement
- **THEN** the gate reports the act as non-compliant and names it, without refusing to load the set, so the requirement can land before the laws that meet it