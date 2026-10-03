# Step 1 prompt — ontology draft (v2)

You are drafting a GFO-light domain ontology for the Potato Hamlet
law-to-simulation framework. Read the law text given after this template,
then output ONE Turtle file to stdout and nothing else.

## Fixed contract (do not invent alternatives)

- Base IRI: `https://potato-hamlet.example/ontology/` with prefix `ph:`.
- Import pinned GFO-light: `https://w3id.org/gfo-light/release/2025-10-01`
  (which extends GFO-core). Also declare `gfo-core:`, `rdfs:`, `rdf:`, `owl:`,
  `xsd:`.
- Every domain class MUST subclass a GFO-light/GFO-core category:
  `Continuant` subclasses via `gfo-light:Object` (independent things:
  Citizen, Townhall, BallotBox, Mailbox, ResultsBoard),
  `gfo-light:ObjectAggregate` (Hamlet, Electorate),
  `gfo-light:InformationObject` (CandidateRegistry, BallotVote, VoteResult,
  the law text itself), `gfo-light:Role` (MayorRole, CandidateRole,
  VoterRole, FallbackAuthorityRole — model BOTH `roleIn` and `playedBy`),
  `gfo-light:Quality` (age and other measurable qualities, reified when
  history matters), `gfo-core:Process` (dynamic phases: announce, nominate,
  create/distribute ballots, cast vote, count, proclaim),
  `gfo-core:State` (static snapshots: RegistryOpen, BallotsReady, PollsOpen,
  PollsClosed, ResultsPosted).
- NEVER use GFO-full categories (Presential, Persistant, Situoid, ...).
- Mirror-by-name: class short names MUST be valid Lean identifiers, because
  `rules.lean` will declare a same-named type per class
  (e.g. `ph:Citizen` <-> `Citizen`).
- Preserve deontic modality from the text as comments on the relevant
  Process (`should` vs `must` vs `may`); the Lean side encodes them as ECA
  modalities.

## Framework invariants (REQUIRED in every law)

These classes are what a law-agnostic consumer relies on. Omitting one fails
the review gate.

- `ph:Citizen rdfs:subClassOf gfo-light:Object .`  Every citizen individual
  must carry `rdfs:label` and a `ph:age` value.
- `ph:Clock rdfs:subClassOf gfo-light:TimeBoundary .`  The current simulated
  position, carrying `ph:dayIndex` and `ph:atHour`.
- `ph:CalendarPoint rdfs:subClassOf gfo-light:TimeBoundary .`  An instant in
  the law's calendar, carrying `rdfs:label`, `ph:atDate`, `ph:dayIndex`, and
  `ph:marksPhase`.
- `ph:CalendarSpan rdfs:subClassOf gfo-light:Chronoid .`  An interval, related
  to its bounding `ph:CalendarPoint`s and optionally carrying `ph:marksPhase`.

Ground the invariant properties as subproperties of GFO's:

- `ph:atDate rdfs:subPropertyOf gfo-core:dateTimeValue .`
- `ph:age`, `ph:atHour`, `ph:dayIndex` each
  `rdfs:subPropertyOf gfo-core:decimalValue .`
- `ph:label rdfs:subPropertyOf rdfs:label .`  (used by runtime individuals)

## TBox only — NO individuals

`ontology.ttl` is a frozen schema: classes and properties ONLY. Do NOT emit
any individual (no `a ph:Citizen`, no cycle individuals, no `rdfs:label` on an
instance). Individuals live at runtime, in two places:

- seeded individuals go in a sibling `population.ttl` (same RDF syntax);
- individuals created during simulation are minted by the oracle.

## Relationship vocabulary (REQUIRED in every law)

A process is a structure, not a name. Declare these framework properties, each
as a subproperty of its GFO counterpart — do NOT reuse the GFO property
directly, so the gate can enumerate them:

- `ph:hasPhase` over `gfo-core:hasSituationPart` — a Process is made of phases
- `ph:hasParticipant` over `gfo-core:hasParticipant`
- `ph:hasTime` over `gfo-core:timeOf` — links a process instance to its
  `Chronoid` interval (a `Chronoid` carries `temporallyStartedBy` /
  `temporallyFinishedBy`; never attach a TimeBoundary straight to a situation)
- `ph:relates` and `ph:containsRole` over `gfo-light:Relator`
- `ph:qualityOf` over `gfo-light:qualityOf`
- `ph:causedBy` over `gfo-core:causedBy` — subject is the affected Process,
  object is the `gfo-core:State` that can bring about the change
- `ph:roleIn` and `ph:playedBy` — model BOTH sides of every Role

## Declare the process hierarchy

Each Process class names its constituent phases as plain class-level
assertions (NOT `someValuesFrom` restrictions, which only assert existence):

    ph:MayorElectionCycle ph:hasPhase ph:AnnounceElection ,
                                     ph:SelfNomination , ...

Every Process class you declare MUST be reachable from a declared root
through `ph:hasPhase`, and every phase MUST be marked by a `ph:CalendarSpan`
carrying `ph:marksPhase`. Do NOT declare a Process class that no ECA, root, or
other phase refers to — an unreferenced class fails the gate.

`gfo-core:State` subclasses are the vocabulary a process moves through
(`RegistryOpen`, `BallotsReady`, `PollsOpen`, `PollsClosed`, `ResultsPosted`);
add your own (e.g. a state meaning "candidacy withdrawn"). To say such a
State can bring about a change in a Process, attach the relation with the
PROCESS as subject and the State as object:

    ph:MayorElectionCycle ph:causedBy ph:CandidacyWithdrawn .

That says the dependency is *permitted*; whether the State actually holds,
and so whether the change fires, is evaluated by the Lean guard and never
asserted here.

## What NOT to declare

- NO `leadsTo`, `resultsFrom`, `causes`, or `causedBy` used as *ordering*
  between phases. Phases overlap, so a chain would assert something false, and
  calendar bounds already answer ordering and overlap from one source.
- NO rule truth. Conditions, guards, holders and winners live in Lean.

## Individuals use full IRIs

Individuals in `population.ttl` use FULL IRIs in angle brackets (a "/" is not
valid in a Turtle prefixed name):
`<https://potato-hamlet.example/ontology/citizen/alice> a ph:Citizen ; ...`.
Snapshot ids in JSON equal these full IRIs.

## The Spirit of the Hamlet is an observer only

NEVER a Role holder, NEVER a `hasParticipant` of any law Process.

## Stability rule (redrafts must diff structurally)

Keep class and property names stable across redrafts. A text change that
only alters a number (e.g. term length 4 -> 2 years) MUST change only
values/comments, never rename classes or reshape the schema. A redraft MUST
NOT reshape the declared process hierarchy: renaming or adding a phase
requires a new review, not a regeneration.

## Calendar contract

The ontology declares the calendar's *shape*; the oracle computes concrete
dates at `apply` time. Declare `ph:CalendarPoint`/`ph:CalendarSpan` as classes
and, where a phase has a window, relate its span via `ph:marksPhase`. Do NOT
emit calendar individuals here — a reviewable cycle's dates belong in
`population.ttl`, and derived dates are minted at runtime.

## Output

Raw Turtle only. No markdown fences, no explanations.

The law text follows after the `---LAW---` marker.
