# Spec Delta

## MODIFIED Requirements

### Requirement: Assisted generation with pinned prompt

The harness SHALL generate draft artefacts via a versioned prompt template pinned to the framework contract (GFO-light mapping, the framework-invariant classes with their GFO grounding, the grounded relationship vocabulary, the declared process hierarchy, ECA shape, Nat-day arithmetic, mirror-by-name rule, snapshot field naming, and act parameter and holder-role declarations), so redrafts stay structurally comparable. The prompt SHALL require the process hierarchy to be generated from the law text, and SHALL NOT ask for causal or conditional relations, which belong to the Lean conditions.

Generation SHALL be iterative rather than one-shot, driven by a pi session with `law.txt`, the framework contract and the shared populated world as background. On each pass the extractor SHALL report every step of the law text it cannot translate into the physical world — a duty whose mechanism no declared object, capability or action accounts for, or that no world individual performs — and the session SHALL put those steps to the author as questions rather than proceed on a guess. Generation SHALL be complete only when the extractor reports none, and nothing SHALL present a draft as complete while any remain. The report SHALL be a separate structured value conforming to the project-owned schema, never a fenced block inside a draft; a headless run with questions outstanding SHALL write its drafts plus the report and exit non-zero rather than invent answers.

The threshold is the extractor's own uncertainty, and nothing SHALL ask about a step it can ground. Where a step can be translated by choosing among the objects and capabilities the shared vocabulary already declares, acting on individuals the shared world already contains, the extractor SHALL proceed and encode that choice as an ordinary declaration in `ontology.ttl` or `rules.lean`, because that is where the choice belongs and where the review gate already examines it. Recording such a choice in a separate artefact would be wrong twice over: it duplicates a fact the declarations already carry, and it implies a class of recorded doubt the process does not have.

The session SHALL draft only the law overlay — law TBox, law-derived seeds, Lean, manifest — reading the shared populated world read-only and referencing its individuals by IRI. It SHALL NOT restate a world-owned individual.

No record of the exchange SHALL be kept. The deliverable is the draft, and an answer given in the course of drafting belongs in the declarations that answer changed, not in a second place beside them.

The gate SHALL enforce what the process promises, and a check SHALL cover the shape the existing ones miss. A draft whose generation did not converge names something no declared class, property or capability accounts for. An individual typed by an undeclared class is already refused by the population check and an undeclared property by seed parity, but **a class naming an undeclared superclass, domain or range is not**: grounding asks whether a class reaches GFO, which an invented name wired alongside a real superclass does not disturb. The frozen-TBox check SHALL therefore require every `ph:` class a declaration names, as a superclass, a domain or a range, to be itself declared; only `ph:` names need resolve, since a GFO class is legitimately external and grounding is what judges it.

The gate SHALL NOT crash on a malformed artefact set. A check that cannot complete on one SHALL report that it could not, naming the failure, so that a caller running the gate as a precondition — `freeze.py` does — sees the finding rather than a traceback.

#### Scenario: Redraft diff is structural
- **WHEN** the mayor law text changes only the term length from 4 to 2 years
- **THEN** the regenerated draft diff shows changed time arithmetic and deadlines, not renamed classes or a reshaped state schema

#### Scenario: Generated artefacts satisfy the framework invariants
- **WHEN** the session drafts a law that names only a custom process with its own vocabulary
- **THEN** the draft still declares `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint`, and `ph:CalendarSpan` with GFO grounding, places law-derived seeded individuals in `population.ttl`, and references world individuals by IRI without restating them

#### Scenario: Generated ontology carries a hierarchy
- **WHEN** the harness drafts a law whose text describes a process made of named stages
- **THEN** the draft declares each Process class's constituents through `ph:hasPhase` as grounded subproperties of `gfo-core:hasSituationPart`, rather than leaving the process as an unelaborated class

#### Scenario: Prompt requests are verified, not trusted
- **WHEN** a draft omits the `roleIn` and `playedBy` relations the prompt requires
- **THEN** the gate fails naming the missing relation, so an unfulfilled prompt instruction cannot reach the review gate unnoticed

#### Scenario: A step the extractor can ground is not asked about
- **WHEN** a law requires a duty performed with an instrument but names no kind of instrument, and the shared vocabulary declares a capability covering it
- **THEN** the extractor proceeds and declares the duty against that capability, and no question is put to the author, because the choice is expressible in the declarations the gate already reviews

#### Scenario: A step the extractor cannot ground is asked about
- **WHEN** a law requires a step for which the shared vocabulary declares no object, capability or action accounting for it
- **THEN** the session asks the author what the step consists of, and does not present the draft as complete until answered, rather than inventing a mechanism and encoding it

#### Scenario: An answer lands in the declarations, not beside them
- **WHEN** an author's answer changes what a class means, or which class a duty is performed on
- **THEN** `ontology.ttl` or `rules.lean` carries the answer as an ordinary declaration, and no separate file records either the question or its answer

#### Scenario: A loop that stopped early is refused
- **WHEN** generation is presented as complete while the draft still refers to a class no ontology declares, whether by typing a seeded individual by it, by making a class its subclass, or by giving a property its domain or range
- **THEN** the gate fails naming the undeclared class, so a draft resting on an unanswered question cannot be frozen

#### Scenario: A headless run with questions outstanding is not complete
- **WHEN** a headless run ends with the report non-empty
- **THEN** it has written its drafts plus the schema-conforming report and exited non-zero, so nothing downstream can mistake an unconverged draft for a finished one

#### Scenario: A malformed set is reported rather than crashing the gate
- **WHEN** a check cannot complete because the artefact set is malformed
- **THEN** the gate reports the failure under that check's name and continues, so a caller running the gate as a precondition sees the finding instead of a traceback

#### Scenario: The vocabulary's coverage bounds how often the loop interrupts
- **WHEN** two laws' texts both need a concept the shared vocabulary does not declare, so both drafts put the same question to their authors
- **THEN** the repeated question is evidence the shared stage lacks a concept every law can reach for, rather than a question each law should answer for itself
