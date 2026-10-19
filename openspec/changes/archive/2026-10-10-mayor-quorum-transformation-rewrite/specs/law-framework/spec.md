# Spec Delta

## MODIFIED Requirements

### Requirement: Quorum validity with 30-day repeat

Quorum flavors SHALL declare the election valid only if at least half of the citizens cast a vote, and on failure SHALL schedule a repeat election as a NEW election-cycle individual 30 days later with all preparation dates recomputed relative to the new election date (announce at E-10, prepare at E-1, polls 9am-7pm on E-day). The void cycle SHALL be preserved in snapshot history with its outcome (void, turnout, winner if any); the successor SHALL start with a reset candidate registry and a fresh ballot set: prior nominations and ballots do not carry over. The repeat loop SHALL continue until quorum is valid.

Making the ballots and delivering them SHALL be separate acts, because the state in which every ballot has been made and none delivered is a state the simulation represents. A ballot SHALL be grounded in an existing physical individual that takes it on as a Role in the current election, and the candidate it represents SHALL be carried by that Role as a relation from the writing on the sheet to the citizen it names, not as a value on the sheet. The delivered status of a ballot SHALL be ordinary state written by the delivering act rather than fixed when the ballot comes into being. The authority SHALL have a duty to deliver every ballot made, and an act that delivers while any ballot of the current election is undelivered SHALL be refused.

#### Scenario: Failed quorum schedules repeat with fresh prep
- **WHEN** a snapshot shows fewer than half of the citizens voted at polls-close
- **THEN** `check` returns quorum-invalid with the `{voted, total}` witness, names a repeat election date 30 days later, and the repeat's announce/prepare/poll dates derive from the new date with empty registry and ballots pending

#### Scenario: Failed quorum schedules a new cycle preserving history
- **WHEN** a snapshot shows fewer than half of the citizens voted at polls-close on the current cycle
- **THEN** `check` returns quorum-invalid with the `{voted, total}` witness naming a repeat date 30 days later, and after the authority performs `repeat`, the snapshot contains both the void cycle (registry, box, turnout preserved) and the fresh successor (empty registry and ballots)

#### Scenario: Repeat until valid
- **WHEN** the first repeat also fails quorum
- **THEN** a further repeat schedules a third cycle at `E+30` with the same fresh-prep shape, and the two void cycles remain in history

#### Scenario: Made and delivered are different states
- **WHEN** the authority has made the ballots for the current election and delivered none
- **THEN** the graph holds each ballot as an individual carrying its candidate and not yet delivered, so the state is one a consumer can read rather than a count inferred from absence

#### Scenario: A ballot is a role of an existing thing
- **WHEN** the authority writes a candidate's name on a sheet
- **THEN** the sheet is an individual of its own class, a Role individual names it as a ballot in the current election and relates the writing to the citizen named, and no new physical thing came into existence

#### Scenario: The writing is readable before it means anything
- **WHEN** the authority has written on a sheet and the sheet has not been made a ballot
- **THEN** the writing is an individual on the sheet carrying the literal, and nothing resolves it to a citizen, so the two facts are separately readable

#### Scenario: The Role, not the text, resolves the candidate
- **WHEN** a consumer asks which candidate a ballot represents
- **THEN** it reads the election's Role and the relation it carries to a citizen, and never compares the literal on the sheet to a name, so two elections writing the same text differently both resolve correctly

#### Scenario: An instrument the writing needs must exist
- **WHEN** the making act runs and the world contains no instrument to write with
- **THEN** the act is refused naming it, because the law's duty is to write and writing requires something to write with

#### Scenario: Delivery completes before polls
- **WHEN** every ballot made for the current election has been delivered
- **THEN** an act delivering ballots is refused because none remain undelivered, and the same act is refused before the ballots have been made

#### Scenario: The undelivered ballot is nameable
- **WHEN** the graph shows one ballot made for the current election and not delivered
- **THEN** the all-distributed condition's witness names that ballot's individual rather than only reporting a count short, because an undelivered ballot is an individual that exists

#### Scenario: Repeat starts from blank paper again
- **WHEN** a void cycle's successor begins
- **THEN** its ballots are made from the same seeded stock and none of the void cycle's ballots, nominations, or deliveries carry over, and a sheet already written in the void cycle holds no Role in the successor

## ADDED Requirements

### Requirement: Ballot preparation as making then delivering

A quorum flavor's ballot-preparation phase SHALL declare the two duties its law states separately: an act that makes each ballot, and an act that delivers each made ballot to where its recipient receives it. The making act SHALL name the existing individuals it acts on — the sheet and the instrument the writing is done with — and SHALL be refused naming any that the world lacks; it SHALL NOT bring a physical thing into existence to fill a gap. Each ballot it makes SHALL be a Role an existing individual takes on in the current election, and SHALL NOT be fixed as delivered when made. The writing the making act performs SHALL be recorded as an individual related to the sheet and carrying the literal written, so that what was written is readable independently of what it has been made to mean.

The delivering act SHALL be the authority's duty, SHALL be available only once the making act has run for the current election, and SHALL record each delivery against the ballot it delivers so that a ballot's delivered status follows from the graph rather than from a value set when it was created. A delivered ballot SHALL remain in the graph afterwards, and no act SHALL un-deliver it.

#### Scenario: The making act declares what it acts on
- **WHEN** the authority performs the making act and the seeded stock is short of the sheets the registry implies
- **THEN** the act is refused naming the shortfall, rather than creating sheets to fill it

#### Scenario: Delivered status follows from the graph
- **WHEN** the graph shows a delivery recorded for a ballot
- **THEN** that ballot is read as delivered, and a ballot of the same election with no delivery recorded is read as not delivered, with neither fact held only in the oracle

#### Scenario: A delivery is permanent
- **WHEN** a ballot has been delivered and any later act is applied
- **THEN** the delivery record remains in the graph and the ballot is still read as delivered

#### Scenario: No delivery before making
- **WHEN** the authority requests the delivering act before the making act has run for the current election
- **THEN** the act is refused with a guard naming that nothing has been made to deliver