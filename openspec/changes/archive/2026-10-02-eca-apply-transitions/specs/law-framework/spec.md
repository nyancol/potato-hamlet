# Spec Delta

## MODIFIED Requirements

### Requirement: ECA metamodel with bounded FOL subset

Each law SHALL declare its dynamics as ECA rules with Event (clock tick or act), Condition over a state snapshot, Action transition, duty-holder role, deadline, modality (should vs must, preserved from the source text), and display message. Conditions SHALL use only the framework FOL subset: universal/existential quantification over finite sets, counting, Nat comparisons and arithmetic. The Action leg SHALL have an executable encoding: one pure transition function per ECA taking a snapshot to a snapshot (or a rejection reason), guarded by the same conditions the oracle checks, with actions addressed as data (ECA id plus parameters) over JSON.

#### Scenario: All-ballots condition expressed
- **WHEN** the rule "authority must distribute one ballot per candidate to every citizen" is encoded
- **THEN** it reads as a finite universal over citizens and candidates with an existential over delivered ballots, decidable in Lean and evaluable by the oracle

#### Scenario: Modality preserved
- **WHEN** the source text says the authority "should communicate" (announce) but "must create" (ballots)
- **THEN** the two ECAs carry modality should and must respectively, and the guide conveys the difference instead of flattening both to obligations

#### Scenario: Prepare transition executable
- **WHEN** the driver requests the prepare act on a snapshot where prepare is due and an authority holds office
- **THEN** the transition returns a snapshot with the prepared flag set and the full citizen-by-candidate ballot set marked delivered, instead of only reporting that prepare is pending

### Requirement: Oracle runtime interface

Each law SHALL ship a compiled Lean oracle speaking a fixed CLI protocol over JSON: a `list` query naming available ECAs, a `check` query taking a snapshot and returning conditions truth values, per-citizen pending actions, and violations with witnesses, and an `apply` query taking an act-plus-snapshot envelope and returning the new snapshot (or a JSON rejection naming the failed guard). `check` SHALL stay advisory; `apply` SHALL be the single enforcing path — drivers SHALL request transitions through it and SHALL NOT implement rule semantics themselves.

#### Scenario: Missing ballot reported with witness
- **WHEN** a snapshot has 39 of 40 expected ballots delivered
- **THEN** `check` returns false for all-distributed plus the witness (citizen id, candidate id) so the guide can name what is missing

#### Scenario: Double vote rejected with reason
- **WHEN** the driver requests a vote act for a citizen who already voted with polls open
- **THEN** `apply` returns a rejection naming the already-voted guard instead of a new snapshot, and the stored snapshot is unchanged

### Requirement: Guide as non-participant observer

The Spirit of the Hamlet SHALL hold no role, SHALL never be an ECA holder, and SHALL never appear as a `hasParticipant` of any law Process. Every ECA holder SHALL be a GFO Role played by a citizen (e.g. mayor, fallback oldest-person authority, candidate, voter). Process phases derived from state plus Nat time SHALL be exposed as readings for display. Oracle `check` verdicts (phase, pending, witnesses, would-win counts) SHALL be advisory only: counts and winners inform the guide, but proclamation and all other transitions remain human acts owned by their holders. The oracle SHALL never initiate a transition: `apply` executes only driver-requested acts, and no transition fires until the owning citizen acts through the driver.

#### Scenario: Spirit advises, authority proclaims
- **WHEN** the count shows Cara would win with the most votes
- **THEN** the verdict reports "would-win: Cara" while the proclaim duty stays pending on the authority holder, and no transition fires until that citizen acts

#### Scenario: Spirit holds no office
- **WHEN** the mayor ontology is validated
- **THEN** no ECA names the Spirit as holder and no election Process lists it as participant

## ADDED Requirements

### Requirement: Transition table per law

Each law SHALL define the snapshot effect and rejection reasons of every ECA act: announce sets the announced flag; nominate appends the citizen to the registry (rejecting closed registry and duplicates); prepare sets the prepared flag and populates the full delivered ballot set; vote appends exactly one ballot-box entry (rejecting closed polls and double votes); count sets the counted flag; proclaim sets the proclaimed flag and records the winner (rejecting empty candidacy). Quorum flavors SHALL additionally define the repeat act producing a fresh snapshot on the 30-day-later election date with reset registry and ballots.

#### Scenario: Full cycle via apply trace
- **WHEN** a driver plays announce, nominate, prepare, vote, count, and proclaim acts for the 2027 cycle through `apply`
- **THEN** each step returns the lawfully updated snapshot or a named rejection, and the final snapshot shows the winner proclaimed with the oldest-on-tie rule applied
