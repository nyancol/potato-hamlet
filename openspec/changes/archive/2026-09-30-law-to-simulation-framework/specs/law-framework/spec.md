# Spec Delta

## Purpose

Defines the artefact contract that lets one generic simulator run any hamlet law: how governance texts are grounded in GFO-light, how rules are expressed as ECA over Nat-day time, and how Python and Lean exchange state and verdicts.

## ADDED Requirements

### Requirement: Ontology profile grounded in GFO-light

Artefact ontologies SHALL subclass GFO-light/GFO-core categories (Object, ObjectAggregate, Role, Relator, Quality, InformationObject, Process, State, SituationAggregate) with mirror-by-name Lean counterparts, and every simulatable entity SHALL carry an `rdfs:label` for display.

#### Scenario: Mayor ontology validates
- **WHEN** the mayor `ontology.ttl` declares Citizen as `gfo-light:Object`, MayorRole as `gfo-light:Role` with `roleIn` + `playedBy`, and election phases as `gfo-core:Process`/`State`
- **THEN** OWL parsing plus the GFO-light consistency check passes and each class has a same-named Lean type

#### Scenario: Missing label rejected
- **WHEN** an ontology individual lacks `rdfs:label`
- **THEN** the Step 1 review gate fails with the offending IRI named

### Requirement: Nat-day time model

Laws SHALL express time as `Nat` days plus hour integers, with named day arithmetic per cycle (election day, announce day = election day minus 10, prepare day = election day minus 1, polls 9am-7pm on election day). Periodic recurrence SHALL be a Nat function of the cycle index (e.g. election year = 2027 + 4k).

#### Scenario: Election dates derive correctly
- **WHEN** cycle index 0 denotes the 2027 election
- **THEN** announce day, prepare day, and poll hours compute to Jan 2, Jan 11, and 9-19 on Jan 12 respectively

### Requirement: ECA metamodel with bounded FOL subset

Each law SHALL declare its dynamics as ECA rules with Event (clock tick or act), Condition over a state snapshot, Action transition, duty-holder role, deadline, modality (should vs must, preserved from the source text), and display message. Conditions SHALL use only the framework FOL subset: universal/existential quantification over finite sets, counting, Nat comparisons and arithmetic.

#### Scenario: All-ballots condition expressed
- **WHEN** the rule "authority must distribute one ballot per candidate to every citizen" is encoded
- **THEN** it reads as a finite universal over citizens and candidates with an existential over delivered ballots, decidable in Lean and evaluable by the oracle

#### Scenario: Modality preserved
- **WHEN** the source text says the authority "should communicate" (announce) but "must create" (ballots)
- **THEN** the two ECAs carry modality should and must respectively, and the guide conveys the difference instead of flattening both to obligations

### Requirement: OWL-Lean correspondence and snapshot identity

Snapshot entity ids SHALL equal the OWL individual IRIs, so Python-loaded individuals, JSON snapshots, and Lean records denote the same entity. Every ECA action SHALL reference a GFO Process class, every post-state a GFO State class, and every holder a Role class.

#### Scenario: Identity round-trips
- **WHEN** Python loads `ph:citizen/alice` from the `.ttl`, sends a snapshot, and receives a verdict
- **THEN** the verdict references the same id and the TUI resolves its `rdfs:label` for display

### Requirement: Oracle runtime interface

Each law SHALL ship a compiled Lean oracle speaking a fixed CLI protocol over JSON: a `list` query naming available ECAs and a `check` query taking a snapshot and returning conditions truth values, per-citizen pending actions, and violations with witnesses.

#### Scenario: Missing ballot reported with witness
- **WHEN** a snapshot has 39 of 40 expected ballots delivered
- **THEN** `check` returns false for all-distributed plus the witness (citizen id, candidate id) so the guide can name what is missing

### Requirement: Quorum validity with 30-day repeat

Quorum flavors SHALL declare the election valid only if at least half of the citizens cast a vote, and on failure SHALL schedule a repeat election 30 days later with all preparation dates recomputed relative to the new election date (announce at E-10, prepare at E-1, polls 9am-7pm on E-day). The repeat SHALL rerun the full preparation cycle with a reset candidate registry and a fresh ballot set: prior nominations and ballots do not carry over.

#### Scenario: Failed quorum schedules repeat with fresh prep
- **WHEN** a snapshot shows fewer than half of the citizens voted at polls-close
- **THEN** `check` returns quorum-invalid with the `{voted, total}` witness, names a repeat election date 30 days later, and the repeat's announce/prepare/poll dates derive from the new date with empty registry and ballots pending

### Requirement: Guide as non-participant observer

The Spirit of the Hamlet SHALL hold no role, SHALL never be an ECA holder, and SHALL never appear as a `hasParticipant` of any law Process. Every ECA holder SHALL be a GFO Role played by a citizen (e.g. mayor, fallback oldest-person authority, candidate, voter). Process phases derived from state plus Nat time SHALL be exposed as readings for display. Oracle verdicts (phase, pending, witnesses, would-win counts) SHALL be advisory only: counts and winners inform the guide, but proclamation and all other transitions remain human acts owned by their holders.

#### Scenario: Spirit advises, authority proclaims
- **WHEN** the count shows Cara would win with the most votes
- **THEN** the verdict reports "would-win: Cara" while the proclaim duty stays pending on the authority holder, and no transition fires until that citizen acts

#### Scenario: Spirit holds no office
- **WHEN** the mayor ontology is validated
- **THEN** no ECA names the Spirit as holder and no election Process lists it as participant
