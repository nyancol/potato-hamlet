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
  modalities. `should` leaves a permitted alternative; `must` does not.

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

A day index names a MOMENT, so it must be grounded on the GFO category for
one. Declare `rdfs:domain gfo-light:TimeBoundary` on BOTH `ph:dayIndex` and
`ph:atHour`: the hour of a moment sits on `ph:Clock`, on a `ph:CalendarPoint`,
and on the plain `gfo-light:TimeBoundary` individuals the oracle mints as a
`Chronoid`'s start and finish bounds. A process instance, an occurrence or a
span must NOT carry `ph:dayIndex` or `ph:atHour` — it holds no present of its
own, and a second copy of the clock is a second source for the same fact.

Declare every SINGLE-VALUED property as `owl:FunctionalProperty`. The oracle
re-encodes the whole state on every apply, so a single-valued property must be
written with set-one; the declaration is what lets a consumer tell a
re-encoding from a second value, and what lets the gate catch a set-one that
regressed to an append. Declare functional at least: `ph:label`, `ph:atDate`,
`ph:atHour`, `ph:dayIndex`, `ph:age`, `ph:hasTime`, `ph:cycleIndex`, `ph:outcome`,
and every flag or per-instance field the law rewrites.

Do NOT declare functional any property that may hold several values for one
subject — notably `ph:marksPhase` (one moment may mark several phases),
`ph:hasParticipant`, `ph:playedBy`, `ph:roleIn`, `ph:relates`,
`ph:containsRole`, `ph:qualityOf`, `ph:causedBy`. The oracle appends to those.

Declare every property the oracle WRITES. A property used in `rules.lean` but
absent from `ontology.ttl` is invisible to the gate, which only checks
properties the schema already declares.

## TBox only — NO individuals

`ontology.ttl` is a frozen schema: classes and properties ONLY. Do NOT emit
any individual (no `a ph:Citizen`, no cycle individuals, no `rdfs:label` on an
instance). Individuals live at runtime, in two places:

- seeded individuals go in a sibling `population.ttl` (same RDF syntax);
- individuals created during simulation are minted by the oracle.

## The shared physical vocabulary — draw on it, do not restate it

Governance texts presuppose physical things: a place to meet, a container to put
things in, a surface to write on, an instrument to write with. Those are declared
ONCE, in `framework/physical.ttl`, and resolved alongside this file. Do NOT
re-declare them here: two declarations of one concept leave two laws' versions
unrelated, and the review gate reports the collision.

Named there already: `ph:Townhall`, `ph:Dwelling`, `ph:Mailbox`, `ph:BallotBox`,
`ph:ResultsBoard`, `ph:CandidateRegistry`, `ph:Sheet`. Capabilities there —
classes under `ph:PhysicalCapability` that qualify an object for an action:
`ph:Inscriptible` (something one may inscribe with), `ph:Inscribable` (something
one may inscribe on), `ph:Container` (something a thing may be put into).
Actions there: `ph:Inscribe`, `ph:Deposit`, under `ph:PhysicalAction`.

Referring to one of these is not declaring it. Writing
`ph:CreateBallots ph:hasParticipant ph:Mailbox` USES the concept and restates
nothing.

**Name the physical concepts your law text presupposes, and draw each one from
the shared vocabulary.** The rule: if the class is there, use it; if it is not,
declare it in this file and subclass it under the capability it qualifies for.

Do NOT require a physical concept the law's duties do not concern. A law whose
text presupposes nothing physical — one about paperwork alone — gets no physical
declaration at all, and that is correct: the vocabulary is AVAILABLE, not
required. Only `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint` and `ph:CalendarSpan`
are mandatory, because a consumer cannot operate without them.

**Do NOT narrow where the text left the choice open.** If the text says to
`write` a name without saying with what, the act takes an instrument qualified by
CAPABILITY (`ph:Inscriptible`), not by a named kind — a hamlet stocked with
pencils is not blocked by a class its law never mentioned. Qualify by a named
kind only where the text names it. The review gate reports a narrowing either
way, because it cannot read the text and a human has to.

What a gesture MEANS is the law's own and must be declared here as a Role:
`ph:BallotVote` is a `gfo-light:Role` the sheet takes on in the election
(`ph:roleIn` the process, `ph:playedBy` the sheet), not a class the sheet becomes.
An individual never changes its class as a process unfolds — meaning is a
relation, so the same sheet can be a ballot in one election and something else in
another.

## Relationship vocabulary (REQUIRED in every law)

A process is a structure, not a name. Declare these framework properties, each
as a subproperty of its GFO counterpart — do NOT reuse the GFO property
directly, so the gate can enumerate them:

- `ph:hasPhase` over `gfo-core:hasSituationPart` — a Process is made of phases
- `ph:hasParticipant` over `gfo-core:hasParticipant`
- `ph:hasTime` over `gfo-core:hasTime` — links a process instance to its
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

## Clarification loop — report what you cannot ground

This draft is one pass of an iterative loop, not a one-shot delivery. Deliver
three draft files (ontology.ttl, rules.lean, manifest.yaml) plus the report;
population.ttl rides along only when the pass drafts seeds — unauthored passes
omit it. Alongside
the Turtle file you return a SEPARATE structured report listing every step the
law text requires that no declared object, capability, or action accounts for —
a duty whose mechanism nothing in `framework/physical.ttl` qualifies an object
for, or that no world individual performs. Each entry is `{step, why-ungroundable}`:
quote the step, then say which object, capability, or action is missing.

The report is a separate value conforming to
`framework/clarification-report.schema.json`. It is NEVER a fenced block inside
the draft: the draft files go into the freeze hash verbatim, so anything left
inside them becomes part of the frozen TBox. A validator rejects anything but
the strict shape — free text and fenced blocks do not parse as converged.

Where a declared capability DOES account for the step, proceed and declare
against it, and do not ask. A law that says to write without naming an
instrument gets `ph:Inscriptible`, not a question; a law whose instrument the
text names gets the named kind. The threshold stated only negatively produces
performative reporting — a well-covered law asks nothing.

Do NOT invent a mechanism in order to avoid reporting a step. An invented class
is checkable and a concealed guess is not: a name wired into a superclass,
domain, or range fails the gate by name, while a guess hidden inside a
plausible declaration builds, passes, and reads as if the text determined it.

## Law-derived seeds are drafted by reference, never by restatement

`population.ttl` holds only what the law derives — its calendar, its process
instances, its states, its roles — drafted against the world fixture as
background. Reference world individuals (citizens, furniture, supply, the
clock) by their full IRIs; NEVER restate a world-owned individual. A drafted
seed set must pass the gate over the world merge: a restated IRI fails it the
same way a restated shared class does.

## Output

Raw Turtle only. No markdown fences, no explanations.

The law text follows after the `---LAW---` marker.
