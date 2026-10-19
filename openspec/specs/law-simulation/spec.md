# law-simulation

## Purpose

Gives hamlet inhabitants an interactive Spirit of the Hamlet guide that, for any conforming law, walks them through the lifecycle of every process the hamlet is running: what each process is made of, when its parts run, what is happening now, what is blocked and why, and what each selected citizen is required to do — with every transition performed only by the citizen and all rule truth coming from Lean.

## Requirements

### Requirement: Generic loading of frozen artefact sets

The TUI SHALL load any frozen artefact set — the schema in `ontology.ttl`, the seed instances in `population.ttl`, display declarations in `manifest.yaml`, and the compiled oracle named by the manifest — with zero code changes per law. Swapping artefact sets SHALL fully swap the simulated law. The TUI SHALL refuse a set whose freeze mark does not verify, or whose manifest ECA ids do not match the oracle's `list`, naming the offending files rather than loading partially.

#### Scenario: Second flavor runs unmodified
- **WHEN** the reviewed `mayor-quorum` artefact set, which declares a `repeat` ECA absent from the mayor baseline, is loaded into the shipped TUI binary
- **THEN** the guide renders and plays the repeat election with no TUI code change; success is defined as unmodified-binary law swap

#### Scenario: Unfrozen or mismatched set refused
- **WHEN** the TUI is pointed at a set whose files changed after its freeze mark, or whose manifest declares an ECA the oracle does not list
- **THEN** it refuses to load and names the mismatching files or ids

### Requirement: Process structure and schedule from the artefacts

The TUI SHALL render, for the law it has loaded, the process hierarchy declared in the ontology and the window of each declared phase from its calendar span, reading both from the frozen artefacts without computing or reconciling them. The TUI SHALL display phases as concurrent where their spans overlap rather than presenting them as an ordered sequence. The TUI SHALL NOT derive whether a phase is currently running from the calendar; that is the oracle's `phase` reading.

#### Scenario: Election renders as a tree with windows
- **WHEN** the mayor set is loaded
- **THEN** the guide shows the election as a process containing announce, nomination, ballot creation, voting, counting, and proclaiming, each with its own day window read from the calendar

#### Scenario: Overlapping phases shown as concurrent
- **WHEN** the nomination window and the announce point both cover day 0
- **THEN** the guide shows both as running, with no arbitrary ordering between them

#### Scenario: Guide never decides what is current
- **WHEN** a declared window and the oracle's `phase` reading appear to disagree
- **THEN** the guide surfaces the disagreement as a warning and displays the oracle's reading, rather than resolving it itself

### Requirement: Every process shown, with the process selectable

The TUI SHALL display every process instance in the graph, distinguishing those initialised and awaiting a trigger, those ongoing, and those finished with an outcome, and SHALL show concurrently unfolding processes side by side rather than one at a time. When the selected citizen holds duties on more than one process, the TUI SHALL tag each duty with the process it belongs to and SHALL let the user select a process to act within that one. The TUI SHALL NOT choose on the user's behalf which of a citizen's processes takes priority.

#### Scenario: Concurrent processes both visible
- **WHEN** an election and a budget period are both unfolding and the selected citizen holds a duty on each
- **THEN** the guide displays both processes and shows the citizen's two duties, each attributed to its own process

#### Scenario: Acting in the context of a chosen process
- **WHEN** two instances of one process type are ongoing and the citizen's duty applies to one of them
- **THEN** selecting a process narrows the guide to that instance and offers the duty with its target selectable

#### Scenario: No priority chosen for the citizen
- **WHEN** a citizen owes duties on three processes at once
- **THEN** all three are presented and the user chooses, with the guide making no recommendation of which matters most

### Requirement: Time advance and citizen selection

The TUI SHALL let the user advance the `ph:Clock` position, select any citizen, and view that citizen's roles as the law reports them. The TUI SHALL own the clock as its only local state change, and SHALL NOT offer any other transition outside `oracle apply`. The TUI SHALL NOT decide who holds a duty when no office is filled; it reads the holder from the verdict.

#### Scenario: Oldest person sees authority duties pre-election
- **WHEN** no mayor holds office and the fallback-authority citizen is selected on the announce day
- **THEN** the pending list shows the announce duty owned by that citizen, naming the role the law assigns it

#### Scenario: Clock advances without a subprocess round trip
- **WHEN** the user steps the clock forward
- **THEN** the displayed position changes immediately and the next check reflects it, with no clock-advancement call to the oracle

### Requirement: Pending duties from oracle verdicts, performed only by the citizen

For the selected citizen at the current time, the TUI SHALL display pending actions derived from oracle `check` verdicts, conveying each rule's declared modality, label, and message, and naming the process instance each belongs to. It SHALL build every actionable control from the manifest's declared `holder_role` and parameters, sourcing any `choices` parameter from the options the verdict supplies. The TUI SHALL perform a pending action only on the user's explicit confirmation, by sending it to `oracle apply` and adopting the returned graph, and SHALL append a log entry for each. The TUI SHALL never auto-apply a transition, advance a phase, or proclaim a result.

#### Scenario: Citizen nominates and votes
- **WHEN** Bob is selected during the nomination window and later during polls-open
- **THEN** the guide offers nominate-self, then cast-vote with the candidate selectable, and after each explicit confirmation the graph and log reflect the change on the next check

#### Scenario: Would-win is not proclaimed
- **WHEN** a reading shows a citizen would win but the authority has not yet proclaimed
- **THEN** the guide reports the count as advisory, the proclaim duty stays pending on the authority holder, and no office changes until that citizen confirms the proclaim act

#### Scenario: Guide offers nothing the law does not permit
- **WHEN** a law declares an act the TUI has never seen
- **THEN** the guide still offers it, rendered from its declared label, message, modality, and parameters, with no TUI change

### Requirement: Blocks explained with structured witnesses

When no action is available but a process cannot advance, the TUI SHALL show the failed condition together with the witness data from the verdict: the individuals named under `refs` and the counts named under `counts`, resolved to labels through the graph. The TUI SHALL NOT recover counts or identities by parsing the verdict's display string.

#### Scenario: Incomplete distribution blocks polls
- **WHEN** one ballot is undelivered on the prepare day
- **THEN** the guide shows the distribution condition unmet and names the missing citizen and candidate by label

#### Scenario: Quorum failure shows the counts
- **WHEN** fewer than half the citizens have voted at polls-close
- **THEN** the guide shows the quorum condition unmet with the voted and total figures as numbers, and shows the repeat duty pending on the authority alongside it

### Requirement: Oracle subprocess discipline and graph custody

Rule truth SHALL come from the compiled Lean oracle per check and per act, with the knowledge graph as the only representation of state, and with execution that never freezes the interface. The TUI SHALL send the whole graph to `apply`, adopt the whole returned graph, and refuse to commit any returned subject typed by a class the ontology does not declare. The TUI SHALL own the clock and display; Lean SHALL own condition truth, obligations, winner computation, violations, and every state transition.

#### Scenario: Full mayor cycle guided
- **WHEN** a user plays announce, nominate, prepare, vote, count, and proclaim for a cycle
- **THEN** the oracle confirms each precondition, computes the winner with oldest-on-tie, and the log shows a complete lawful cycle with the office changed only at the proclaim act

#### Scenario: Rejected act leaves state untouched
- **WHEN** a user confirms an act whose guard the oracle rejects
- **THEN** the guide reports the named rejection reason and the graph is unchanged

#### Scenario: Interface stays responsive during a check
- **WHEN** a check is in flight
- **THEN** the user can still advance the clock and change selection, and the interface does not block

#### Scenario: Undeclared subject refuses the write
- **WHEN** an `apply` response contains a subject the ontology does not declare
- **THEN** the guide reports the error and keeps the previous graph rather than committing a partial write
