# Spec Delta

## MODIFIED Requirements

### Requirement: Ontology profile grounded in GFO-light

Artefact ontologies SHALL subclass GFO-light/GFO-core categories (Object, ObjectAggregate, Role, Relator, Quality, InformationObject, Process, State, SituationAggregate) with mirror-by-name Lean counterparts, and every simulatable entity SHALL carry an `rdfs:label` for display. The mirror-by-name rule applies to a law's own declarations: a class resolved from the shared physical vocabulary is not required to have a Lean counterpart in each law that draws on it.

Every law SHALL additionally declare the framework-invariant classes without which a law-agnostic consumer cannot operate: `ph:Citizen` as a subclass of `gfo-light:Object` whose every individual carries `rdfs:label` and a `ph:age` value; `ph:Clock` as a subclass of `gfo-light:TimeBoundary` carrying `ph:dayIndex` and `ph:atHour`; `ph:CalendarPoint` as a subclass of `gfo-light:TimeBoundary` carrying `rdfs:label`, `ph:atDate`, `ph:dayIndex`, and `ph:marksPhase`; and `ph:CalendarSpan` as a subclass of `gfo-light:Chronoid` related to its bounding `ph:CalendarPoint`s and optionally carrying `ph:marksPhase`. `ph:atDate` SHALL be a subproperty of `gfo-core:dateTimeValue`, and `ph:age`, `ph:atHour`, and `ph:dayIndex` SHALL be subproperties of `gfo-core:decimalValue`. `ph:atHour` and `ph:dayIndex` SHALL each declare `rdfs:domain gfo-light:TimeBoundary`: a day index names a moment, so it belongs on `ph:Clock`, on a `ph:CalendarPoint`, and on the bounds the oracle mints, and on no other individual. A process instance, an occurrence, or a span carries no position of its own, because a second copy of the present is a second source for a fact the framework already fixes.

A law SHALL declare as `owl:FunctionalProperty` every `ph:` property whose encoding is single-valued, including the flags, the outcome, the status, the index, and the moment properties of a bound. A property that may hold more than one value for one subject SHALL NOT be declared functional, such as `ph:marksPhase`, which one moment may carry for several phases. The declaration is what makes re-encoding a no-op rather than an accumulation, so a property the oracle rewrites on every act SHALL be functional unless it is deliberately set-valued.

Every law SHALL declare the relationships between its Process classes, each grounded in GFO rather than reusing a GFO property directly. Grounding SHALL be by `rdfs:subPropertyOf` where the relation coincides with a GFO one, and by GFO `rdfs:domain`/`rdfs:range` where GFO has no such relation but the types are knowable. A property may not be declared as a subproperty of a GFO relation it does not coincide with, even where the direction or the object type differs: `ph:hasPhase` over `gfo-core:hasSituationPart` for decomposition, `ph:hasParticipant` over `gfo-core:hasParticipant`, `ph:hasTime` over `gfo-core:timeOf`, `ph:relates` and `ph:containsRole` over `gfo-light:Relator`, and `ph:qualityOf` over `gfo-light:qualityOf`, with roles related by `roleIn` and `playedBy`.

Each Process class SHALL name its constituent phases through `ph:hasPhase` as a plain class-level assertion. Every Process class a law declares SHALL be reachable from a declared root Process through that relation, and every phase SHALL be marked by a `ph:CalendarSpan` carrying `ph:marksPhase`. A law SHALL NOT declare a Process class that no ECA, root, or other phase refers to.

Process instances SHALL take their temporal bounds in GFO's shape: an instance relates to a `Chronoid` by `ph:hasTime`, and that `Chronoid` carries `gfo-core:temporallyStartedBy` and `gfo-core:temporallyFinishedBy` pointing at `TimeBoundary` individuals. A `TimeBoundary` SHALL NOT be attached directly to a situation in place of a `Chronoid`. Absence of a start bound SHALL denote an instance that has not begun.

The ontology SHALL be a frozen schema of classes and properties only. Individuals SHALL NOT appear in it. Individuals are split between two stores: the shared populated world — citizens, physical furniture, supply, and the single `ph:Clock` individual — lives in the framework's world store, reviewed and frozen once, and laws SHALL reference world individuals by IRI without restating them; individuals that a law itself derives — calendar, process instances, states, roles — SHALL live in a sibling `population.ttl` in the same case directory, in the same RDF serialisation as the schema. A law SHALL NOT declare or re-declare a world-owned individual in its own files. Individuals created during simulation SHALL be minted into the runtime knowledge graph. All individuals SHALL carry labels through a `ph:label` property that the ontology declares as a subproperty of `rdfs:label`. Because the schema is frozen while the individuals in the runtime graph are not, freezing bounds the vocabulary of minting and not its extent: a law SHALL declare every class it will ever mint, and nothing bounds how many instances of those classes may come to exist.

The framework SHALL distinguish the classes a law must declare from the classes it may draw on. The framework-invariant classes above are mandatory, because a consumer cannot operate without them. The shared physical vocabulary is available to every law and required of none, because it answers what a law's text presupposes rather than what a consumer operates on: a law's duties are performed on and with physical things, so those things need one declaration rather than one per law, but a law whose text presupposes nothing physical has no use for them. A law needing a concept the shared vocabulary does not carry SHALL declare it locally, and a local declaration colliding with a shared class SHALL be reported by the review gate naming both rather than resolved silently.

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

#### Scenario: A shared class needs no Lean counterpart per law
- **WHEN** a law draws on a class from the shared physical vocabulary that has no same-named Lean type in that law's `rules.lean`
- **THEN** the law is not failed by the mirror-by-name rule, because that rule governs a law's own declarations and a shared class is not declared by the law

#### Scenario: Omitting the physical vocabulary is not a failure
- **WHEN** a law's ontology references no shared physical class
- **THEN** the framework invariants check passes, because the physical vocabulary is available to a law rather than required of one

#### Scenario: A local physical class is reported against the shared one
- **WHEN** a law declares locally a class the shared physical vocabulary also declares
- **THEN** the review gate reports both declarations so a reviewer can see which one a subject resolves to, rather than the shared one silently taking precedence
