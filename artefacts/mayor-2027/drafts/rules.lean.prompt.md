# Step 1 prompt — Lean rules draft (v1)

You are drafting the Lean 4 oracle rules for the Potato Hamlet
law-to-simulation framework. You receive the law text plus the reviewed
`ontology.ttl`. Output ONE Lean file to stdout and nothing else.

## Fixed contract (do not invent alternatives)

- Lean 4 (toolchain `leanprover/lean4:v4.34.1`), no extra dependencies
  beyond the project lakefile. Use `Lean.Data.Json` for I/O (added in
  task 3.1; for the draft, plain structures suffice).
- Time: `Nat` days (day-of-cycle) + hour `Nat`. Name the arithmetic:
  `electionDay`, `announceDay = electionDay - 10`,
  `prepareDay = electionDay - 1`, `pollOpenHour = 9`,
  `pollCloseHour = 19`. Cycle 0 = January 2027; recurrence is a Nat
  function of the cycle index (e.g. +1461 days per 4-year cycle).
- `Snapshot` holds day, hour, citizens (`id : String` = full OWL
  individual IRI, `age : Nat`), candidates, ballots
  (`owner`, `candidate`, `delivered : Bool`), registry state, box contents.
- Mirror-by-name: every type name MUST equal the `ontology.ttl` class
  short name (`Citizen`, `MayorRole`, `CastVote`, ...).
- ECA encoding per rule: an `Event` (`tick` or `act`), a condition as a
  **Bool/Prop twin with an agreement theorem**:
  `def <name>? : Snapshot -> Bool`, `def <Name> : Snapshot -> Prop`,
  `theorem <name>_agrees : <name>? s = true ↔ <Name> s`, plus
  `def holder : String -> Snapshot -> String` mapping ECA id to the
  citizen id that must act. Cover at minimum: announce, nominate window,
  all-distributed, polls-open, winner with oldest-on-tie, fallback
  oldest-authority (holder = mayor if one holds office else oldest
  citizen), quorum when the law text has one.
- FOL subset only: universal/existential quantification over finite
  lists, counting, Nat comparisons and arithmetic. Everything decidable.
- Each ECA carries a modality (`should` / `must` / `may`) preserved from
  the source text ("should communicate" vs "must create"); keep them
  distinct, never flatten to plain obligations.
- The oracle advises, never decides: report phase, pending per holder,
  failed conditions WITH witnesses (e.g. `{missingCitizen,
  missingCandidate}`), would-win counts. No transition application, no
  auto-proclaim. The Spirit of the Hamlet never appears as a holder.
- Oracle CLI (task 3.3): `list` names ECA ids; `check` takes a snapshot
  JSON and returns conditions truth values, per-citizen pending, and
  violations with witnesses. Draft the pure functions; IO wiring lands
  with task 3.1/3.3.

## Stability rule (redrafts must diff structurally)

Keep ECA ids, type names, and Snapshot fields stable. A text change that
only alters a number MUST change only arithmetic/constants, never rename
ECAs or reshape Snapshot.

## Output

Raw Lean 4 only. No markdown fences, no explanations.
Ontology follows after `---ONTOLOGY---`, law text after `---LAW---`.

---ONTOLOGY---
@prefix ph: <https://potato-hamlet.example/ontology/> .
@prefix gfo-core: <https://w3id.org/gfo-core/> .
@prefix gfo-light: <https://w3id.org/gfo-light/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# Skeleton — full class/individual coverage lands via the Step 1 draft loop.
# Every ph: class subclasses a GFO-light/GFO-core category (mirror-by-name
# with Lean types in rules.lean). Every simulatable individual has rdfs:label.

ph:Citizen rdfs:subClassOf gfo-light:Object .
ph:Hamlet rdfs:subClassOf gfo-light:ObjectAggregate .
ph:Townhall rdfs:subClassOf gfo-light:Object .
ph:BallotBox rdfs:subClassOf gfo-light:Object .
ph:Mailbox rdfs:subClassOf gfo-light:Object .
ph:ResultsBoard rdfs:subClassOf gfo-light:Object .
ph:CandidateRegistry rdfs:subClassOf gfo-light:InformationObject .
ph:BallotVote rdfs:subClassOf gfo-light:InformationObject .
ph:VoteResult rdfs:subClassOf gfo-light:InformationObject .
ph:MayorRole rdfs:subClassOf gfo-light:Role .
ph:CandidateRole rdfs:subClassOf gfo-light:Role .
ph:VoterRole rdfs:subClassOf gfo-light:Role .
ph:FallbackAuthorityRole rdfs:subClassOf gfo-light:Role .
ph:CitizenAge rdfs:subClassOf gfo-light:Quality .
ph:AnnounceElection rdfs:subClassOf gfo-core:Process .
ph:SelfNomination rdfs:subClassOf gfo-core:Process .
ph:CreateBallots rdfs:subClassOf gfo-core:Process .
ph:DistributeBallots rdfs:subClassOf gfo-core:Process .
ph:CastVote rdfs:subClassOf gfo-core:Process .
ph:CountVotes rdfs:subClassOf gfo-core:Process .
ph:ProclaimMayor rdfs:subClassOf gfo-core:Process .
ph:MayorElectionCycle rdfs:subClassOf gfo-core:Process .
ph:RegistryOpen rdfs:subClassOf gfo-core:State .
ph:BallotsReady rdfs:subClassOf gfo-core:State .
ph:PollsOpen rdfs:subClassOf gfo-core:State .
ph:PollsClosed rdfs:subClassOf gfo-core:State .
ph:ResultsPosted rdfs:subClassOf gfo-core:State .

ph:age a owl:DatatypeProperty ;
  rdfs:domain ph:Citizen ;
  rdfs:range xsd:integer .

# Sample individuals so loader/label checks have data before drafts land.
# NOTE: full IRIs in angle brackets because "/" is not valid in a
# Turtle prefixed name; "ph:citizen/alice" is the prefixed reading of
# <https://potato-hamlet.example/ontology/citizen/alice>.
ph:hamlet a ph:Hamlet ;
  rdfs:label "Potato Hamlet" .

<https://potato-hamlet.example/ontology/citizen/alice> a ph:Citizen ;
  rdfs:label "Alice" ;
  ph:age 71 .

<https://potato-hamlet.example/ontology/citizen/bob> a ph:Citizen ;
  rdfs:label "Bob" ;
  ph:age 54 .

<https://potato-hamlet.example/ontology/citizen/cara> a ph:Citizen ;
  rdfs:label "Cara" ;
  ph:age 43 .

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
