# Spec Delta

## MODIFIED Requirements

### Requirement: Law variant input layout

Each law variant SHALL live under `artefacts/<case>/` with `law.txt` as the single source text, plus generated `ontology.ttl`, `rules.lean`, and `manifest.yaml`, plus `population.ttl` holding the law-derived individuals the law starts from: its calendar, its process instances, its states and its roles. Individuals the hamlet already has — citizens, physical furniture, supply, and the single shared clock — SHALL NOT be restated there; they are referenced by IRI from the framework's world store, which is populated once before any law is proposed. `ontology.ttl` SHALL hold only classes and properties; seeded individuals SHALL live in `population.ttl` in the same RDF serialisation, and individuals created during simulation SHALL be minted into the runtime knowledge graph. `population.ttl` describes what the law permits and not how the oracle works out a moment: it SHALL NOT carry a value whose purpose is to let a consumer reproduce a computation the oracle owns, and SHALL NOT state what an interval is measured from. The TUI SHALL be built only against frozen (reviewed) artefact sets, never against drafts.

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

### Requirement: Explicit review gate to frozen

No artefact set SHALL be consumable by the simulator until a human marks it reviewed, freezing the exact file versions. A freeze SHALL record both the case files' versions and the world version the set was reviewed against. Post-freeze law edits SHALL require a new review, and so SHALL a world version that no longer matches the recorded one: a set reviewed against a world that has since moved is not consumable until re-reviewed.

#### Scenario: TUI refuses drafts
- **WHEN** the TUI is pointed at an artefact set that was edited after its review mark
- **THEN** it refuses to load and names the changed files

#### Scenario: TUI refuses a set whose world moved
- **WHEN** the TUI is pointed at a frozen artefact set whose recorded world version no longer matches the world's current version
- **THEN** it refuses to load and names the world store as the drifted dependency, so a meaning that moved underneath the review prompts a new review instead of a silent reinterpretation
