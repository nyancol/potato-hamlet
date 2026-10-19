# law-extraction

## Purpose

Turns a hamlet governance text into reviewed, machine-checked simulation artefacts quickly, so law flavors can be iterated (reword, regenerate, diff, review) before anything downstream depends on them.

## Requirements

### Requirement: Law variant input layout

Each law variant SHALL live under `cases/<case>/` with `law.txt` as the single source text, plus generated `ontology.ttl`, `rules.lean`, and `manifest.yaml`, plus `population.ttl` holding the law-derived individuals the law starts from: its calendar, its process instances, its states and its roles. Individuals the hamlet already has — citizens, physical furniture, supply, and the single shared clock — SHALL NOT be restated there; they are referenced by IRI from the framework's world store, which is populated once before any law is proposed. `ontology.ttl` SHALL hold only classes and properties; seeded individuals SHALL live in `population.ttl` in the same RDF serialisation, and individuals created during simulation SHALL be minted into the runtime knowledge graph. `population.ttl` describes what the law permits and not how the oracle works out a moment: it SHALL NOT carry a value whose purpose is to let a consumer reproduce a computation the oracle owns, and SHALL NOT state what an interval is measured from. The TUI SHALL be built only against frozen (reviewed) artefact sets, never against drafts.

A shared physical vocabulary SHALL be resolvable alongside every case's artefacts, declaring the classes governance texts presuppose — the things a duty is performed on, with, or towards — each subclassed in GFO and carrying `rdfs:label`. It MAY also declare named kinds beneath a capability it already declares, so that a law whose text leaves an instrument open is not made narrower by the file offering kinds: which kinds exist is the world's business, and a law qualifies by the capability rather than by a kind unless its own text names one. It SHALL be a framework artefact in its own right rather than part of any case, so that a concept a law's text presupposes is declared once and every law referring to it refers to the same class. It SHALL be available to every law and required of none: a law whose text presupposes nothing physical SHALL load and pass without drawing on it, and a law SHALL NOT be required to declare, seed, or otherwise account for a concept its duties do not concern.

A law needing a physical concept the shared vocabulary does not declare MAY declare it locally, which is the point at which the two vocabularies diverge and the concept belongs to that law alone. A class a law declares locally that the shared vocabulary also declares SHALL be reported by the review gate naming both, rather than one silently taking precedence. A class referenced from the shared vocabulary SHALL count as declared for every check that requires a subject to be typed by a declared class, so drawing on the vocabulary needs no exemption from the transformation requirement's input check.

#### Scenario: New flavor scaffolded
- **WHEN** an author adds `cases/mayor-quorum/law.txt` with a quorum-validity plus 30-day-repeat clause
- **THEN** the harness generates draft artefacts under the same directory without touching the frozen mayor baseline or the TUI

#### Scenario: Seeds live outside the ontology
- **WHEN** a law starts from a named calendar and named process instances over citizens the world already names
- **THEN** `ontology.ttl` declares the classes and properties describing them, `population.ttl` holds the law-derived individuals in RDF, and the citizens are referenced by IRI from the world store rather than restated, so the frozen ontology stays a schema and no bespoke seed-to-instance mapping is needed

#### Scenario: A seed states no method
- **WHEN** a law fixes an interval such as a repeat delay
- **THEN** `population.ttl` records the interval once as `ph:gapDays` on the calendar node bounding the phase, and says nothing about how the resulting moment is derived, because that computation belongs to the oracle and reproducing it in the seed would make the seed a second source for it

#### Scenario: A seed value the oracle never reads is rejected
- **WHEN** a draft seeds a property that duplicates a constant the oracle holds in its own rules, such as an interval kept on a process instance
- **THEN** the review gate fails naming the property and the individual, since a value no condition consults is a description of nothing the law permits

#### Scenario: World furniture restated in a case is rejected
- **WHEN** a draft's `population.ttl` declares an individual the world store already owns, such as a citizen, a mailbox, or a sheet
- **THEN** the review gate fails naming the IRI, since the world is populated once and a law reaches its furniture by reference rather than by restatement

#### Scenario: A law with no physical duties draws on nothing
- **WHEN** a law's text presupposes nothing physical and its artefacts reference no shared class
- **THEN** the set is freezable and the gate passes, because the vocabulary is available and not required

#### Scenario: One mailbox across two laws
- **WHEN** two laws' texts both refer to a citizen's mailbox
- **THEN** both refer to the same shared class, so a consumer reading either law resolves the same kind of thing and neither law invented a private one

#### Scenario: Offering kinds does not narrow a law that left the choice open
- **WHEN** the shared vocabulary declares named kinds beneath a capability, and a law whose text names no kind of instrument requires that capability
- **THEN** the law's requirement is satisfied by any individual bearing the capability, the gate reports no narrowing, and a hamlet stocked with one kind is not refused an act the law's own text left to the world

#### Scenario: A concept the vocabulary lacks is declared locally
- **WHEN** a law's text presupposes something the shared vocabulary does not declare
- **THEN** the law declares it in its own `ontology.ttl` and the set is freezable, because the shared vocabulary is a stage laws perform on rather than a catalogue of every noun a governance text might use

#### Scenario: A local redeclaration is reported
- **WHEN** a law declares a class locally that the shared vocabulary also declares
- **THEN** the review gate reports the collision naming both declarations, so the divergence is visible rather than resolved silently

#### Scenario: A shared-typed individual satisfies the type check
- **WHEN** a law's act acts on an individual whose class comes from the shared vocabulary
- **THEN** the individual counts as typed by a declared class for every check that requires it, so drawing on the shared vocabulary needs no exemption

### Requirement: Assisted generation with pinned prompt

The harness SHALL generate draft artefacts via a versioned prompt template pinned to the framework contract (GFO-light mapping, the framework-invariant classes with their GFO grounding, the grounded relationship vocabulary, the declared process hierarchy, ECA shape, Nat-day arithmetic, mirror-by-name rule, snapshot field naming, and act parameter and holder-role declarations), so redrafts stay structurally comparable. The prompt SHALL require the process hierarchy to be generated from the law text, and SHALL NOT ask for causal or conditional relations, which belong to the Lean conditions.

The prompt SHALL also ask the author to name the physical concepts the law text presupposes and to draw on the shared physical vocabulary for each one it recognises, declaring a class locally only for a concept the vocabulary does not carry. It SHALL NOT require a concept the law's duties do not concern, so a law with no physical duties is not given one.

Generation SHALL be iterative rather than one-shot, driven by a pi session with `law.txt`, the framework contract and the shared populated world as background. On each pass the extractor SHALL report every step of the law text it cannot translate into the physical world — a duty whose mechanism no declared object, capability or action accounts for, or that no world individual performs — and the session SHALL put those steps to the author as questions rather than proceed on a guess. Generation SHALL be complete only when the extractor reports none, and nothing SHALL present a draft as complete while any remain. The report SHALL be a separate structured value conforming to the project-owned schema, never a fenced block inside a draft; a headless run with questions outstanding SHALL write its drafts plus the report and exit non-zero rather than invent answers.

The threshold is the extractor's own uncertainty, and nothing SHALL ask about a step it can ground. Where a step can be translated by choosing among the objects and capabilities the shared vocabulary already declares, acting on individuals the shared world already contains, the extractor SHALL proceed and encode that choice as an ordinary declaration in `ontology.ttl` or `rules.lean`, because that is where the choice belongs and where the review gate already examines it. Recording such a choice in a separate artefact would be wrong twice over: it duplicates a fact the declarations already carry, and it implies a class of recorded doubt the process does not have.

The session SHALL draft only the law overlay — law TBox, law-derived seeds, Lean, manifest — reading the shared populated world read-only and referencing its individuals by IRI. It SHALL NOT restate a world-owned individual.

No record of the exchange SHALL be kept. The deliverable is the draft, and an answer given in the course of drafting belongs in the declarations that answer changed, not in a second place beside them.

The gate SHALL enforce what the process promises, and a check SHALL cover the shape the existing ones miss. A draft whose generation did not converge names something no declared class, property or capability accounts for. An individual typed by an undeclared class is already refused by the population check and an undeclared property by seed parity, but **a class naming an undeclared superclass, domain or range is not**: grounding asks whether a class reaches GFO, which an invented name wired alongside a real superclass does not disturb. The frozen-TBox check SHALL therefore require every `ph:` class a declaration names, as a superclass, a domain or a range, to be itself declared; only `ph:` names need resolve, since a GFO class is legitimately external and grounding is what judges it.

The gate SHALL NOT crash on a malformed artefact set. A check that cannot complete on one SHALL report that it could not, naming the failure, so that a caller running the gate as a precondition — `freeze.py` does — sees the finding rather than a traceback.

#### Scenario: Redraft diff is structural
- **WHEN** the mayor law text changes only the term length from 4 to 2 years
- **THEN** the regenerated draft diff shows changed time arithmetic and deadlines, not renamed classes or a reshaped state schema

#### Scenario: Generated artefacts satisfy the framework invariants
- **WHEN** the session drafts a law that names only a custom process with its own vocabulary
- **THEN** the draft still declares `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint`, and `ph:CalendarSpan` with GFO grounding, places law-derived seeded individuals in `population.ttl`, and references world individuals by IRI without restating them

#### Scenario: Generated ontology carries a hierarchy
- **WHEN** the harness drafts a law whose text describes a process made of named stages
- **THEN** the draft declares each Process class's constituents through `ph:hasPhase` as grounded subproperties of `gfo-core:hasSituationPart`, rather than leaving the process as an unelaborated class

#### Scenario: Prompt requests are verified, not trusted
- **WHEN** a draft omits the `roleIn` and `playedBy` relations the prompt requires
- **THEN** the gate fails naming the missing relation, so an unfulfilled prompt instruction cannot reach the review gate unnoticed

#### Scenario: Physical concepts named from the text
- **WHEN** the harness drafts the mayor law, whose text performs duties on a mailbox, a ballot box, a townhall, and a board
- **THEN** the draft refers to those through the shared vocabulary rather than declaring private classes, and declares locally only what the vocabulary does not carry

#### Scenario: No physical duty, no physical class
- **WHEN** the harness drafts a law whose text presupposes nothing physical
- **THEN** the prompt produces no physical declaration for it, so availability is not read as an obligation

#### Scenario: A step the extractor can ground is not asked about
- **WHEN** a law requires a duty performed with an instrument but names no kind of instrument, and the shared vocabulary declares a capability covering it
- **THEN** the extractor proceeds and declares the duty against that capability, and no question is put to the author, because the choice is expressible in the declarations the gate already reviews

#### Scenario: A step the extractor cannot ground is asked about
- **WHEN** a law requires a step for which the shared vocabulary declares no object, capability or action accounting for it
- **THEN** the session asks the author what the step consists of, and does not present the draft as complete until answered, rather than inventing a mechanism and encoding it

#### Scenario: An answer lands in the declarations, not beside them
- **WHEN** an author's answer changes what a class means, or which class a duty is performed on
- **THEN** `ontology.ttl` or `rules.lean` carries the answer as an ordinary declaration, and no separate file records either the question or its answer

#### Scenario: A loop that stopped early is refused
- **WHEN** generation is presented as complete while the draft still refers to a class no ontology declares, whether by typing a seeded individual by it, by making a class its subclass, or by giving a property its domain or range
- **THEN** the gate fails naming the undeclared class, so a draft resting on an unanswered question cannot be frozen

#### Scenario: A headless run with questions outstanding is not complete
- **WHEN** a headless run ends with the report non-empty
- **THEN** it has written its drafts plus the schema-conforming report and exited non-zero, so nothing downstream can mistake an unconverged draft for a finished one

#### Scenario: A malformed set is reported rather than crashing the gate
- **WHEN** a check cannot complete because the artefact set is malformed
- **THEN** the gate reports the failure under that check's name and continues, so a caller running the gate as a precondition sees the finding instead of a traceback

#### Scenario: The vocabulary's coverage bounds how often the loop interrupts
- **WHEN** two laws' texts both need a concept the shared vocabulary does not declare, so both drafts put the same question to their authors
- **THEN** the repeated question is evidence the shared stage lacks a concept every law can reach for, rather than a question each law should answer for itself

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

### Requirement: Explicit review gate to frozen

No artefact set SHALL be consumable by the simulator until a human marks it reviewed, freezing the exact file versions. A freeze SHALL record both the case files' versions and the world version the set was reviewed against, as well as which version of the shared physical vocabulary the set was frozen against. Post-freeze law edits SHALL require a new review, and so SHALL a world version that no longer matches the recorded one: a set reviewed against a world that has since moved is not consumable until re-reviewed. A freeze SHALL cover the shared physical vocabulary as well as the case's own files, so that verification can say which vocabulary moved rather than only that something did.

#### Scenario: TUI refuses drafts
- **WHEN** the TUI is pointed at an artefact set that was edited after its review mark
- **THEN** it refuses to load and names the changed files

#### Scenario: TUI refuses a set whose world moved
- **WHEN** the TUI is pointed at a frozen artefact set whose recorded world version no longer matches the world's current version
- **THEN** it refuses to load and names the world store as the drifted dependency, so a meaning that moved underneath the review prompts a new review instead of a silent reinterpretation

#### Scenario: A moved vocabulary invalidates the freeze
- **WHEN** the shared physical vocabulary changes after a case was frozen
- **THEN** verification fails for that case and names the vocabulary as the changed artefact, so a set cannot verify against a vocabulary it was not reviewed with

#### Scenario: The frozen vocabulary version is recorded
- **WHEN** a case is frozen
- **THEN** its manifest names the version of the shared vocabulary it was reviewed against, so upgrading the vocabulary prompts an informed re-review rather than an automatic one
