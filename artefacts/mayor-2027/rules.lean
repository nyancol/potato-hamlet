-- Mayor election law: ontology mirror + ECA conditions + oracle interface.
-- Mirror-by-name with artefacts/mayor-2027/ontology.ttl (ph: short names).
-- Time: Nat days (day-of-cycle) + hour ints. Cycle 0 = January 2027.
-- Convention: every rule has a Bool (executable) + Prop (FOL) twin with an
-- agreement theorem, so `lake build` certifies what the oracle answers.
-- The oracle advises, never decides: `evaluate` reports phase, pending per
-- holder, failed conditions WITH witnesses, and would-win counts.
-- The Spirit of the Hamlet never appears as a holder.
--
-- Uniform oracle interface (framework-fixed; stable across redrafts/flavors):
--   Snapshot / VerdictData (+ JSON instances), `ecaIds`, `evaluate`,
--   `Act` (+ JSON instance), `apply` (enforcing transitions, `check` advisory).
-- The build script copies this file to RulesCase.lean in potato-hamlet-lean
-- and compiles the `oracle` exe against it (single source of truth).

import Lean.Data.Json

open Lean

/-! Graph layer: the knowledge graph IS the snapshot.
    `check` and `apply` take typed instance triples and Lean derives its state
    from them, so there is one representation of the world rather than a JSON
    state object plus a parallel graph. The wire format is the ABox only —
    schema triples never cross the boundary. -/

def rdfType : String := "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
def gfoCore : String := "https://w3id.org/gfo-core/"
def gfoLight : String := "https://w3id.org/gfo-light/"

/-- An object is either an IRI (bare JSON string) or a typed literal
    (`{"lit": ..., "type": ...}`). IRIs are always full: no prefix table is
    transmitted, so there is nothing to resolve. -/
inductive TripleObj where
  | iri (value : String)
  | lit (value : String) (datatype : String)
deriving Repr, DecidableEq

structure Triple where
  subject : String
  predicate : String
  object : TripleObj
deriving Repr, DecidableEq

abbrev Graph := List Triple

instance : FromJson TripleObj where
  fromJson? j := match j with
    | .str v => return TripleObj.iri v
    | .obj _ => do
      let v ← j.getObjVal? "lit" >>= FromJson.fromJson? (α := String)
      let dt ← j.getObjVal? "type" >>= FromJson.fromJson? (α := String)
      return TripleObj.lit v dt
    | _ => .error "object must be an IRI string or a literal object"

instance : ToJson TripleObj where
  toJson
    | .iri v => .str v
    | .lit v dt => Json.mkObj [("lit", .str v), ("type", .str dt)]

instance : FromJson Triple where
  fromJson? j := do
    let arr ← j.getArr?
    let t ← if arr.size = 3 then
      (do
        let s ← arr[0]!.getStr?
        let p ← arr[1]!.getStr?
        let o ← FromJson.fromJson? (α := TripleObj) arr[2]!
        pure { subject := s, predicate := p, object := o })
    else
      Except.error "triple must be a 3-element array"
    return t

instance : ToJson Triple where
  toJson t := Json.arr #[.str t.subject, .str t.predicate, toJson t.object]

structure GraphEnvelope where
  graph : Graph
deriving Repr, DecidableEq

instance : FromJson GraphEnvelope where
  fromJson? j := do
    let rows ← j.getObjVal? "graph" >>= FromJson.fromJson? (α := Graph)
    return { graph := rows }

instance : ToJson GraphEnvelope where
  toJson e := Json.mkObj [("graph", toJson e.graph)]

/-! Graph queries. Everything the law needs is reachable through these, so
    no consumer and no rule ever hardcodes a JSON field name. -/

namespace Graph

/-- Subjects carrying `predicate`, de-duplicated and in wire order. -/
def subjectsWith (g : Graph) (predicate : String) : List String :=
  (g.filter (fun t => t.predicate == predicate)).map (·.subject) |>.eraseDups

/-- Objects of `subject predicate ?`, de-duplicated. -/
def objectsOf (g : Graph) (subject predicate : String) : List TripleObj :=
  ((g.filter fun t => t.subject == subject && t.predicate == predicate).map
    (·.object)).eraseDups

def firstObjOf? (g : Graph) (subject predicate : String) : Option TripleObj :=
  (objectsOf g subject predicate).head?

/-- The IRI a subject's first object holds, if any. -/
def iriOf? (g : Graph) (subject predicate : String) : Option String :=
  match firstObjOf? g subject predicate with
  | some (.iri v) => some v
  | _ => none

/-- The lexical value of a subject's first object, if any. -/
def litOf? (g : Graph) (subject predicate : String) : Option String :=
  match firstObjOf? g subject predicate with
  | some (.lit v _) => some v
  | _ => none

/-- A Nat-valued property, defaulting to 0 when absent or unparsable. The
    clock is untrusted input (the driver writes it), so nothing here may
    fail on a malformed value — see the totality requirement. -/
def natOf (g : Graph) (subject predicate : String) : Nat :=
  match litOf? g subject predicate with
  | some v => (v.toNat?).getD 0
  | none => 0

/-- Subjects whose `rdf:type` is the given class IRI. -/
def typedOf (g : Graph) (classIri : String) : List String :=
  (g.filter fun t => t.predicate == rdfType && t.object == .iri classIri).map
    (·.subject)

/-- Replace every triple for `subject predicate ?`, keeping other triples. -/
def setOne (g : Graph) (subject predicate : String) (o : TripleObj) : Graph :=
  (g.filter fun t => !(t.subject == subject && t.predicate == predicate)) ++
    [{ subject := subject, predicate := predicate, object := o }]

end Graph

/-! Framework prelude: model types (stable across redrafts and flavors). -/

structure Citizen where
  id : String   -- full OWL individual IRI, e.g. ".../citizen/alice"
  age : Nat
deriving Repr, DecidableEq

structure Ballot where
  owner : String
  candidate : String
  delivered : Bool
deriving Repr, DecidableEq

structure Vote where
  voter : String
  candidate : String
deriving Repr, DecidableEq

/-- Closed-world snapshot: enumerates the full finite population.
    TTL ids = JSON ids = Lean ids. Act-flags track performed transitions;
    Python owns transitions, Lean only reads them. -/
structure Snapshot where
  day : Nat     -- day-of-cycle; election day = 10, announce = 0, prepare = 9
  hour : Nat
  citizens : List Citizen
  candidates : List String
  ballots : List Ballot
  registry : List String
  box : List Vote
  announced : Bool
  prepared : Bool
  counted : Bool
  proclaimed : Bool
  mayorId : Option String
deriving Repr, DecidableEq

/-- One duty owed by one citizen. `choices` names the options available at
    this instant for any parameter the manifest sources from `choices`, so a
    consumer can build a complete act without reading law-specific state. -/
structure PendingEntry where
  citizen : String
  eca : String
  choices : List (String × List String)
deriving Repr, DecidableEq

structure Violation where
  eca : String
  witnessCitizen : Option String
  witnessCandidate : Option String
  detail : String
deriving Repr, DecidableEq

structure VerdictData where
  fired : List String
  pending : List PendingEntry
  violations : List Violation
  wouldWin : Option String
  phase : String
deriving Repr, DecidableEq

/-! JSON instances (hand-written; core Lean has no deriving for these). -/

instance : FromJson Citizen where
  fromJson? j := do
    let id ← j.getObjVal? "id" >>= FromJson.fromJson? (α := String)
    let age ← j.getObjVal? "age" >>= FromJson.fromJson? (α := Nat)
    return { id, age }

instance : ToJson Citizen where
  toJson c := Json.mkObj [("id", toJson c.id), ("age", toJson c.age)]

instance : FromJson Ballot where
  fromJson? j := do
    let owner ← j.getObjVal? "owner" >>= FromJson.fromJson? (α := String)
    let candidate ← j.getObjVal? "candidate" >>= FromJson.fromJson? (α := String)
    let delivered ← j.getObjVal? "delivered" >>= FromJson.fromJson? (α := Bool)
    return { owner, candidate, delivered }

instance : ToJson Ballot where
  toJson b := Json.mkObj [("owner", toJson b.owner), ("candidate", toJson b.candidate),
    ("delivered", toJson b.delivered)]

instance : FromJson Vote where
  fromJson? j := do
    let voter ← j.getObjVal? "voter" >>= FromJson.fromJson? (α := String)
    let candidate ← j.getObjVal? "candidate" >>= FromJson.fromJson? (α := String)
    return { voter, candidate }

instance : ToJson Vote where
  toJson v := Json.mkObj [("voter", toJson v.voter), ("candidate", toJson v.candidate)]

private def getOptStr (j : Json) (k : String) : Except String (Option String) :=
  match j.getObjVal? k with
  | .error _ => .ok none
  | .ok Json.null => .ok none
  | .ok v => (Option.some ·) <$> FromJson.fromJson? (α := String) v

instance : FromJson Snapshot where
  fromJson? j := do
    let day ← j.getObjVal? "day" >>= FromJson.fromJson? (α := Nat)
    let hour ← j.getObjVal? "hour" >>= FromJson.fromJson? (α := Nat)
    let citizens ← j.getObjVal? "citizens" >>= FromJson.fromJson? (α := List Citizen)
    let candidates ← j.getObjVal? "candidates" >>= FromJson.fromJson? (α := List String)
    let ballots ← j.getObjVal? "ballots" >>= FromJson.fromJson? (α := List Ballot)
    let registry ← j.getObjVal? "registry" >>= FromJson.fromJson? (α := List String)
    let box ← j.getObjVal? "box" >>= FromJson.fromJson? (α := List Vote)
    let announced ← j.getObjVal? "announced" >>= FromJson.fromJson? (α := Bool)
    let prepared ← j.getObjVal? "prepared" >>= FromJson.fromJson? (α := Bool)
    let counted ← j.getObjVal? "counted" >>= FromJson.fromJson? (α := Bool)
    let proclaimed ← j.getObjVal? "proclaimed" >>= FromJson.fromJson? (α := Bool)
    let mayorId ← getOptStr j "mayorId"
    return Snapshot.mk day hour citizens candidates ballots registry box
      announced prepared counted proclaimed mayorId

instance : ToJson Snapshot where
  toJson s := Json.mkObj [
    ("day", toJson s.day), ("hour", toJson s.hour),
    ("citizens", toJson s.citizens), ("candidates", toJson s.candidates),
    ("ballots", toJson s.ballots), ("registry", toJson s.registry),
    ("box", toJson s.box), ("announced", toJson s.announced),
    ("prepared", toJson s.prepared), ("counted", toJson s.counted),
    ("proclaimed", toJson s.proclaimed),
    ("mayorId", match s.mayorId with | none => Json.null | some m => toJson m)]

instance : ToJson Violation where
  toJson v := Json.mkObj [
    ("eca", toJson v.eca),
    ("witnessCitizen", match v.witnessCitizen with | none => Json.null | some c => toJson c),
    ("witnessCandidate", match v.witnessCandidate with | none => Json.null | some c => toJson c),
    ("detail", toJson v.detail)]

/-- A pending entry as JSON: the ECA plus any parameter choices. -/
def pendingEntryJson (p : PendingEntry) : Json :=
  let base : List (String × Json) := [("eca", toJson p.eca)]
  let pairs : List (String × Json) :=
    p.choices.map (fun kv => (kv.1, Json.arr (kv.2.toArray.map (fun v => toJson v))))
  let choicesJson : Json := Json.mkObj pairs
  let withChoices : List (String × Json) :=
    if p.choices.isEmpty then base else base ++ [("choices", choicesJson)]
  Json.mkObj withChoices

instance : ToJson VerdictData where
  toJson v :=
    let grouped := v.pending.foldl (fun (m : List (String × List Json)) p =>
      match m.find? (fun kv => kv.1 == p.citizen) with
      | some _ => m.map (fun kv =>
        if kv.1 == p.citizen then (kv.1, kv.2 ++ [pendingEntryJson p]) else kv)
      | none => m ++ [(p.citizen, [pendingEntryJson p])]) []
    Json.mkObj [
      ("fired", toJson v.fired),
      ("pending", Json.mkObj (grouped.map (fun kv => (kv.1, Json.arr kv.2.toArray)))),
      ("violations", toJson v.violations),
      ("wouldWin", match v.wouldWin with | none => Json.null | some w => toJson w),
      ("phase", toJson v.phase)]

/-! Law-specific: named day arithmetic (announce = E-10, prepare = E-1). -/

def electionDay : Nat := 10
def announceDay : Nat := electionDay - 10
def prepareDay : Nat := electionDay - 1
def pollOpenHour : Nat := 9
def pollCloseHour : Nat := 19

/-! Ontology IRIs. Every lookup below names an IRI, never a JSON field, so
    no rule and no consumer hardcodes a wire key. -/

def ph (name : String) : String := "https://potato-hamlet.example/ontology/" ++ name
def iriHamlet : String := ph "hamlet"
def iriClock : String := ph "clock/now"
def iriElection : String := ph "election/mayor-2027-r0"
def iriRole (kind : String) : String := ph "role/" ++ kind

/-! Deriving typed state from the graph.
    A ballot or a cast vote names two citizens, so it cannot be a single data
    property: each side is a Role instance whose `roleIn` is the situation and
    whose `playedBy` is the citizen. One helper serves every such lookup, which
    is why `roleIn` matters — it gives the Role its context. -/

namespace Graph

/-- The citizen playing `roleClass` in the situation `ctx`, if any. -/
def participantVia? (g : Graph) (ctx roleClass : String) : Option String :=
  ((g.filter fun t => t.predicate == rdfType && t.object == .iri roleClass).filterMap
    fun t => if g.iriOf? t.subject (ph "roleIn") == some ctx
              then g.iriOf? t.subject (ph "playedBy") else none).head?

/-- Occurrences of a Process class that have `citizen` as a participant. -/
def occurrencesBy (g : Graph) (classIri citizen : String) : List String :=
  (g.filter fun t => t.predicate == rdfType && t.object == .iri classIri).filterMap
    fun t => if g.iriOf? t.subject (ph "hasParticipant") == some citizen
              then some t.subject else none

end Graph

/-! Snapshot derived from the graph. -/

/-- The citizen's age, or 0 when the graph does not record one. -/
def ageIn (g : Graph) (citizen : String) : Nat :=
  Graph.natOf g citizen (ph "age")

def citizensOf (g : Graph) : List Citizen :=
  (Graph.typedOf g (ph "Citizen")).map fun c => Citizen.mk c (ageIn g c)

/-- A ballot exists iff delivered; absence is what the witness reports. -/
def ballotsOf (g : Graph) : List Ballot :=
  (Graph.typedOf g (ph "BallotVote")).filterMap fun b =>
    match g.participantVia? b (ph "BallotOwnerRole"),
          g.participantVia? b (ph "CandidateRole") with
    | some owner, some cand => some (Ballot.mk owner cand true)
    | _, _ => none

def votesOf (g : Graph) : List Vote :=
  (Graph.typedOf g (ph "CastVote")).filterMap fun v =>
    match g.participantVia? v (ph "VoterRole"),
          g.participantVia? v (ph "CandidateRole") with
    | some voter, some cand => some (Vote.mk voter cand)
    | _, _ => none

/-- Candidacy: a Citizen playing `ph:CandidateRole` in the hamlet. -/
def candidatesOf (g : Graph) : List String :=
  ((g.filter fun t => t.predicate == rdfType && t.object == .iri (ph "CandidateRole")).filterMap
    fun t => if g.iriOf? t.subject (ph "roleIn") == some iriHamlet
              then g.iriOf? t.subject (ph "playedBy") else none)

/-- The registry: citizens with a nomination occurrence. -/
def registryOf (g : Graph) : List String :=
  (Graph.typedOf g (ph "Citizen")).filter fun c =>
    (Graph.occurrencesBy g (ph "SelfNomination") c).length > 0

/-- The mayor in office, if the office is filled. -/
def mayorIn (g : Graph) : Option String :=
  g.participantVia? iriHamlet (ph "MayorRole")

/-- A flag on the election instance. Absent means false. -/
def flagOn (g : Graph) (name : String) : Bool :=
  match g.litOf? iriElection (ph name) with
  | some "true" => true
  | _ => false

def snapshotOf (g : Graph) : Snapshot :=
  { day := g.natOf iriClock (ph "dayIndex")
    hour := g.natOf iriClock (ph "atHour")
    citizens := citizensOf g
    candidates := candidatesOf g
    ballots := ballotsOf g
    registry := registryOf g
    box := votesOf g
    announced := flagOn g "announced"
    prepared := flagOn g "prepared"
    counted := flagOn g "counted"
    proclaimed := flagOn g "proclaimed"
    mayorId := mayorIn g }

/-! Authority: current mayor if one holds office, else oldest citizen. -/

def oldest? : List Citizen → Option Citizen
  | [] => none
  | c :: cs => some (cs.foldl (fun best x => if x.age > best.age then x else best) c)

def authorityId : Snapshot → Option String
  | s => match s.mayorId with
    | some m => some m
    | none => (oldest? s.citizens).map (·.id)

def ageOf (s : Snapshot) (id : String) : Nat :=
  ((s.citizens.find? (fun c => c.id == id)).map (·.age)).getD 0

/-! ECA conditions: Bool/Prop twins. Arithmetic/window rules use
    `decide` over the Prop directly (genuine FOL, trivial agreement). -/

def announceDue? (s : Snapshot) : Bool :=
  decide (s.day = announceDay ∧ s.announced = false)
def AnnounceDue (s : Snapshot) : Prop :=
  s.day = announceDay ∧ s.announced = false
theorem announceDue_agrees (s : Snapshot) :
    announceDue? s = true ↔ AnnounceDue s := by
  simp [announceDue?, AnnounceDue]

def nominateOpen? (s : Snapshot) : Bool :=
  decide (announceDay ≤ s.day ∧ s.day < prepareDay)
def NominateOpen (s : Snapshot) : Prop :=
  announceDay ≤ s.day ∧ s.day < prepareDay
theorem nominateOpen_agrees (s : Snapshot) :
    nominateOpen? s = true ↔ NominateOpen s := by
  simp [nominateOpen?, NominateOpen]

def prepareDue? (s : Snapshot) : Bool :=
  decide (s.day = prepareDay ∧ s.prepared = false)
def PrepareDue (s : Snapshot) : Prop :=
  s.day = prepareDay ∧ s.prepared = false
theorem prepareDue_agrees (s : Snapshot) :
    prepareDue? s = true ↔ PrepareDue s := by
  simp [prepareDue?, PrepareDue]

def pollsOpen? (s : Snapshot) : Bool :=
  decide (s.day = electionDay ∧ pollOpenHour ≤ s.hour ∧ s.hour < pollCloseHour)
def PollsOpen (s : Snapshot) : Prop :=
  s.day = electionDay ∧ pollOpenHour ≤ s.hour ∧ s.hour < pollCloseHour
theorem pollsOpen_agrees (s : Snapshot) :
    pollsOpen? s = true ↔ PollsOpen s := by
  simp [pollsOpen?, PollsOpen]

def pollsClosed? (s : Snapshot) : Bool :=
  decide (s.day > electionDay ∨ (s.day = electionDay ∧ pollCloseHour ≤ s.hour))
def PollsClosed (s : Snapshot) : Prop :=
  s.day > electionDay ∨ (s.day = electionDay ∧ pollCloseHour ≤ s.hour)
theorem pollsClosed_agrees (s : Snapshot) :
    pollsClosed? s = true ↔ PollsClosed s := by
  simp [pollsClosed?, PollsClosed]

def countDue? (s : Snapshot) : Bool :=
  decide ((s.day > electionDay ∨ (s.day = electionDay ∧ pollCloseHour ≤ s.hour)) ∧
    s.counted = false)
def CountDue (s : Snapshot) : Prop :=
  (s.day > electionDay ∨ (s.day = electionDay ∧ pollCloseHour ≤ s.hour)) ∧
    s.counted = false
theorem countDue_agrees (s : Snapshot) :
    countDue? s = true ↔ CountDue s := by
  simp [countDue?, CountDue]

def proclaimDue? (s : Snapshot) : Bool :=
  decide (s.counted = true ∧ s.proclaimed = false)
def ProclaimDue (s : Snapshot) : Prop :=
  s.counted = true ∧ s.proclaimed = false
theorem proclaimDue_agrees (s : Snapshot) :
    proclaimDue? s = true ↔ ProclaimDue s := by
  simp [proclaimDue?, ProclaimDue]

/-! Distribution completeness: finite universal over citizens × candidates.
    The flagship FOL rule — OWL cannot express "for every ... exists ...". -/

def ballotOk (b : Ballot) (owner cand : String) : Bool :=
  b.owner == owner && b.candidate == cand && b.delivered

def BallotOk (b : Ballot) (owner cand : String) : Prop :=
  b.owner = owner ∧ b.candidate = cand ∧ b.delivered = true

theorem ballotOk_true (b : Ballot) (owner cand : String) :
    ballotOk b owner cand = true ↔ BallotOk b owner cand := by
  unfold ballotOk BallotOk
  simp only [Bool.and_eq_true, beq_iff_eq]
  constructor
  · intro h; obtain ⟨⟨h1, h2⟩, h3⟩ := h; exact ⟨h1, h2, h3⟩
  · intro h; obtain ⟨h1, h2, h3⟩ := h; exact ⟨⟨h1, h2⟩, h3⟩

def allDistributed? (s : Snapshot) : Bool :=
  s.citizens.all (fun c =>
    s.candidates.all (fun cand => s.ballots.any (ballotOk · c.id cand)))

def AllDistributed (s : Snapshot) : Prop :=
  ∀ c ∈ s.citizens, ∀ cand ∈ s.candidates,
    ∃ b ∈ s.ballots, BallotOk b c.id cand

theorem allDistributed_agrees (s : Snapshot) :
    allDistributed? s = true ↔ AllDistributed s := by
  simp [allDistributed?, AllDistributed, List.all_eq_true, List.any_eq_true,
    ballotOk_true]

/-- First missing (citizen, candidate) pair: the witness for the guide. -/
def missingFor (s : Snapshot) (c : Citizen) : Option String :=
  s.candidates.find?
    (fun cand => !(s.ballots.any (ballotOk · c.id cand)))

def firstMissing? (s : Snapshot) : Option (String × String) :=
  match s.citizens.find? (fun c => (missingFor s c).isSome) with
  | none => none
  | some c => match missingFor s c with
    | none => none
    | some cand => some (c.id, cand)

/-! Votes, winner with oldest-on-tie (advisory: proclamation stays human). -/

def voteCount (s : Snapshot) (cand : String) : Nat :=
  (s.box.filter (fun v => v.candidate == cand)).length

def voted? (s : Snapshot) (voter : String) : Bool :=
  s.box.any (fun v => v.voter == voter)

def maxCount (s : Snapshot) : Nat :=
  s.candidates.foldl (fun m c => Nat.max m (voteCount s c)) 0

def winners (s : Snapshot) : List String :=
  s.candidates.filter (fun c => voteCount s c == maxCount s)

def oldestId : Snapshot → List String → Option String
  | _, [] => none
  | s, i :: is => some
    (is.foldl (fun best x => if ageOf s x > ageOf s best then x else best) i)

def winner? (s : Snapshot) : Option String :=
  oldestId s (winners s)

/-- Winner agreement is stated as Bool-equality (rfl): a full argmax-plus-oldest
    correctness proof (winner ∈ candidates, maximal count, oldest on ties) is
    deferred. The counting/oldest building blocks above are the checkable part. -/
def IsWinner (s : Snapshot) (w : String) : Prop :=
  winner? s = some w
theorem winner_agrees (s : Snapshot) (w : String) :
    (winner? s = some w) ↔ IsWinner s w := by
  rfl

/-! Double-vote detection. -/

def doubleVoters (s : Snapshot) : List String :=
  (s.box.map (·.voter)).eraseDups.filter
    (fun v => decide (2 ≤ (s.box.filter (fun b => b.voter == v)).length))

/-! Uniform oracle interface. -/

def ecaIds : List String :=
  ["announce", "nominate", "prepare", "vote", "count", "proclaim"]

def firedOf (s : Snapshot) : List String :=
  (if s.day == announceDay then ["announce"] else []) ++
  (if nominateOpen? s then ["nominate"] else []) ++
  (if s.day == prepareDay then ["prepare"] else []) ++
  (if s.day == electionDay then ["vote"] else []) ++
  (if pollsClosed? s then ["count"] else []) ++
  (if s.counted then ["proclaim"] else [])

def pendingOf (s : Snapshot) : List PendingEntry :=
  let authPending : List PendingEntry := match authorityId s with
    | none => []
    | some a =>
      (if announceDue? s then [{ citizen := a, eca := "announce", choices := [] }] else []) ++
      (if prepareDue? s then [{ citizen := a, eca := "prepare", choices := [] }] else []) ++
      (if countDue? s then [{ citizen := a, eca := "count", choices := [] }] else []) ++
      (if proclaimDue? s then [{ citizen := a, eca := "proclaim", choices := [] }] else [])
  let nominees : List PendingEntry :=
    if nominateOpen? s then
      (s.citizens.filter (fun c => !(s.registry.any (· == c.id)))).map
        (fun c => { citizen := c.id, eca := "nominate", choices := [] })
    else []
  let voters : List PendingEntry :=
    if pollsOpen? s then
      (s.citizens.filter (fun c => decide (!(voted? s c.id)))).map
        (fun c => { citizen := c.id, eca := "vote",
                       choices := [("candidate", s.candidates)] })
    else []
  authPending ++ nominees ++ voters

def violationsOf (s : Snapshot) : List Violation :=
  let dist : List Violation := match firstMissing? s with
    | none => []
    | some (c, cand) =>
      if decide (prepareDay ≤ s.day) then
        [{ eca := "all_distributed", witnessCitizen := some c,
           witnessCandidate := some cand, detail := "ballot missing" }]
      else []
  let dupes : List Violation := (doubleVoters s).map (fun v =>
    { eca := "single_vote", witnessCitizen := some v, witnessCandidate := none,
      detail := "citizen voted twice" })
  dist ++ dupes

def phaseOf (s : Snapshot) : String :=
  if s.proclaimed then "ResultsPosted"
  else if s.counted then "PollsClosed"
  else if pollsOpen? s then "PollsOpen"
  else if pollsClosed? s then "PollsClosed"
  else if s.prepared then "BallotsReady"
  else "RegistryOpen"

def evaluate (s : Snapshot) : VerdictData :=
  { fired := firedOf s, pending := pendingOf s, violations := violationsOf s,
    wouldWin := winner? s, phase := phaseOf s }

/-! Actions as data + enforcing transitions (`apply` enforces, `check` advises).
    Each transition reuses the same `?` guards as `check`, so precondition
    truth has one source. Rejection strings double as guide messages. -/

inductive Act
  | announce
  | nominate (citizen : String)
  | prepare
  | vote (voter candidate : String)
  | count
  | proclaim
deriving Repr, DecidableEq

instance : FromJson Act where
  fromJson? j := do
    let eca ← j.getObjVal? "eca" >>= FromJson.fromJson? (α := String)
    match eca with
    | "announce" => pure .announce
    | "nominate" =>
      Act.nominate <$> (j.getObjVal? "citizen" >>= FromJson.fromJson? (α := String))
    | "prepare" => pure .prepare
    | "vote" =>
      Act.vote <$> (j.getObjVal? "voter" >>= FromJson.fromJson? (α := String))
               <*> (j.getObjVal? "candidate" >>= FromJson.fromJson? (α := String))
    | "count" => pure .count
    | "proclaim" => pure .proclaim
    | other => .error s!"unknown eca: {other}"

def applyAnnounce (s : Snapshot) : Except String Snapshot :=
  match authorityId s with
  | none => .error "no authority in office"
  | some _ =>
    if announceDue? s then .ok { s with announced := true }
    else .error "announce not due"

def applyNominate (s : Snapshot) (c : String) : Except String Snapshot :=
  if !nominateOpen? s then .error "registry closed"
  else if s.registry.any (· == c) then .error "already registered"
  else .ok { s with registry := c :: s.registry }

def fullBallots (citizens : List Citizen) (cands : List String) : List Ballot :=
  citizens.flatMap (fun c => cands.map (fun cand => Ballot.mk c.id cand true))

def applyPrepare (s : Snapshot) : Except String Snapshot :=
  match authorityId s with
  | none => .error "no authority in office"
  | some _ =>
    if prepareDue? s then
      .ok { s with prepared := true,
                   ballots := fullBallots s.citizens s.candidates }
    else .error "prepare not due"

def applyVote (s : Snapshot) (v c : String) : Except String Snapshot :=
  if !pollsOpen? s then .error "polls closed"
  else if voted? s v then .error "citizen already voted"
  else .ok { s with box := Vote.mk v c :: s.box }

def applyCount (s : Snapshot) : Except String Snapshot :=
  if countDue? s then .ok { s with counted := true }
  else .error "count not due"

def applyProclaim (s : Snapshot) : Except String Snapshot :=
  match winner? s with
  | none => .error "no candidates"
  | some w =>
    if proclaimDue? s then .ok { s with proclaimed := true, mayorId := some w }
    else .error "proclaim not due"

def apply : Act → Snapshot → Except String Snapshot
  | .announce, s => applyAnnounce s
  | .nominate c, s => applyNominate s c
  | .prepare, s => applyPrepare s
  | .vote v c, s => applyVote s v c
  | .count, s => applyCount s
  | .proclaim, s => applyProclaim s

/-! Writing a snapshot back into the graph.
    `apply` returns the WHOLE graph and the consumer replaces its stored copy
    wholesale, so the oracle's state and the graph can never diverge. Nothing
    is ever removed: a cast vote or a delivered ballot persists for the rest
    of the simulation, and a later rule may only change how it is counted. -/

/-- A stable short name for an entity, from the last path segment of its IRI.
    Minted IRIs must be deterministic from the act's parameters so a replayed
    act addresses the same individual. -/
def shortId (iri : String) : String :=
  match (iri.splitOn "/").getLast? with
  | some s => s
  | none => iri

def iriBallot (owner cand : String) : String :=
  ph "ballot/" ++ shortId owner ++ "-" ++ shortId cand
def iriNomination (citizen : String) : String :=
  ph "nomination/" ++ shortId citizen
def iriVote (voter cand : String) : String :=
  ph "vote/" ++ shortId voter ++ "-" ++ shortId cand

/-- Role instance triples: type + roleIn (context) + playedBy (the citizen). -/
def roleTriples' (roleClass ctx citizen : String) : List Triple :=
  [ { subject := ctx ++ "#" ++ roleClass
    , predicate := rdfType, object := .iri roleClass }
  , { subject := ctx ++ "#" ++ roleClass
    , predicate := ph "roleIn", object := .iri ctx }
  , { subject := ctx ++ "#" ++ roleClass
    , predicate := ph "playedBy", object := .iri citizen } ]

def boolLit (b : Bool) : TripleObj := TripleObj.lit (if b then "true" else "false") "boolean"

/-- Overlay a derived snapshot onto the graph: clock, election flags, office,
    and every occurrence. Existing triples for these subjects are replaced;
    occurrences already present are left alone, so applying twice cannot
    duplicate or delete an individual. -/
def writeBack (g : Graph) (s : Snapshot) : Graph :=
  let base :=
    g.setOne iriClock (ph "dayIndex") (.lit (toString s.day) "integer")
     |>.setOne iriClock (ph "atHour") (.lit (toString s.hour) "integer")
     |>.setOne iriElection (ph "announced") (boolLit s.announced)
     |>.setOne iriElection (ph "prepared") (boolLit s.prepared)
     |>.setOne iriElection (ph "counted") (boolLit s.counted)
     |>.setOne iriElection (ph "proclaimed") (boolLit s.proclaimed)
  -- office: the MayorRole individual is ADDITIVE. No act clears the office in
  -- this law, so an unfilled office simply means the role instance is not
  -- there yet. Filtering here would delete unrelated role triples, which is
  -- exactly the erasure the contract forbids.
  let mayorRole := iriRole "mayor" ++ "#MayorRole"
  let withOffice :=
    match s.mayorId with
    | none => base
    | some m =>
      base ++ (roleTriples' (ph "MayorRole") iriHamlet m).map fun t =>
        { t with subject := mayorRole }
  -- candidacy, nominations, ballots, votes: additive only
  let candidacy := s.candidates.filterMap fun c =>
    match g.participantVia? iriHamlet (ph "CandidateRole") with
    | some existing => if existing == c then none else some c
    | none => some c
  let withCandidacy := withOffice ++
    (candidacy.flatMap fun c =>
      (roleTriples' (ph "CandidateRole") iriHamlet c).map fun t =>
        { t with subject := iriRole "candidate" ++ "/" ++ shortId c })
  let nominations := s.registry.filterMap fun c =>
    match g.iriOf? (iriNomination c) rdfType with
    | some _ => none
    | none => some c
  let withNominations := withCandidacy ++ (nominations.flatMap fun c =>
    [ { subject := iriNomination c, predicate := rdfType, object := .iri (ph "SelfNomination") }
    , { subject := iriNomination c, predicate := ph "hasParticipant", object := .iri c } ] ++
    -- Adding your name IS becoming a candidate: the citizen thereby plays
    -- ph:CandidateRole in the hamlet, which is what the ballot and vote
    -- rules enumerate.
    (roleTriples' (ph "CandidateRole") iriHamlet c).map fun t =>
      { t with subject := iriRole "candidate" ++ "/" ++ shortId c })
  let ballots := s.ballots.filterMap fun b =>
    match g.iriOf? (iriBallot b.owner b.candidate) rdfType with
    | some _ => none
    | none => some b
  let withBallots := withNominations ++ (ballots.flatMap fun b =>
    [ { subject := iriBallot b.owner b.candidate, predicate := rdfType
      , object := .iri (ph "BallotVote") } ] ++
    (roleTriples' (ph "BallotOwnerRole") (iriBallot b.owner b.candidate) b.owner) ++
    (roleTriples' (ph "CandidateRole") (iriBallot b.owner b.candidate) b.candidate))
  let votes := s.box.filterMap fun v =>
    match g.iriOf? (iriVote v.voter v.candidate) rdfType with
    | some _ => none
    | none => some v
  withBallots ++ (votes.flatMap fun v =>
    [ { subject := iriVote v.voter v.candidate, predicate := rdfType
      , object := .iri (ph "CastVote") } ] ++
    (roleTriples' (ph "VoterRole") (iriVote v.voter v.candidate) v.voter) ++
    (roleTriples' (ph "CandidateRole") (iriVote v.voter v.candidate) v.candidate))

/-- `apply` over the graph: derive, transition, write the whole graph back. -/
def applyGraph (act : Act) (g : Graph) : Except String Graph :=
  match apply act (snapshotOf g) with
  | .error reason => .error reason
  | .ok s' => .ok (writeBack g s')
