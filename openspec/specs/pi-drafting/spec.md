# pi-drafting

## Purpose

The pi session that turns a hamlet governance text into a converged, gate-passing law draft by running the clarification loop as code rather than by hand-pasting prompts.

## Requirements

### Requirement: Session command owns the clarification loop

The pi extension SHALL provide a `/draft-law` session command that runs the clarification loop for a case under `cases/<case>/`: render the versioned prompts, extract drafts plus the extractor's report, validate the report, and run the repo's own gate over the world fixture. While the report is non-empty the command SHALL put each reported step to the author as a question and re-extract with the answers. Each pass SHALL be self-contained: answers are fed back as fresh-pass context, not accumulated as conversation state.

#### Scenario: Converging run presents a complete draft

- **WHEN** the author answers every reported step and a later pass returns an empty report with drafts the gate passes
- **THEN** the command presents the draft as complete, and only then

#### Scenario: Unanswered questions stop the run

- **WHEN** a pass reports steps the author does not answer
- **THEN** the command writes its drafts plus the strict report and stops with a non-zero outcome rather than presenting the draft as complete or inventing answers

### Requirement: Schema-bound report tool

The extension SHALL expose a `report_ungroundable_steps` tool bound to the project-owned schema (`framework/clarification-report.schema.json`): the tool SHALL return the three draft files plus the report as structured data. Drafts stay inline — the handoff is self-contained — with a sha256 ack receipt quoted per draft. The tool SHALL return its result as content blocks (never a bare string, which the host renderer cannot consume), accept an optional caller-supplied `passId`, and echo it back so the loop can correlate receipts with passes; a redelivered `passId` SHALL NOT open a second question round. Callers SHALL read the report from the structured data, never from free text — a pass that phrases uncertainty politely in prose SHALL NOT parse as converged, and only the strict shape counts.

#### Scenario: Free text does not converge the loop

- **WHEN** a pass emits uncertainty as prose without a schema-conforming structured report
- **THEN** the command treats the pass as unconverged and re-extracts rather than terminating

#### Scenario: Clean handoff receipt

- **WHEN** a pass delivers schema-conforming drafts plus report with a `passId`
- **THEN** the tool result renders without error, quotes one sha256 per draft matching the delivered bytes, and echoes the `passId`, so the caller can confirm receipt distinctly from a render failure

#### Scenario: Redelivery asks nothing twice

- **WHEN** a pass arrives bearing an already-consumed `passId`
- **THEN** the loop records it as a duplicate receipt and asks no question twice, rather than opening a second question round

### Requirement: Gate wrapper tools call the repo's own gate

The extension SHALL wrap the repo's `check`, `build`, and `freeze` scripts as the tools the session calls, so the session judges drafts with the same gate CI runs rather than a reimplementation. A draft the wrapper gate refuses SHALL NOT be presented as complete, and the refusal SHALL name the finding.

#### Scenario: Gate refusal blocks completion

- **WHEN** the report is empty but the gate refuses the draft, naming an undeclared reference
- **THEN** the command reports the finding and stops rather than presenting the draft as complete

### Requirement: Question UI with a no-progress guard

The session SHALL put each reported step to the author as a question rather than proceeding on a guess, and SHALL keep an asked-set across passes: a step that was asked about and comes back ungrounded SHALL NOT be asked again. When every outstanding step was already asked, the command SHALL record the stall and stop rather than spin.

#### Scenario: Stalled step stops the loop

- **WHEN** an answered step returns ungrounded on the next pass
- **THEN** the command records no-progress and stops instead of re-asking it, and no step appears as a question twice in one run

### Requirement: Headless runs write and exit

A headless run with no user interface (`pi -p`) SHALL write its drafts plus the strict report and exit non-zero while any report entries remain, never inventing answers. An empty report plus a passing gate SHALL exit zero.

#### Scenario: Headless run with questions outstanding

- **WHEN** a `pi -p` run ends with the report non-empty
- **THEN** drafts plus the report are written and the run exits non-zero, so nothing downstream mistakes an unconverged draft for a finished one

### Requirement: Credential-gated end-to-end testing

The real command loop SHALL be tested end-to-end only when a model credential exists; without one those tests SHALL skip. The always-on floor SHALL remain the credential-free contract tests (schema validator, headless driver plus deterministic fake), which run on every commit with no key.

#### Scenario: CI without a credential

- **WHEN** the suite runs where no model credential exists
- **THEN** the contract tests run and pass, and the end-to-end loop tests skip rather than fail
