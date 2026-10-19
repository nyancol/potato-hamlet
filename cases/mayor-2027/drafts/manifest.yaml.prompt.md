# Step 1 prompt — manifest draft (v1)

You are drafting the `manifest.yaml` for a Potato Hamlet law artefact set.
You receive the reviewed `ontology.ttl` and `rules.lean`. Output ONE YAML
file to stdout and nothing else.

## Fixed contract

- Fields: `case` (directory name), `freeze: null` (never invent a hash;
  the review gate sets it), `ontology` (ttl filename), `oracle: null`
  (binary path lands with oracle build, task 3.3), `time` (cycle_days,
  announce_minus, prepare_minus, polls_open, polls_close), `ecas` (list
  of `id`, `eca_process` = GFO Process class short name, `label`,
  `message` with `{holder}`/`{citizen}` placeholders, `modality` =
  should|must|may preserved from the source text).
- ECA `id`s MUST equal the Lean ECA ids exactly; the review gate refuses
  mismatches against oracle `list`. Labels/messages are display-only.
- No rule truth here: conditions, holders, winners live in Lean.

## Output

Raw YAML only. No markdown fences, no explanations.
Ontology follows after `---ONTOLOGY---`, Lean after `---LEAN---`.

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

---LEAN---
-- Skeleton — executable ECA conditions land via the Step 1 draft loop.
-- Mirror-by-name with artefacts/mayor-2027/ontology.ttl (ph: short names).
-- Time: Nat days (day-of-cycle) + hour ints. Cycle 0 = January 2027.
-- Convention: every rule has a Bool (executable) + Prop (FOL) twin with an
-- agreement theorem, so `lake build` certifies what the oracle answers.

structure Citizen where
  id : String   -- OWL individual IRI, e.g. "ph:citizen/alice"
  age : Nat
deriving Repr, DecidableEq

structure Ballot where
  owner : String
  candidate : String
  delivered : Bool
deriving Repr, DecidableEq

structure Snapshot where
  day : Nat     -- day-of-cycle; election day = 10, announce = 0, prepare = 9
  hour : Nat
  citizens : List Citizen
  candidates : List String
  ballots : List Ballot
deriving Repr

-- Named day arithmetic: announce = E-10, prepare = E-1, polls 9-19 on E-day.
def electionDay : Nat := 10
def announceDay : Nat := electionDay - 10
def prepareDay : Nat := electionDay - 1
def pollOpenHour : Nat := 9
def pollCloseHour : Nat := 19

-- Placeholder ECA conditions; real twins arrive with the draft loop.
def allDistributed? : Snapshot -> Bool
  | _ => false

def AllDistributed (s : Snapshot) : Prop :=
  allDistributed? s = true

theorem allDistributed_agrees (s : Snapshot) :
    allDistributed? s = true ↔ AllDistributed s := by
  rfl
