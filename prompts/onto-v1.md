# Step 1 prompt — ontology draft (v1)

You are drafting a GFO-light domain ontology for the Potato Hamlet
law-to-simulation framework. Read the law text given after this template,
then output ONE Turtle file to stdout and nothing else.

## Fixed contract (do not invent alternatives)

- Base IRI: `https://potato-hamlet.example/ontology/` with prefix `ph:`.
- Import pinned GFO-light: `https://w3id.org/gfo-light/release/2025-10-01`
  (which extends GFO-core). Also declare `gfo-core:`, `rdfs:`, `owl:`, `xsd:`.
- Every domain class MUST subclass a GFO-light/GFO-core category:
  `Continuant` subclasses via `gfo-light:Object` (independent things:
  Citizen, Townhall, BallotBox, Mailbox, ResultsBoard),
  `gfo-light:ObjectAggregate` (Hamlet, Electorate),
  `gfo-light:InformationObject` (CandidateRegistry, BallotVote, VoteResult,
  the law text itself), `gfo-light:Role` (MayorRole, CandidateRole,
  VoterRole, FallbackAuthorityRole — model BOTH `roleIn` and `playedBy`),
  `gfo-light:Quality` (age and other measurable qualities, reified when
  history matters), `gfo-core:Process` (dynamic phases: announce, nominate,
  create/distribute ballots, cast vote, count, proclaim), `gfo-core:State`
  (static snapshots: RegistryOpen, BallotsReady, PollsOpen, PollsClosed,
  ResultsPosted).
- NEVER use GFO-full categories (Presential, Persistant, Situoid, ...).
- Mirror-by-name: class short names MUST be valid Lean identifiers, because
  `rules.lean` will declare a same-named type per class
  (e.g. `ph:Citizen` <-> `Citizen`).
- Individuals use FULL IRIs in angle brackets (a "/" is not valid in a
  Turtle prefixed name): `<.../citizen/alice> a ph:Citizen ; ...`.
  Snapshot ids in JSON equal these full IRIs.
- Every simulatable individual MUST have `rdfs:label`.
- The Spirit of the Hamlet is an observer only: NEVER a Role holder,
  NEVER a `hasParticipant` of any law Process.
- Preserve deontic modality from the text as comments on the relevant
  Process (`should` vs `must` vs `may`); the Lean side encodes them as ECA
  modalities.

## Stability rule (redrafts must diff structurally)

Keep class and property names stable across redrafts. A text change that
only alters a number (e.g. term length 4 -> 2 years) MUST change only
values/comments, never rename classes or reshape the schema.

## Output

Raw Turtle only. No markdown fences, no explanations.
The law text follows after the `---LAW---` marker.
