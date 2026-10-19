# Spec Delta

## MODIFIED Requirements

### Requirement: Law variant input layout

Each law variant SHALL live under `artefacts/<case>/` with `law.txt` as the single source text, plus generated `ontology.ttl`, `rules.lean`, and `manifest.yaml`, plus `population.ttl` holding the law-derived individuals the law starts from: its calendar, its process instances, its states and its roles. Individuals the hamlet already has — citizens, physical furniture, supply, and the single shared clock — SHALL NOT be restated there; they are referenced by IRI from the framework's world store, which is populated once before any law is proposed. `ontology.ttl` SHALL hold only classes and properties; seeded individuals SHALL live in `population.ttl` in the same RDF serialisation, and individuals created during simulation SHALL be minted into the runtime knowledge graph. `population.ttl` describes what the law permits and not how the oracle works out a moment: it SHALL NOT carry a value whose purpose is to let a consumer reproduce a computation the oracle owns, and SHALL NOT state what an interval is measured from. The TUI SHALL be built only against frozen (reviewed) artefact sets, never against drafts.

A shared physical vocabulary SHALL be resolvable alongside every case's artefacts, declaring the classes governance texts presuppose — the things a duty is performed on, with, or towards — each subclassed in GFO and carrying `rdfs:label`. It MAY also declare named kinds beneath a capability it already declares, so that a law whose text leaves an instrument open is not made narrower by the file offering kinds: which kinds exist is the world's business, and a law qualifies by the capability rather than by a kind unless its own text names one. It SHALL be a framework artefact in its own right rather than part of any case, so that a concept a law's text presupposes is declared once and every law referring to it refers to the same class. It SHALL be available to every law and required of none: a law whose text presupposes nothing physical SHALL load and pass without drawing on it, and a law SHALL NOT be required to declare, seed, or otherwise account for a concept its duties do not concern.

A law needing a physical concept the shared vocabulary does not declare MAY declare it locally, which is the point at which the two vocabularies diverge and the concept belongs to that law alone. A class a law declares locally that the shared vocabulary also declares SHALL be reported by the review gate naming both, rather than one silently taking precedence. A class referenced from the shared vocabulary SHALL count as declared for every check that requires a subject to be typed by a declared class, so drawing on the vocabulary needs no exemption from the transformation requirement's input check.

#### Scenario: New flavor scaffolded
- **WHEN** an author adds `artefacts/mayor-quorum/law.txt` with a quorum-validity plus 30-day-repeat clause
- **THEN** the harness generates draft artefacts under the same directory without touching the frozen mayor baseline or the TUI

#### Scenario: Seeds live outside the ontology
- **WHEN** a law starts from a named calendar and named process instances over citizens the world already names
- **THEN** `ontology.ttl` declares the classes and properties describing them, `population.ttl` holds the law-derived individuals in RDF, and the citizens are referenced by IRI from the world store rather than restated, so the frozen ontology stays a schema and no bespoke seed-to-instance mapping is needed

#### Scenario: A seed states no method
- **WHEN** a law fixes an interval such as a repeat delay
- **THEN** `population.ttl` records the interval once as `ph:gapDays` on the calendar node bounding the phase, and says nothing about how the resulting moment is derived, because that computation belongs to the oracle and reproducing it in the seed would make the seed a second source for it

#### Scenario: A seed value the oracle never reads is rejected
- **WHEN** a draft seeds a property that duplicates a constant the oracle holds in its own rules, such as an interval kept on a process instance
- **THEN** the review gate fails naming the property and the individual, since a value no condition consults is a description of nothing the law permits

#### Scenario: World furniture restated in a case is rejected
- **WHEN** a draft's `population.ttl` declares an individual the world store already owns, such as a citizen, a mailbox, or a sheet
- **THEN** the review gate fails naming the IRI, since the world is populated once and a law reaches its furniture by reference rather than by restatement

#### Scenario: A law with no physical duties draws on nothing
- **WHEN** a law's text presupposes nothing physical and its artefacts reference no shared class
- **THEN** the set is freezable and the gate passes, because the vocabulary is available and not required

#### Scenario: One mailbox across two laws
- **WHEN** two laws' texts both refer to a citizen's mailbox
- **THEN** both refer to the same shared class, so a consumer reading either law resolves the same kind of thing and neither law invented a private one

#### Scenario: Offering kinds does not narrow a law that left the choice open
- **WHEN** the shared vocabulary declares named kinds beneath a capability, and a law whose text names no kind of instrument requires that capability
- **THEN** the law's requirement is satisfied by any individual bearing the capability, the gate reports no narrowing, and a hamlet stocked with one kind is not refused an act the law's own text left to the world

#### Scenario: A concept the vocabulary lacks is declared locally
- **WHEN** a law's text presupposes something the shared vocabulary does not declare
- **THEN** the law declares it in its own `ontology.ttl` and the set is freezable, because the shared vocabulary is a stage laws perform on rather than a catalogue of every noun a governance text might use

#### Scenario: A local redeclaration is reported
- **WHEN** a law declares a class locally that the shared vocabulary also declares
- **THEN** the review gate reports the collision naming both declarations, so the divergence is visible rather than resolved silently

#### Scenario: A shared-typed individual satisfies the type check
- **WHEN** a law's act acts on an individual whose class comes from the shared vocabulary
- **THEN** the individual counts as typed by a declared class for every check that requires it, so drawing on the shared vocabulary needs no exemption

### Requirement: Assisted generation with pinned prompt

The harness SHALL generate draft artefacts via a versioned prompt template pinned to the framework contract (GFO-light mapping, the framework-invariant classes with their GFO grounding, the grounded relationship vocabulary, the declared process hierarchy, ECA shape, Nat-day arithmetic, mirror-by-name rule, snapshot field naming, and act parameter and holder-role declarations), so redrafts stay structurally comparable. The prompt SHALL require the process hierarchy to be generated from the law text, and SHALL NOT ask for causal or conditional relations, which belong to the Lean conditions.

The prompt SHALL also ask the author to name the physical concepts the law text presupposes and to draw on the shared physical vocabulary for each one it recognises, declaring a class locally only for a concept the vocabulary does not carry. It SHALL NOT require a concept the law's duties do not concern, so a law with no physical duties is not given one.

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

#### Scenario: Physical concepts named from the text
- **WHEN** the harness drafts the mayor law, whose text performs duties on a mailbox, a ballot box, a townhall, and a board
- **THEN** the draft refers to those through the shared vocabulary rather than declaring private classes, and declares locally only what the vocabulary does not carry

#### Scenario: No physical duty, no physical class
- **WHEN** the harness drafts a law whose text presupposes nothing physical
- **THEN** the prompt produces no physical declaration for it, so availability is not read as an obligation

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

### Requirement: Explicit review gate to frozen

No artefact set SHALL be consumable by the simulator until a human marks it reviewed, freezing the exact file versions. A freeze SHALL record both the case files' versions and the world version the set was reviewed against, as well as which version of the shared physical vocabulary the set was frozen against. Post-freeze law edits SHALL require a new review, and so SHALL a world version that no longer matches the recorded one: a set reviewed against a world that has since moved is not consumable until re-reviewed. A freeze SHALL cover the shared physical vocabulary as well as the case's own files, so that verification can say which vocabulary moved rather than only that something did.

#### Scenario: TUI refuses drafts
- **WHEN** the TUI is pointed at an artefact set that was edited after its review mark
- **THEN** it refuses to load and names the changed files

#### Scenario: TUI refuses a set whose world moved
- **WHEN** the TUI is pointed at a frozen artefact set whose recorded world version no longer matches the world's current version
- **THEN** it refuses to load and names the world store as the drifted dependency, so a meaning that moved underneath the review prompts a new review instead of a silent reinterpretation

#### Scenario: A moved vocabulary invalidates the freeze
- **WHEN** the shared physical vocabulary changes after a case was frozen
- **THEN** verification fails for that case and names the vocabulary as the changed artefact, so a set cannot verify against a vocabulary it was not reviewed with

#### Scenario: The frozen vocabulary version is recorded
- **WHEN** a case is frozen
- **THEN** its manifest names the version of the shared vocabulary it was reviewed against, so upgrading the vocabulary prompts an informed re-review rather than an automatic one
