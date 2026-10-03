# Spec Delta

## MODIFIED Requirements

### Requirement: Ontology profile grounded in GFO-light

Artefact ontologies SHALL subclass GFO-light/GFO-core categories (Object, ObjectAggregate, Role, Relator, Quality, InformationObject, Process, State, SituationAggregate) with mirror-by-name Lean counterparts, and every simulatable entity SHALL carry an `rdfs:label` for display. Each election cycle SHALL be an individual of the law's election-cycle Process class (e.g. `ph:MayorElectionCycle`) carrying an `rdfs:label` naming the election (e.g. "Repeat election, Feb 11 — scheduled") and date datatype properties for its election, announce, and prepare days. Cycle IRIs SHALL be deterministic from `(case, index)`.

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

### Requirement: Nat-day time model

Laws SHALL express time as `Nat` days plus hour integers, with named day arithmetic per cycle (election day, announce day = election day minus 10, prepare day = election day minus 1, polls 9am-7pm on election day). Periodic recurrence SHALL be a Nat function of the cycle index (e.g. election year = 2027 + 4k). Quorum repeats SHALL derive per-repeat dates as a Nat function of the repeat index (`E(k+1) = E(k)+30`, announce at `E-10`, prepare at `E-1`, polls 9am-7pm on E-day). Repeats SHALL NOT shift the 4-year election clock; they only shorten the mandate in office.

#### Scenario: Election dates derive correctly
- **WHEN** cycle index 0 denotes the 2027 election
- **THEN** announce day, prepare day, and poll hours compute to Jan 2, Jan 11, and 9-19 on Jan 12 respectively

#### Scenario: Repeat dates derive per index
- **WHEN** the void election sits at E-day 10
- **THEN** repeat index 1 computes to E-day 40, announce day 30, prepare day 39, and polls 9am-7pm on day 40

#### Scenario: Four-year clock unaffected
- **WHEN** two repeats slip the 2027 election into March
- **THEN** the 2031 election date is unchanged

### Requirement: ECA metamodel with bounded FOL subset

Each law SHALL declare its dynamics as ECA rules with Event (clock tick or act), Condition over a state snapshot, Action transition, duty-holder role, deadline, modality (should vs must, preserved from the source text), and display message. Conditions SHALL use only the framework FOL subset: universal/existential quantification over finite sets, counting, Nat comparisons and arithmetic. The Action leg SHALL have an executable encoding: one pure transition function per ECA taking a snapshot to a snapshot (or a rejection reason), guarded by the same conditions the oracle checks, with actions addressed as data (ECA id plus parameters) over JSON. Quorum flavors SHALL declare `repeat` as a first-class ECA whose holder is the authority (mayor-or-oldest, same `authorityId` as announce/prepare/count/proclaim), whose modality is `must`, and whose message names the scheduled successor.

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

### Requirement: OWL-Lean correspondence and snapshot identity

Snapshot entity ids SHALL equal the OWL individual IRIs, so Python-loaded individuals, JSON snapshots, and Lean records denote the same entity. Every ECA action SHALL reference a GFO Process class, every post-state a GFO State class, and every holder a Role class. Snapshots SHALL carry the full election-cycle history as a list of cycle records; each cycle id SHALL equal its OWL cycle individual IRI; only population (`citizens`) and office (`mayorId`) live outside the cycle list, and the current cycle is the last element.

#### Scenario: Identity round-trips
- **WHEN** Python loads `ph:citizen/alice` from the `.ttl`, sends a snapshot, and receives a verdict
- **THEN** the verdict references the same id and the TUI resolves its `rdfs:label` for display

#### Scenario: Cycle identity round-trips
- **WHEN** the driver sends a snapshot with two cycles and receives a verdict
- **THEN** the verdict references cycle IRIs that resolve to the same `.ttl` individuals and labels the TUI displays

### Requirement: Oracle runtime interface

Each law SHALL ship a compiled Lean oracle speaking a fixed CLI protocol over JSON: a `list` query naming available ECAs (including `repeat` on quorum flavors), a `check` query taking a snapshot and returning conditions truth values, per-citizen pending actions (including the repeat duty on the authority when the current cycle is void), and violations with witnesses, and an `apply` query taking an act-plus-snapshot envelope and returning the new snapshot (or a JSON rejection naming the failed guard). `check` SHALL stay advisory; `apply` SHALL be the single enforcing path — drivers SHALL request transitions through it and SHALL NOT implement rule semantics themselves. `check`/`apply` SHALL scope phase, pending, and guards to the current cycle while history remains visible for past-dependent rules.

#### Scenario: Missing ballot reported with witness
- **WHEN** a snapshot has 39 of 40 expected ballots delivered
- **THEN** `check` returns false for all-distributed plus the witness (citizen id, candidate id) so the guide can name what is missing

#### Scenario: Double vote rejected with reason
- **WHEN** the driver requests a vote act for a citizen who already voted with polls open
- **THEN** `apply` returns a rejection naming the already-voted guard instead of a new snapshot, and the stored snapshot is unchanged

#### Scenario: Repeat offered as pending
- **WHEN** a snapshot shows a void current cycle with an authority in office
- **THEN** `check` returns a pending entry for that citizen with eca `repeat` alongside the quorum violation witness

#### Scenario: Repeat on valid election rejected
- **WHEN** the driver requests a repeat act on a quorum-valid snapshot
- **THEN** `apply` returns a rejection naming the quorum-not-failed guard and the stored snapshot is unchanged

### Requirement: Quorum validity with 30-day repeat

Quorum flavors SHALL declare the election valid only if at least half of the citizens cast a vote, and on failure SHALL schedule a repeat election as a NEW election-cycle individual 30 days later with all preparation dates recomputed relative to the new election date (announce at E-10, prepare at E-1, polls 9am-7pm on E-day). The void cycle SHALL be preserved in snapshot history with its outcome (void, turnout, winner if any); the successor SHALL start with a reset candidate registry and a fresh ballot set: prior nominations and ballots do not carry over. The repeat loop SHALL continue until quorum is valid.

#### Scenario: Failed quorum schedules repeat with fresh prep
- **WHEN** a snapshot shows fewer than half of the citizens voted at polls-close
- **THEN** `check` returns quorum-invalid with the `{voted, total}` witness, names a repeat election date 30 days later, and the repeat's announce/prepare/poll dates derive from the new date with empty registry and ballots pending

#### Scenario: Failed quorum schedules a new cycle preserving history
- **WHEN** a snapshot shows fewer than half of the citizens voted at polls-close on the current cycle
- **THEN** `check` returns quorum-invalid with the `{voted, total}` witness naming a repeat date 30 days later, and after the authority performs `repeat`, the snapshot contains both the void cycle (registry, box, turnout preserved) and the fresh successor (empty registry and ballots)

#### Scenario: Repeat until valid
- **WHEN** the first repeat also fails quorum
- **THEN** a further repeat schedules a third cycle at `E+30` with the same fresh-prep shape, and the two void cycles remain in history
