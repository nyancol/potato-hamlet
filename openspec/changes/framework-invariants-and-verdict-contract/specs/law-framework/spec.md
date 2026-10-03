# Spec Delta

## MODIFIED Requirements

### Requirement: Ontology profile grounded in GFO-light

Artefact ontologies SHALL subclass GFO-light/GFO-core categories (Object, ObjectAggregate, Role, Relator, Quality, InformationObject, Process, State, SituationAggregate) with mirror-by-name Lean counterparts, and every simulatable entity SHALL carry an `rdfs:label` for display.

Every law SHALL additionally declare the framework-invariant classes without which a law-agnostic consumer cannot operate: `ph:Citizen` as a subclass of `gfo-light:Object` whose every individual carries `rdfs:label` and a `ph:age` value; `ph:Clock` as a subclass of `gfo-light:TimeBoundary` carrying `ph:dayIndex` and `ph:atHour`; `ph:CalendarPoint` as a subclass of `gfo-light:TimeBoundary` carrying `rdfs:label`, `ph:atDate`, `ph:dayIndex`, and `ph:marksPhase`; and `ph:CalendarSpan` as a subclass of `gfo-light:Chronoid` related to its bounding `ph:CalendarPoint`s and optionally carrying `ph:marksPhase`. `ph:atDate` SHALL be a subproperty of `gfo-core:dateTimeValue`, and `ph:age`, `ph:atHour`, and `ph:dayIndex` SHALL be subproperties of `gfo-core:decimalValue`.

Every law SHALL declare the relationships between its Process classes, each grounded in GFO rather than reusing a GFO property directly. Grounding SHALL be by `rdfs:subPropertyOf` where the relation coincides with a GFO one, and by GFO `rdfs:domain`/`rdfs:range` where GFO has no such relation but the types are knowable. A property may not be declared as a subproperty of a GFO relation it does not coincide with, even where the direction or the object type differs: `ph:hasPhase` over `gfo-core:hasSituationPart` for decomposition, `ph:hasParticipant` over `gfo-core:hasParticipant`, `ph:hasTime` over `gfo-core:timeOf`, `ph:relates` and `ph:containsRole` over `gfo-light:Relator`, and `ph:qualityOf` over `gfo-light:qualityOf`, with roles related by `roleIn` and `playedBy`.

Each Process class SHALL name its constituent phases through `ph:hasPhase` as a plain class-level assertion. Every Process class a law declares SHALL be reachable from a declared root Process through that relation, and every phase SHALL be marked by a `ph:CalendarSpan` carrying `ph:marksPhase`. A law SHALL NOT declare a Process class that no ECA, root, or other phase refers to.

Process instances SHALL take their temporal bounds in GFO's shape: an instance relates to a `Chronoid` by `ph:hasTime`, and that `Chronoid` carries `gfo-core:temporallyStartedBy` and `gfo-core:temporallyFinishedBy` pointing at `TimeBoundary` individuals. A `TimeBoundary` SHALL NOT be attached directly to a situation in place of a `Chronoid`. Absence of a start bound SHALL denote an instance that has not begun.

The ontology SHALL be a frozen schema of classes and properties only. Individuals SHALL NOT appear in it. Individuals that a law starts from SHALL live in a sibling `population.ttl` in the same case directory, in the same RDF serialisation as the schema, and individuals created during simulation SHALL be minted into the runtime knowledge graph. Both kinds SHALL carry labels through a `ph:label` property that the ontology declares as a subproperty of `rdfs:label`. Process-instance and calendar IRIs SHALL be deterministic from `(case, index)`.

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

### Requirement: Nat-day time model

Laws SHALL express time as `Nat` days plus hour integers, with named day arithmetic per cycle (election day, announce day = election day minus 10, prepare day = election day minus 1, polls 9am-7pm on election day). Periodic recurrence SHALL be a Nat function of the cycle index (e.g. election year = 2027 + 4k). Quorum repeats SHALL derive per-repeat dates as a Nat function of the repeat index (`E(k+1) = E(k)+30`, announce at `E-10`, prepare at `E-1`, polls 9am-7pm on E-day). Repeats SHALL NOT shift the 4-year election clock; they only shorten the mandate in office.

Each law SHALL name its calendar as `ph:CalendarPoint` and `ph:CalendarSpan` individuals, each co-locating a human-readable `ph:atDate` with the `ph:dayIndex` a consumer compares against, so a consumer can display a date without computing one. A span that bounds a phase SHALL carry `ph:marksPhase` naming it. The current position SHALL be carried by a single `ph:Clock`, whose `ph:dayIndex` and `ph:atHour` names are fixed by the framework rather than declared per law. Because `ph:Clock` and `ph:CalendarPoint` share `ph:dayIndex`, the current calendar position SHALL follow from ordering a law's calendar points against the clock, with no law-specific comparison logic.

The frozen calendar is a seed rather than a ceiling. A law SHALL be able to mint further `ph:CalendarPoint` and `ph:CalendarSpan` individuals into the runtime graph during simulation, so that a process which schedules work at a moment not fixed when the law was reviewed still has a calendar the consumer can display. A minted point or span SHALL carry the same declared properties as a seeded one, including `ph:dayIndex` and, where it bounds a phase, `ph:marksPhase`, and its IRI SHALL be deterministic from `(case, index)`. Only Lean SHALL compute the date and day index a minted individual carries; a consumer SHALL NOT derive either.

Sequencing and overlap between phases SHALL be derivable from calendar bounds alone. No ordering relation SHALL appear between phases, because a chain of such relations cannot express two phases running at once and the calendar already answers ordering and overlap from one source.

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

### Requirement: ECA metamodel with bounded FOL subset

Each law SHALL declare its dynamics as ECA rules with Event (clock tick or act), Condition over a state snapshot, Action transition, duty-holder role, deadline, modality (should vs must, preserved from the source text), and display message. Conditions SHALL use only the framework FOL subset: universal/existential quantification over finite sets, counting, Nat comparisons and arithmetic. The Action leg SHALL have an executable encoding: one pure transition function per ECA taking a snapshot to a snapshot (or a rejection reason), guarded by the same conditions the oracle checks, with actions addressed as data (ECA id plus parameters) over JSON. Quorum flavors SHALL declare `repeat` as a first-class ECA whose holder is the authority (mayor-or-oldest, same `authorityId` as announce/prepare/count/proclaim), whose modality is `must`, and whose message names the scheduled successor.

An ECA's parameters and duty-holder role SHALL be declared so that a consumer can build a complete act without law-specific code. Each ECA SHALL carry a `holder_role` naming a Role class, and each parameter SHALL name a wire field, the Role class it binds, and a source drawn from the closed set `selected` (bound to the acting citizen) or `choices` (supplied by the oracle). Every declared Role SHALL be one the ontology declares as participating in that ECA's Process class. Holders SHALL be read from oracle verdicts; a consumer SHALL NOT compute, infer, or default who holds a duty.

An ECA's `eca_process` SHALL name a Process class appearing in the law's declared `ph:hasPhase` hierarchy. An ECA whose action mints a new Process instance SHALL name the Process class it creates, so that starting a process is distinguishable in the artefacts from any other act.

Causality SHALL be expressible where it is structural and SHALL NOT be duplicated where it is evaluated. A `ph:causedBy` relation, declared as a subproperty of `gfo-core:causedBy`, MAY relate a Process to a `gfo-core:State`, with the Process as subject and the State as object, stating that the situation the State holds can bring about a change in that Process. The direction follows `causedBy`'s own sense: the relation's subject is what is affected. Such a relation is read without evaluation: it says the dependency is permitted, not that it has occurred. Whether the State actually holds, and whether it therefore triggers the change, SHALL be evaluated only by the ECA's Lean guard. The ontology and manifest SHALL NOT carry an ordering relation between phases, and SHALL NOT carry a relation asserting that a causal dependency has in fact fired.

#### Scenario: All-ballots condition expressed
- **WHEN** the rule "authority must distribute one ballot per candidate to every citizen" is encoded
- **THEN** it reads as a finite universal over citizens and candidates with an existential over delivered ballots, decidable in Lean and evaluable by the oracle

#### Scenario: Modality preserved
- **WHEN** the source text says the authority "should communicate" (announce) but "must create" (ballots)
- **THEN** the two ECAs carry modality should and must respectively, and the guide conveys the difference instead of flattening both to obligations

#### Scenario: Prepare transition executable
- **WHEN** the driver requests the prepare act on a snapshot where prepare is due and an authority holds office
- **THEN** the transition returns a snapshot with the prepared flag set and the full citizen-by-candidate ballot set marked delivered, instead of only reporting that prepare is pending

#### Scenario: Repeat duty owned by authority
- **WHEN** a snapshot shows a void cycle (polls closed, counted, quorum failed) and an authority holds office
- **THEN** the repeat ECA fires with that citizen as holder and modality `must`

#### Scenario: Act parameters build a complete act
- **WHEN** a consumer loads a law whose vote ECA declares a voter parameter sourced from `selected` and a candidate parameter sourced from `choices`
- **THEN** it builds a vote act bound to the acting citizen and to a candidate the user picks, with no law-specific parameter code

#### Scenario: Declared roles checked against the ontology
- **WHEN** a manifest declares an ECA's `holder_role` or a parameter role that the ontology does not declare as participating in that ECA's Process class
- **THEN** the review gate fails naming the undeclared role

#### Scenario: ECA outside the declared hierarchy rejected
- **WHEN** a manifest names an `eca_process` the ontology's declared `ph:hasPhase` hierarchy does not contain
- **THEN** the review gate fails naming the undeclared Process class

#### Scenario: Causal trigger readable, evaluation in Lean
- **WHEN** a law makes an act conditional on a State arising, such as a candidate withdrawing during polls
- **THEN** the ontology declares a `ph:causedBy` relation whose subject is that Process and whose object is that State, a consumer can read that the dependency is permitted, and whether the State holds and so triggers the change is decided only by the Lean guard

#### Scenario: Ordering between phases is never asserted causally
- **WHEN** one phase follows another in the law
- **THEN** no ordering relation between them appears in the ontology, their sequence following from calendar bounds alone

#### Scenario: A fired causal dependency is not asserted in the artefacts
- **WHEN** a causal trigger has actually occurred
- **THEN** the ontology and manifest are unchanged, because they state what may happen rather than what did, and only the graph and the verdict record that it happened

#### Scenario: Starting a process is distinguishable
- **WHEN** an ECA's action mints a new Process instance, such as scheduling a repeat election
- **THEN** the manifest declares which Process class the act creates, so a consumer can tell a process-starting act from any other

### Requirement: OWL-Lean correspondence and snapshot identity

The snapshot SHALL be the knowledge graph itself: the set of typed individuals describing the simulated world. `check` and `apply` SHALL take that instance graph and Lean SHALL derive its state from it, so there is one representation of the world rather than a JSON state object plus a parallel graph. The ontology's class declarations SHALL be the snapshot's schema; every subject in the graph SHALL be typed by a class the ontology declares. Snapshot entity ids SHALL equal the entity IRIs, so ontology-declared entities, graph individuals, and Lean records denote the same entity. Every ECA action SHALL reference a GFO Process class, every post-state a GFO State class, and every holder a Role class.

The graph SHALL carry both the ongoing process instance and every historical instance of the same Process class. A process instance is ongoing exactly when its `Chronoid` carries no `temporallyStartedBy`; a historical instance SHALL carry a finish bound and an outcome. Current position SHALL therefore follow from that distinction rather than from an ordering convention such as "the current cycle is the last element". A process instance is ongoing exactly when its `Chronoid` carries no `temporallyStartedBy`; a historical instance SHALL carry a finish bound and an outcome. Current position SHALL therefore follow from that distinction rather than from an ordering convention such as "the current cycle is the last element".

No transition SHALL remove an individual from the graph. Once an individual exists — a vote cast, a nomination made, a ballot delivered — it persists for the remainder of the simulation, and no ECA SHALL delete, retract, or overwrite its existence. What a later rule MAY affect is only how that individual is counted: when a process instance is finished with an outcome that does not count its contributions, such as an election stopped part-way through polling, the instance's outcome SHALL record that those contributions do not count toward any result. Erasure is not a power a law lacks by policy; it is not a power a law has. This preserves the audit trail the graph exists to provide, and makes a cancelled process reachable by the same path as any other finished instance rather than a special case.

Identity SHALL hold across the graph, the verdict, and the seed for entities minted during simulation as well as seeded ones, and every entity's label SHALL resolve through the graph by IRI. A verdict and a rejection SHALL each reference the IRIs the graph already uses.

#### Scenario: Identity round-trips
- **WHEN** a consumer loads `ph:citizen/alice` into the graph, sends the graph, and receives a verdict
- **THEN** the verdict references the same IRI and the consumer resolves its `rdfs:label` from the graph for display

#### Scenario: Cycle identity round-trips
- **WHEN** the consumer sends a graph containing two election instances and receives a verdict
- **THEN** the verdict references cycle IRIs that resolve to the same labelled individuals the consumer displays

#### Scenario: Snapshot subjects bind to declared classes
- **WHEN** the consumer reads a graph subject
- **THEN** it resolves the subject's type and every one of its properties from the ontology's declarations, without knowing which law it is reading

#### Scenario: History is the same kind of entity as the present
- **WHEN** a law's graph holds an ongoing election instance and a previously void one
- **THEN** both are individuals of the same Process class, distinguished only by their `Chronoid` bounds, and a past-dependent condition addresses the finished one through that ordinary relation

#### Scenario: Runtime entity labels resolve
- **WHEN** a verdict references an entity minted during simulation rather than seeded from the law
- **THEN** the consumer resolves its label from the graph by IRI, with no second label source and no law-specific lookup

#### Scenario: Cancelled process keeps what it accumulated
- **WHEN** a candidate withdraws during polls and the election is stopped part-way through
- **THEN** the ballots already cast remain in the graph as labelled individuals, the instance's outcome records that they do not count, and no transition is available that would erase them

Also verified with a structurally equivalent ending rather than the one named. A mid-poll stop needs a law shape neither shipped law has; what `mayor-quorum` does have is a failed quorum at polls close, which exercises every clause of the `THEN` — the ballot cast before the failure is still in the graph and still typed `ph:CastVote`, the instance's `ph:outcome` records `void`, the successor starts from a fresh registry rather than inheriting anything, and no act exists that removes the ballot. What is untested is specifically a stop *during* polling, with ballots cast on both sides of it.

#### Scenario: No act removes an individual
- **WHEN** every ECA of a law is applied in turn to a graph and each resulting graph is compared with its input
- **THEN** every subject present before an accepted act is still present after it, so no act deletes an individual whatever the law intends

#### Scenario: Only counting is revisable
- **WHEN** a rule bears on a fact already in the graph, such as whether a cast vote counts toward an outcome
- **THEN** it changes how that fact is counted or which outcome it supports, and never whether the fact exists

#### Scenario: Termination mid-span is ordinary
- **WHEN** a process terminates at a moment inside one of its calendar spans rather than at a declared point
- **THEN** its `Chronoid` carries that finish bound, no new vocabulary is required to express it, and the finished instance is read the same way as one ending on a calendar point

The scenario stands as written. No law shipped with this change instantiates it, and that is a gap in the artefacts rather than a weaker promise: every ending both shipped laws have — `proclaim`, and `repeat` on a failed quorum — is guarded behind polls closing, and every span they declare ends at a polls-close point, so no finish can land strictly inside one. What is verified is the requirement the scenario illustrates, exercised with a finish at a moment that is not a declared calendar point (`scripts/test_cancellation.py`, day 12 hour 14 against day 10 hour 19): the bound sits on the `Chronoid`, is a plain `gfo-light:TimeBoundary` carrying both `ph:dayIndex` and `ph:atHour`, uses no predicate the ontology has not declared, and yields a structurally identical graph to a finish on a calendar point. Exercising the `WHEN` needs a law that halts mid-span and postpones, which no current change builds.

#### Scenario: Occurrence is an instance of its phase
- **WHEN** a citizen nominates inside a nomination window
- **THEN** the nomination is a graph individual of the window's Process class, relating to that citizen and to the enclosing process instance, so several occurrences of one phase coexist without colliding

### Requirement: Oracle runtime interface

Each law SHALL ship a compiled Lean oracle speaking a fixed CLI protocol over JSON: a `list` query naming available ECAs (including `repeat` on quorum flavors), a `check` query taking the instance graph and returning conditions truth values, per-citizen pending actions (including the repeat duty on the authority when the current cycle is void), and violations with structured witnesses, and an `apply` query taking an act-plus-graph envelope and returning the new instance graph (or a JSON rejection naming the failed guard). `check` SHALL stay advisory; `apply` SHALL be the single enforcing path — drivers SHALL request transitions through it and SHALL NOT implement rule semantics themselves. `check`/`apply` SHALL scope phase, pending, and guards to the ongoing process instance while finished instances remain visible for past-dependent rules.

`apply` SHALL receive the whole graph and return the whole updated graph, replacing it wholesale rather than merging into it, so the graph never becomes a second source of truth alongside the oracle's state. A consumer SHALL validate that every subject in a returned graph is typed by a class the ontology declares, and SHALL treat an untyped subject as an error rather than a partial write. The oracle SHALL be total over triples it does not need: conditions select what matters from the graph rather than being told in advance what to look at.

The verdict SHALL NOT carry a field named for any single process concept. Law-specific results SHALL be reported as entries in a generic `readings` list, each naming a law-chosen id, a kind drawn from the closed set `decimal`, `ref`, or `flag`, and a value; a `ref` reading SHALL name the ontology class of the individual it points at so the label resolves. `phase` SHALL remain a top-level reading. A law with no result of a given shape SHALL omit that reading rather than emit a placeholder.

Each violation SHALL carry a structured witness alongside its display string. The witness SHALL name the individuals that break a quantified condition under `refs` and any counts that fell short under `counts`, each count giving a name and a value; this SHALL suffice for the framework FOL subset, whose conditions are universal or existential over finite sets plus counting. A violation SHALL NOT require a law-specific witness field to be interpretable.

Each `pending` entry SHALL carry its ECA together with the parameter slots for it, including the choices available at that instant for any slot sourced from `choices`, so a consumer can present a complete act without reading law-specific state. Each `pending` entry SHALL also name the process instance the duty belongs to, so that duties on concurrently unfolding processes are distinguishable and a consumer can group them under the process they serve.

Because the clock is advanced by the driver rather than by a query, clock values are untrusted input. `check` and `apply` SHALL be total over all `day` and `hour` values, returning a well-formed verdict or a named rejection for any input including values far outside the law's calendar, and SHALL NOT fail on them.

#### Scenario: Missing ballot reported with witness
- **WHEN** the graph has 39 of 40 expected ballots delivered
- **THEN** `check` returns false for all-distributed plus a witness naming the undelivered citizen IRI under `refs`, so the guide can name what is missing without a law-specific field

#### Scenario: Counting failure reported with structured witness
- **WHEN** the graph shows fewer than half the citizens voted at polls close
- **THEN** `check` returns the quorum violation with a witness whose `counts` give the voted and total counts, rather than conveying them only inside the display string

#### Scenario: Double vote rejected with reason
- **WHEN** the consumer requests a vote act for a citizen who already voted with polls open
- **THEN** `apply` returns a rejection naming the already-voted guard instead of a new graph, and the stored graph is unchanged

#### Scenario: Repeat offered as pending
- **WHEN** the graph shows a finished election instance with a failed quorum and an authority in office
- **THEN** `check` returns a pending entry for that citizen with eca `repeat` alongside the quorum violation witness

#### Scenario: Repeat on valid election rejected
- **WHEN** the consumer requests a repeat act on a graph whose quorum is valid
- **THEN** `apply` returns a rejection naming the quorum-not-failed guard and the stored graph is unchanged

#### Scenario: Results reported without a shape change
- **WHEN** a law whose outcome is a number reports it and a law whose outcome is a winning citizen reports that
- **THEN** both appear as `readings` entries differing only in id, kind, and value, and neither needs a verdict field of its own

#### Scenario: Result-free law emits no placeholder
- **WHEN** a law has no result of a given shape
- **THEN** it emits no such reading, and a consumer renders its absence as an absent reading rather than as a null value

#### Scenario: Pending entry carries available choices
- **WHEN** a pending entry has a parameter sourced from `choices`
- **THEN** the verdict names the choices available at that instant, and the consumer builds a complete act from the verdict and the declaration alone

#### Scenario: Pending entry names its process instance
- **WHEN** one citizen holds duties on two concurrently unfolding processes
- **THEN** each pending entry names the process instance it belongs to, so the consumer groups them under separate processes instead of one undifferentiated list

#### Scenario: Act targets a chosen instance
- **WHEN** two instances of one process type are ongoing and a duty on a third is offered
- **THEN** the consumer presents the open instances as a choice and the act names the one selected, with no ambiguity between them

#### Scenario: Absurd clock values stay total
- **WHEN** `check` or `apply` receives a day or hour far outside the law's calendar, including values before its first calendar point
- **THEN** it returns a well-formed verdict or a named rejection rather than failing, underflowing, or erroring

#### Scenario: Clock advanced without an oracle query
- **WHEN** a consumer writes a new `ph:Clock` value into the graph and then calls `check`
- **THEN** the verdict reflects the new position, with no clock-advancement verb required

#### Scenario: Whole graph round-trips
- **WHEN** the consumer sends the whole graph to `apply` and a new graph is returned
- **THEN** the returned graph replaces the stored one wholesale rather than merging into it, so the oracle's state and the graph never diverge

#### Scenario: Irrelevant triples are tolerated
- **WHEN** the graph contains individuals and triples a given law's conditions never address
- **THEN** `check` and `apply` remain well-formed and total, selecting what matters from the graph rather than requiring the framework to have declared in advance what the law needs

#### Scenario: Untyped subject is refused
- **WHEN** an `apply` response contains a subject typed by a class the ontology does not declare
- **THEN** the consumer reports the error and does not commit a partial write