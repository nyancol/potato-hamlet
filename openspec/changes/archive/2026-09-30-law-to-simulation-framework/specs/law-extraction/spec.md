# Spec Delta

## Purpose

Turns a hamlet governance text into reviewed, machine-checked simulation artefacts quickly, so law flavors can be iterated (reword, regenerate, diff, review) before anything downstream depends on them.

## ADDED Requirements

### Requirement: Law variant input layout

Each law variant SHALL live under `artefacts/<case>/` with `law.txt` as the single source text, plus generated `ontology.ttl`, `rules.lean`, and `manifest.yaml`. The TUI SHALL be built only against frozen (reviewed) artefact sets, never against drafts.

#### Scenario: New flavor scaffolded
- **WHEN** an author adds `artefacts/mayor-quorum/law.txt` with a quorum-validity plus 30-day-repeat clause
- **THEN** the harness generates draft artefacts under the same directory without touching the frozen mayor baseline or the TUI

### Requirement: Assisted generation with pinned prompt

The harness SHALL generate draft artefacts via a versioned prompt template pinned to the framework contract (GFO-light mapping, ECA shape, Nat-day arithmetic, mirror-by-name rule), so redrafts stay structurally comparable.

#### Scenario: Redraft diff is structural
- **WHEN** the mayor law text changes only the term length from 4 to 2 years
- **THEN** the regenerated draft diff shows changed time arithmetic and deadlines, not renamed classes or a reshaped state schema

### Requirement: Machine checks before human review

Drafts SHALL pass `lake build` (Lean, including Prop/Bool agreement theorems) and OWL parse plus consistency checks before reaching the human gate, with failures fed back as diagnostics.

#### Scenario: Broken draft blocked
- **WHEN** a draft `rules.lean` fails to build or the `.ttl` is inconsistent
- **THEN** the harness reports the diagnostics and marks the artefact set unreviewable until regenerated or fixed

### Requirement: Explicit review gate to frozen

No artefact set SHALL be consumable by the simulator until a human marks it reviewed, freezing the exact file versions. Post-freeze law edits SHALL require a new review.

#### Scenario: TUI refuses drafts
- **WHEN** the TUI is pointed at an artefact set that was edited after its review mark
- **THEN** it refuses to load and names the changed files
