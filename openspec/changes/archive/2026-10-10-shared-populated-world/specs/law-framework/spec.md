# Spec Delta

## MODIFIED Requirements

### Requirement: Ontology profile grounded in GFO-light

Artefact ontologies SHALL subclass GFO-light/GFO-core categories (Object, ObjectAggregate, Role, Relator, Quality, InformationObject, Process, State, SituationAggregate) with mirror-by-name Lean counterparts, and every simulatable entity SHALL carry an `rdfs:label` for display.

Every law SHALL additionally declare the framework-invariant classes without which a law-agnostic consumer cannot operate: `ph:Citizen` as a subclass of `gfo-light:Object` whose every individual carries `rdfs:label` and a `ph:age` value; `ph:Clock` as a subclass of `gfo-light:TimeBoundary` carrying `ph:dayIndex` and `ph:atHour`; `ph:CalendarPoint` as a subclass of `gfo-light:TimeBoundary` carrying `rdfs:label`, `ph:atDate`, `ph:dayIndex`, and `ph:marksPhase`; and `ph:CalendarSpan` as a subclass of `gfo-light:Chronoid` related to its bounding `ph:CalendarPoint`s and optionally carrying `ph:marksPhase`. `ph:atDate` SHALL be a subproperty of `gfo-core:dateTimeValue`, and `ph:age`, `ph:atHour`, and `ph:dayIndex` SHALL be subproperties of `gfo-core:decimalValue`. `ph:atHour` and `ph:dayIndex` SHALL each declare `rdfs:domain gfo-light:TimeBoundary`: a day index names a moment, so it belongs on `ph:Clock`, on a `ph:CalendarPoint`, and on the bounds the oracle mints, and on no other individual. A process instance, an occurrence, or a span carries no position of its own, because a second copy of the present is a second source for a fact the framework already fixes.

A law SHALL declare as `owl:FunctionalProperty` every `ph:` property whose encoding is single-valued, including the flags, the outcome, the status, the index, and the moment properties of a bound. A property that may hold more than one value for one subject SHALL NOT be declared functional, such as `ph:marksPhase`, which one moment may carry for several phases. The declaration is what makes re-encoding a no-op rather than an accumulation, so a property the oracle rewrites on every act SHALL be functional unless it is deliberately set-valued.

Every law SHALL declare the relationships between its Process classes, each grounded in GFO rather than reusing a GFO property directly. Grounding SHALL be by `rdfs:subPropertyOf` where the relation coincides with a GFO one, and by GFO `rdfs:domain`/`rdfs:range` where GFO has no such relation but the types are knowable. A property may not be declared as a subproperty of a GFO relation it does not coincide with, even where the direction or the object type differs: `ph:hasPhase` over `gfo-core:hasSituationPart` for decomposition, `ph:hasParticipant` over `gfo-core:hasParticipant`, `ph:hasTime` over `gfo-core:timeOf`, `ph:relates` and `ph:containsRole` over `gfo-light:Relator`, and `ph:qualityOf` over `gfo-light:qualityOf`, with roles related by `roleIn` and `playedBy`.

Each Process class SHALL name its constituent phases through `ph:hasPhase` as a plain class-level assertion. Every Process class a law declares SHALL be reachable from a declared root Process through that relation, and every phase SHALL be marked by a `ph:CalendarSpan` carrying `ph:marksPhase`. A law SHALL NOT declare a Process class that no ECA, root, or other phase refers to.

Process instances SHALL take their temporal bounds in GFO's shape: an instance relates to a `Chronoid` by `ph:hasTime`, and that `Chronoid` carries `gfo-core:temporallyStartedBy` and `gfo-core:temporallyFinishedBy` pointing at `TimeBoundary` individuals. A `TimeBoundary` SHALL NOT be attached directly to a situation in place of a `Chronoid`. Absence of a start bound SHALL denote an instance that has not begun.

The ontology SHALL be a frozen schema of classes and properties only. Individuals SHALL NOT appear in it. Individuals are split between two stores: the shared populated world — citizens, physical furniture, supply, and the single `ph:Clock` individual — lives in the framework's world store, reviewed and frozen once, and laws SHALL reference world individuals by IRI without restating them; individuals that a law itself derives — calendar, process instances, states, roles — SHALL live in a sibling `population.ttl` in the same case directory, in the same RDF serialisation as the schema. A law SHALL NOT declare or re-declare a world-owned individual in its own files. Individuals created during simulation SHALL be minted into the runtime knowledge graph. All individuals SHALL carry labels through a `ph:label` property that the ontology declares as a subproperty of `rdfs:label`. Because the schema is frozen while the individuals in the runtime graph are not, freezing bounds the vocabulary of minting and not its extent: a law SHALL declare every class it will ever mint, and nothing bounds how many instances of those classes may come to exist.

The framework SHALL NOT fix who holds a duty when no office is filled, and SHALL NOT require every law to distinguish a time-scoped phase from a stateful per-occurrence entity: both are Process instances and differ only in cardinality and nesting.

#### Scenario: Mayor ontology validates
- **WHEN** the mayor `ontology.ttl` declares Citizen as `gfo-light:Object`, MayorRole as `gfo-light:Role` with `roleIn` + `playedBy`, and election phases as `gfo-core:Process`/`State`
- **THEN** OWL parsing plus the GFO-light consistency check passes and each class has a same-named Lean type

#### Scenario: Missing label rejected
- **WHEN** an ontology individual lacks `rdfs:label`
- **THEN** the Step 1 review gate fails with the offending IRI named

#### Scenario: Cycle individual validates
- **WHEN** the quorum ontology declares cycle date properties on `ph:MayorElectionCycle` and a cycle individual carries its label plus concrete day values
- **THEN** OWL parsing plus the GFO-light consistency check passes and the TUI resolves the cycle name by IRI lookup without date arithmetic

#### Scenario: Missing cycle label rejected
- **WHEN** a cycle individual lacks `rdfs:label`
- **THEN** the review gate fails with the offending IRI named, as for any simulatable individual

#### Scenario: Law omitting a framework invariant is rejected
- **WHEN** an ontology omits `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint`, or `ph:CalendarSpan`, or omits the GFO superclass or subproperty grounding for any of them
- **THEN** the review gate fails naming the missing or ungrounded declaration, and the set is not freezable

#### Scenario: Frozen ontology carries no individuals
- **WHEN** a case's `ontology.ttl` declares a citizen, calendar point, or process individual
- **THEN** the review gate fails and names the offending IRI, directing the author to declare the class in `ontology.ttl` and the seeded individual in `population.ttl`

#### Scenario: Authority is law-determined
- **WHEN** two laws both leave a duty unheld by an office holder and resolve it to different citizens
- **THEN** each resolves per its own rules with no framework rule naming oldest, youngest, or any other fallback, and neither law requires a framework declaration to do so

#### Scenario: Calendar-to-phase grounding is by type
- **WHEN** a law declares a relation from a calendar node to the Process phase it bounds
- **THEN** it is grounded by declaring `gfo-light:Chronoid`/`gfo-light:TimeBoundary` as its domain and `gfo-core:Process` as its range, and is not declared as the inverse of `gfo-core:hasTime`, because that relation's object is an individual while a frozen shared calendar can only name a phase class

#### Scenario: Declared hierarchy is readable structure
- **WHEN** a consumer loads an ontology in which `ph:MayorElectionCycle` declares `ph:hasPhase ph:SelfNomination`
- **THEN** it reports nomination as a constituent phase of the election without knowing which law it is reading and without consulting the manifest

#### Scenario: Unreachable Process class rejected
- **WHEN** a law declares a Process class that no root Process reaches and no ECA refers to
- **THEN** the review gate fails naming the orphan class

#### Scenario: Phase without a calendar span rejected
- **WHEN** a law declares a phase that no `ph:CalendarSpan` marks
- **THEN** the review gate fails naming the phase, so no process structure exists that the law never scheduled

#### Scenario: Lifecycle bounds take the Chronoid shape
- **WHEN** a process instance carries temporal bounds
- **THEN** they reach a `Chronoid` by `ph:hasTime` whose start and finish point at `TimeBoundary` individuals, and the gate rejects a `TimeBoundary` attached directly to the situation

#### Scenario: Absent start bound means not begun
- **WHEN** a process instance exists with no start bound on its `Chronoid`
- **THEN** a consumer reports it as initialised and awaiting its trigger rather than as ongoing

#### Scenario: Overlapping phases need no causal chain
- **WHEN** the nomination window overlaps both announce and prepare
- **THEN** a consumer derives that overlap from the `Chronoid` bounds of their calendar spans, and the ontology needs no ordering relation between the phases

#### Scenario: A position outside a moment is rejected
- **WHEN** an individual that is not a `gfo-light:TimeBoundary` carries `ph:dayIndex` or `ph:atHour`
- **THEN** the review gate fails naming the subject and the property, because a process instance or a span holds no present of its own

#### Scenario: Functional properties are declared
- **WHEN** a law's oracle re-encodes a property on every act
- **THEN** the ontology declares it `owl:FunctionalProperty`, so a consumer can tell a re-encoding from a second value, and a property that may hold several values for one subject is not declared functional

#### Scenario: An undeclared functional property is caught
- **WHEN** a draft declares a single-valued property such as a flag or an outcome without `owl:FunctionalProperty`
- **THEN** the review gate fails naming the property, since its idempotent encoding cannot be checked

#### Scenario: Freezing bounds vocabulary, not extent
- **WHEN** a law declares the classes it will mint and then mints many instances of them over a long run
- **THEN** the set stays freezable because no new class appeared, and a class the law would need but did not declare is a review failure rather than a runtime surprise

#### Scenario: A world individual restated in a case is refused
- **WHEN** a case's `population.ttl` declares an individual the world store already owns, such as a citizen or a sheet
- **THEN** the review gate fails naming the IRI, directing the author to reference the world individual instead, since two declarations of one individual leave two states for one thing

#### Scenario: Law seeds hold only what the law derives
- **WHEN** a case's `population.ttl` carries calendar, process instance, state and role individuals and references world furniture by IRI without restating it
- **THEN** the gate passes the seed scope, so the law's own starting facts are reviewable apart from the world they start in

### Requirement: Nat-day time model

Laws SHALL express time as `Nat` days plus hour integers, with named day arithmetic per cycle (election day, announce day = election day minus 10, prepare day = election day minus 1, polls 9am-7pm on election day). Periodic recurrence SHALL be a Nat function of the cycle index (e.g. election year = 2027 + 4k). Quorum repeats SHALL derive per-repeat dates as a Nat function of the repeat index (`E(k+1) = E(k)+30`, announce at `E-10`, prepare at `E-1`, polls 9am-7pm on E-day). Repeats SHALL NOT shift the 4-year election clock; they only shorten the mandate in office.

Each law SHALL name its calendar as `ph:CalendarPoint` and `ph:CalendarSpan` individuals. A node whose position is fixed when the law is reviewed SHALL co-locate a human-readable `ph:atDate` with the `ph:dayIndex` a consumer compares against, so a consumer can display a date without computing one. A span whose end falls a fixed interval after a moment that does not exist until the simulation runs SHALL instead carry `ph:gapDays` and no absolute position, because the law has fixed the interval and left the moment to be resolved; such a span names no day, and the oracle resolves it into concrete points when it accepts the act that schedules the work. A span that bounds a phase SHALL carry `ph:marksPhase` naming it.

The current position SHALL be carried by the single `ph:Clock` individual in the shared world, whose `ph:dayIndex` and `ph:atHour` names are fixed by the framework rather than declared per law, and no other individual in the graph SHALL carry the current position. There is one simulation over the shared reality, so all laws read the same present; the simulation activates one law at a time against the persistent world, and the clock persists across activations. A process instance's own schedule SHALL follow from its declared index and the law's named day arithmetic, never from a position stored on the instance; where a consumer needs to know how far an instance has got, it reads the instance's `Chronoid` bounds and its flags, which record moments rather than a present. Because `ph:Clock` and `ph:CalendarPoint` share `ph:dayIndex`, the current calendar position SHALL follow from ordering a law's calendar points against the clock, with no law-specific comparison logic.

The clock SHALL be the runtime's one write into the graph. Only the runtime advances it, and it SHALL advance the clock monotonically: a consumer SHALL NOT move it to an earlier day or hour than the one the graph already carries. Totality over absurd values and monotonicity are separate guarantees. Totality says no value can crash the oracle. Monotonicity says no value can contradict a recorded moment, since a clock moved back would let a period a law has already closed reopen and admit an act into a process that has finished. The clock's reading is runtime-owned mutable state and is excluded from the world freeze hash, so advancing the present never invalidates a review.

The frozen calendar is a seed rather than a ceiling. A law SHALL be able to mint further `ph:CalendarPoint` and `ph:CalendarSpan` individuals into the runtime graph during simulation, so that a process which schedules work at a moment not fixed when the law was reviewed still has a calendar the consumer can display. A minted point SHALL carry the same declared properties as a seeded one, including `ph:dayIndex`, `ph:atHour` where the moment has an hour, and, where it bounds a phase, `ph:marksPhase`; a minted span SHALL carry the same declared properties as a seeded one, which for a span in the relative form means `ph:gapDays` and no absolute position. Its IRI SHALL satisfy the freshness rule. Only Lean SHALL compute the date and day index a minted individual carries; a consumer SHALL NOT derive either.

Sequencing and overlap between phases SHALL be derivable from calendar bounds alone. No ordering relation SHALL appear between phases, because a chain of such relations cannot express two phases running at once and the calendar already answers ordering and overlap from one source.

A seed describes what the law permits and not how the oracle works out a moment. A seeded individual SHALL NOT carry a value whose purpose is to let a consumer reproduce a computation the oracle owns, and a seeded individual SHALL NOT state what an interval is measured from, because the method is the oracle's and declaring it puts the computation back into the artefacts. Where a law fixes an interval, it appears once as the interval on the calendar node that bounds the phase, and the moment it resolves to is computed by Lean when the act that needs it is accepted, whether that is the instance's initialisation or a later trigger.

#### Scenario: Election dates derive correctly
- **WHEN** cycle index 0 denotes the 2027 election
- **THEN** announce day, prepare day, and poll hours compute to Jan 2, Jan 11, and 9-19 on Jan 12 respectively

#### Scenario: Repeat dates derive per index
- **WHEN** the void election sits at E-day 10
- **THEN** repeat index 1 computes to E-day 40, announce day 30, prepare day 39, and polls 9am-7pm on day 40

#### Scenario: Four-year clock unaffected
- **WHEN** two repeats slip the 2027 election into March
- **THEN** the 2031 election date is unchanged

#### Scenario: Calendar resolves without date arithmetic
- **WHEN** a law declares a calendar point with `ph:dayIndex 0` and `ph:atDate "2027-01-02"` and the clock reads `ph:dayIndex 0`
- **THEN** a consumer displays that point's label and date read straight from the ontology, computing no calendar arithmetic

#### Scenario: Clock names need no per-law declaration
- **WHEN** a law is loaded by a consumer that reads only the framework-fixed `ph:dayIndex` and `ph:atHour` on `ph:Clock`
- **THEN** the consumer advances and reads the clock for that law with no law-specific field mapping

#### Scenario: Overlapping phases ordered by bounds
- **WHEN** two phases' calendar spans cover overlapping day ranges
- **THEN** a consumer reports both as running concurrently, deriving it from the bounds alone with no ordering relation in the artefacts

#### Scenario: Calendar grows as a process unfolds
- **WHEN** a law mints a further calendar span into the runtime graph for work it schedules at a moment not fixed at review
- **THEN** the span carries the same declared properties as a seeded one, resolves a date and a day index for display, and the consumer adds it to the displayed calendar without any law-specific handling

#### Scenario: Only Lean dates a minted calendar individual
- **WHEN** a minted calendar span appears in the graph
- **THEN** its `ph:atDate` and `ph:dayIndex` were computed by the oracle, and the consumer displays them without deriving either

#### Scenario: Advancing the clock moves every law
- **WHEN** a consumer writes a new `ph:Clock` day and hour into the graph of any conforming law and then calls `check`
- **THEN** the verdict reflects the new position, so the clock is the position for every law rather than for those whose shape happens to keep one, and no consumer needs to know how many places a given law records the day

#### Scenario: A process instance holds no position
- **WHEN** a law's oracle derives the current phase by comparing a moment against a process instance's schedule
- **THEN** the schedule comes from the instance's declared index and the law's day arithmetic, and no individual other than `ph:Clock` carries the present

#### Scenario: The clock does not move backwards
- **WHEN** a consumer sets the clock to an earlier day or hour than the graph already carries
- **THEN** a law whose conditions derive from the clock treats the recorded periods as they stand, so a period already closed cannot reopen

#### Scenario: A span whose end is relative names no day
- **WHEN** a law declares a span bounded by an interval after a moment that only exists once the simulation runs
- **THEN** the span carries `ph:gapDays` and no `ph:dayIndex` and no `ph:atDate`, so the frozen calendar does not assert a day that differs for each occurrence, and the oracle resolves the concrete points when it schedules the work

#### Scenario: A seed states no anchor for an interval
- **WHEN** a seed declares a span carrying `ph:gapDays`
- **THEN** nothing in the seed says what the interval is measured from or how the moment is derived, because the method belongs to the oracle and a declared anchor would put the computation back into the artefacts

#### Scenario: A seed value nothing reads is rejected
- **WHEN** a seed carries a property that no condition, guard, or verdict of the law consults, such as an interval held on a process instance that the oracle holds as a constant of its own
- **THEN** the review gate fails naming the property and the individual carrying it, since a value that duplicates the oracle's own arithmetic is a second source for a fact rather than a description of what the law permits

#### Scenario: One present shared across laws
- **WHEN** the simulation activates a second law after advancing the clock under the first
- **THEN** the second law reads the same `ph:Clock` individual and its calendar positions resolve against the carried-over present, so time passes hamlet-wide rather than per law

#### Scenario: Advancing the present never invalidates a review
- **WHEN** the runtime advances the shared clock and a frozen case is re-verified
- **THEN** verification still passes, because the clock's reading is excluded from the world freeze hash and only the clock's identity is pinned
