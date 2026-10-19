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

---LAW---
Our agreement on how we choose our mayor — decided together, autumn 2026

We, the people of Potato Hamlet, have talked a lot around the fire about how to choose a mayor fairly, and this is what we agreed.

We will hold mayor elections every 4 years, always on the 12th of January. The first one will be on the 12th of January 2027, then 2031, and so on.

On the 2nd of January, so 10 days before the election, the current mayor is expected to let everyone know the election is coming. If we don't have a mayor yet, then
the oldest person in the hamlet does it instead. They should put a note in the townhall and tell people that anyone who wants to be mayor should come and write their
name in the candidate registry book that stays in the townhall.

Then people have until the 11th to add their names. On the 11th of January, the mayor — or the oldest person if there is no mayor yet — must make the ballot votes.
That means one paper per candidate for each citizen, so everyone can choose. They must put these papers in the mailbox of each citizen, and they must also put a big
closed box, the ballot box, in the townhall where everyone can see it.

On the 12th of January, starting from 9am, each citizen should come to the townhall in person and put their vote, just one, into the box. At 7pm it is over, no more
votes after that.

At 7pm the mayor, or the oldest person, must open the box, count all the votes in front of anyone who wants to watch, write the results clearly on the big board in
the townhall, and name the new mayor. It is the one who got the most votes. If two or more have the same number and are tied, then the oldest candidate among them
becomes mayor.

This is what we want the Spirit of the Hamlet to remind us of, so nobody forgets a step.

Signed, the inhabitants.
