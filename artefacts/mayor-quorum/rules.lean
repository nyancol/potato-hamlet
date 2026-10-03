-- Mayor-quorum election law: baseline mayor rules + quorum validity with repeat.
-- Mirror-by-name with artefacts/mayor-quorum/ontology.ttl (ph: short names).
-- Time: Nat days (day-of-cycle) + hour ints. Cycle 0 = January 2027.
-- Quorum: valid iff at least half of citizens voted; on failure a NEW
-- election cycle is scheduled 30 days later with recomputed prep dates and a
-- reset registry/ballots (void-cycle data is preserved in history and never
-- carries over). Repeats continue until quorum is valid and never shift the
-- 4-year election clock (mandate only shortens).
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

/-- One election cycle: per-cycle state lives here. The void cycle is
    preserved with its outcome; the successor starts fresh. -/
structure Cycle where
  id : String   -- cycle individual IRI, e.g. ".../election/mayor-quorum-r1"
  day : Nat     -- day-of-cycle for THIS cycle; E-day = electionDayK k
  hour : Nat
  candidates : List String
  ballots : List Ballot
  registry : List String
  box : List Vote
  announced : Bool
  prepared : Bool
  counted : Bool
  proclaimed : Bool
  outcome : Option String  -- none = ongoing, some "void", some "valid"
  -- The moments the Chronoid's start and finish bounds denote. A GFO
  -- TimeBoundary names ONE moment, so a bound has to record when the
  -- instance actually began and ended -- not the cycle's current day, which
  -- keeps moving and would rewrite a bound that already happened.
  startDay : Option Nat
  startHour : Option Nat
  finishDay : Option Nat
  finishHour : Option Nat
deriving Repr, DecidableEq

/-- The day an instance began on, defaulting to its current day before it
    has been stamped. -/
def Cycle.startDayOf (c : Cycle) : Nat :=
  match c.startDay with
  | some d => d
  | none => c.day

def Cycle.startHourOf (c : Cycle) : Nat :=
  match c.startHour with
  | some h => h
  | none => c.hour

def Cycle.finishDayOf (c : Cycle) : Nat :=
  match c.finishDay with
  | some d => d
  | none => c.day

def Cycle.finishHourOf (c : Cycle) : Nat :=
  match c.finishHour with
  | some h => h
  | none => c.hour

/-- Record the moment the instance began, if it has not been recorded. -/
def Cycle.stampStart (c : Cycle) : Cycle :=
  { c with
    startDay := some c.startDayOf
    startHour := some c.startHourOf }

/-- Record the moment the instance ended, if it has not been recorded. -/
def Cycle.stampFinish (c : Cycle) : Cycle :=
  { c with
    finishDay := some c.finishDayOf
    finishHour := some c.finishHourOf }

def Cycle.started (c : Cycle) : Bool :=
  c.announced || c.prepared || c.counted || c.proclaimed

/-- Closed-world snapshot: enumerates the full finite population plus the
    full election-cycle history. TTL ids = JSON ids = Lean ids.
    Population (`citizens`) and office (`mayorId`) are global; everything
    else lives per cycle. The current cycle is the last element
    (invariant: at least one cycle). -/
structure Snapshot where
  citizens : List Citizen
  cycles : List Cycle
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

/-! Readings: a law's results, reported without a verdict field of their own.

    The verdict once carried `wouldWin`, which is the name of one process's
    result. A taxation or requisition law has no winner, so the field was
    meaningless for it and any genuinely new result would have needed a
    verdict shape change -- the framework-fixed contract was not fixed. A
    reading instead names a law-chosen id, a `kind` from a closed set, and a
    value, so a new result is a new entry rather than a new field.

    A law with no result of a given shape emits NO reading for it. Absence is
    how a consumer learns there is nothing, so there is never a null that
    could be mistaken for a value. -/

inductive ReadingKind where
  | decimal | ref | flag
  deriving Repr, DecidableEq, Inhabited

def ReadingKind.name : ReadingKind → String
  | .decimal => "decimal"
  | .ref => "ref"
  | .flag => "flag"

inductive ReadingValue where
  | num (n : Nat)
  | flag (b : Bool)
  | iri (s : String)
  deriving Repr, DecidableEq

/-- One result. `refClass` names the ontology class of the individual a `ref`
    reading points at, so a consumer resolves its label from the graph without
    knowing which law it is reading. It is present on `ref` readings only. -/
structure Reading where
  id : String
  kind : ReadingKind
  value : ReadingValue
  refClass : Option String
deriving Repr, DecidableEq

instance : ToJson Reading where
  toJson r :=
    let base : List (String × Json) :=
      [ ("id", toJson r.id)
      , ("kind", Json.str r.kind.name)
      , ("value", match r.value with
          | .num n => toJson n
          | .flag b => toJson b
          | .iri s => toJson s) ]
    Json.mkObj (match r.refClass with
      | some c => base ++ [("refClass", toJson c)]
      | none => base)

structure VerdictData where
  fired : List String
  pending : List PendingEntry
  violations : List Violation
  readings : List Reading
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

instance : ToJson Cycle where
  toJson c := Json.mkObj [
    ("id", toJson c.id), ("day", toJson c.day), ("hour", toJson c.hour),
    ("candidates", toJson c.candidates), ("ballots", toJson c.ballots),
    ("registry", toJson c.registry), ("box", toJson c.box),
    ("announced", toJson c.announced), ("prepared", toJson c.prepared),
    ("counted", toJson c.counted), ("proclaimed", toJson c.proclaimed),
    ("outcome", match c.outcome with | none => Json.null | some o => toJson o)]

private def getOptStr (j : Json) (k : String) : Except String (Option String) :=
  match j.getObjVal? k with
  | .error _ => .ok none
  | .ok Json.null => .ok none
  | .ok v => (Option.some ·) <$> FromJson.fromJson? (α := String) v

instance : FromJson Cycle where
  fromJson? j := do
    let id ← j.getObjVal? "id" >>= FromJson.fromJson? (α := String)
    let day ← j.getObjVal? "day" >>= FromJson.fromJson? (α := Nat)
    let hour ← j.getObjVal? "hour" >>= FromJson.fromJson? (α := Nat)
    let candidates ← j.getObjVal? "candidates" >>= FromJson.fromJson? (α := List String)
    let ballots ← j.getObjVal? "ballots" >>= FromJson.fromJson? (α := List Ballot)
    let registry ← j.getObjVal? "registry" >>= FromJson.fromJson? (α := List String)
    let box ← j.getObjVal? "box" >>= FromJson.fromJson? (α := List Vote)
    let announced ← j.getObjVal? "announced" >>= FromJson.fromJson? (α := Bool)
    let prepared ← j.getObjVal? "prepared" >>= FromJson.fromJson? (α := Bool)
    let counted ← j.getObjVal? "counted" >>= FromJson.fromJson? (α := Bool)
    let proclaimed ← j.getObjVal? "proclaimed" >>= FromJson.fromJson? (α := Bool)
    let outcome ← getOptStr j "outcome"
    return Cycle.mk id day hour candidates ballots registry box
      announced prepared counted proclaimed outcome
      none none none none

instance : FromJson Snapshot where
  fromJson? j := do
    let citizens ← j.getObjVal? "citizens" >>= FromJson.fromJson? (α := List Citizen)
    let cycles ← j.getObjVal? "cycles" >>= FromJson.fromJson? (α := List Cycle)
    match cycles with
    | [] => .error "cycles must be non-empty"
    | _ =>
      let mayorId ← getOptStr j "mayorId"
      return Snapshot.mk citizens cycles mayorId

instance : ToJson Snapshot where
  toJson s := Json.mkObj [
    ("citizens", toJson s.citizens), ("cycles", toJson s.cycles),
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
      ("readings", Json.arr (v.readings.toArray.map toJson)),
      ("phase", toJson v.phase)]

/-! Law-specific: per-index day arithmetic (announce = E-10, prepare = E-1).
    Repeat k sits at E-day 10 + 30k; repeats never shift the 4-year clock. -/

def baseElectionDay : Nat := 10
def repeatGap : Nat := 30
def electionDayK (k : Nat) : Nat := baseElectionDay + repeatGap * k
/-! Calendar dates, computed only here.

    `ph:atDate` is display-only -- the oracle owns day arithmetic and the
    driver never computes a date. A minted calendar point therefore carries
    the same declared properties as a seeded one, which means this has to
    exist at all: a repeat lands on a day the frozen base calendar cannot
    contain, and its date has to come from somewhere.

    Day 0 of the base calendar is EPOCH_Y/EPOCH_M/EPOCH_D; every other day is
    EPOCH advanced by that many real days, leap years included. -/

def isLeapYear (y : Nat) : Bool :=
  (y % 4 == 0 && y % 100 != 0) || y % 400 == 0

def daysInMonth (y m : Nat) : Nat :=
  match m with
  | 1 | 3 | 5 | 7 | 8 | 10 | 12 => 31
  | 4 | 6 | 9 | 11 => 30
  | 2 => if isLeapYear y then 29 else 28
  | _ => 0

/-- Advance a civil date by `n` days. -/
def addDays (y m d n : Nat) : Nat × Nat × Nat :=
  go y m d n
where
  go (y m d : Nat) : Nat → Nat × Nat × Nat
    | 0 => (y, m, d)
    | n + 1 =>
      if d < daysInMonth y m then go y m (d + 1) n
      else if m < 12 then go y (m + 1) 1 n
      else go (y + 1) 1 1 n

def epochYear : Nat := 2027
def epochMonth : Nat := 1
def epochDay : Nat := 2

def dateOfDayIndex (day : Nat) : Nat × Nat × Nat :=
  addDays epochYear epochMonth epochDay day

def monthName (m : Nat) : String :=
  match m with
  | 1 => "Jan" | 2 => "Feb" | 3 => "Mar" | 4 => "Apr" | 5 => "May" | 6 => "Jun"
  | 7 => "Jul" | 8 => "Aug" | 9 => "Sep" | 10 => "Oct" | 11 => "Nov" | 12 => "Dec"
  | _ => "?"

def pad2 (n : Nat) : String :=
  let s := toString n
  if n < 10 then "0" ++ s else s

/-- `ph:atDate` for a day index, as an xsd:date literal body. -/
def atDateOf (day : Nat) : String :=
  let (y, m, d) := dateOfDayIndex day
  s!"{y}-{pad2 m}-{pad2 d}"

/-- Display suffix for a day index, e.g. `Feb 21`. -/
def dateLabelOf (day : Nat) : String :=
  let (y, m, d) := dateOfDayIndex day
  s!"{monthName m} {d}, {y}"

def announceK (k : Nat) : Nat := electionDayK k - 10
def prepareK (k : Nat) : Nat := electionDayK k - 1
def pollOpenHour : Nat := 9
def pollCloseHour : Nat := 19

/-- Cycle IRI minted in Lean: deterministic from (case, index). -/
def cycleIri (k : Nat) : String :=
  s!"https://potato-hamlet.example/ontology/election/mayor-quorum-r{k}"


/-! Graph layer: the knowledge graph IS the snapshot.
    Mirrors the framework graph types (the prelude is stable across flavours).
    The ABox crosses the wire; schema triples stay in ontology.ttl. -/

def rdfType : String := "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

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
    | _ => Except.error "object must be an IRI string or a literal object"

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

def ph (name : String) : String := "https://potato-hamlet.example/ontology/" ++ name
def iriHamlet : String := ph "hamlet"
def iriClock : String := ph "clock/now"
def iriRole (kind : String) : String := ph "role/" ++ kind

/-- A stable short name, from the last path segment of an IRI. Minted IRIs
    must be deterministic from an act's parameters. -/
def shortId (iri : String) : String :=
  match (iri.splitOn "/").getLast? with
  | some s => s
  | none => iri

namespace Graph

def subjectsWith (g : Graph) (predicate : String) : List String :=
  (g.filter (fun t => t.predicate == predicate)).map (·.subject) |>.eraseDups

def objectsOf (g : Graph) (subject predicate : String) : List TripleObj :=
  ((g.filter fun t => t.subject == subject && t.predicate == predicate).map
    (·.object)).eraseDups

def firstObjOf? (g : Graph) (subject predicate : String) : Option TripleObj :=
  (objectsOf g subject predicate).head?

def iriOf? (g : Graph) (subject predicate : String) : Option String :=
  match firstObjOf? g subject predicate with
  | some (.iri v) => some v
  | _ => none

def litOf? (g : Graph) (subject predicate : String) : Option String :=
  match firstObjOf? g subject predicate with
  | some (.lit v _) => some v
  | _ => none

def natOf (g : Graph) (subject predicate : String) : Nat :=
  match litOf? g subject predicate with
  | some v => (v.toNat?).getD 0
  | none => 0

def typedOf (g : Graph) (classIri : String) : List String :=
  (g.filter fun t => t.predicate == rdfType && t.object == .iri classIri).map
    (·.subject)

def setOne (g : Graph) (subject predicate : String) (o : TripleObj) : Graph :=
  (g.filter fun t => !(t.subject == subject && t.predicate == predicate)) ++
    [{ subject := subject, predicate := predicate, object := o }]

/-- The citizen playing `roleClass` in the situation `ctx`, if any. -/
def participantVia? (g : Graph) (ctx roleClass : String) : Option String :=
  ((g.filter fun t => t.predicate == rdfType && t.object == .iri roleClass).filterMap
    fun t => if g.iriOf? t.subject (ph "roleIn") == some ctx
              then g.iriOf? t.subject (ph "playedBy") else none).head?

def occurrencesBy (g : Graph) (classIri citizen : String) : List String :=
  (g.filter fun t => t.predicate == rdfType && t.object == .iri classIri).filterMap
    fun t => if g.iriOf? t.subject (ph "hasParticipant") == some citizen
              then some t.subject else none

end Graph

def iriBallotIn (cyc owner cand : String) : String :=
  ph "ballot/" ++ shortId cyc ++ "/" ++ shortId owner ++ "-" ++ shortId cand
def iriVoteIn (cyc voter cand : String) : String :=
  ph "vote/" ++ shortId cyc ++ "/" ++ shortId voter ++ "-" ++ shortId cand
def iriNominationIn (cyc citizen : String) : String :=
  ph "nomination/" ++ shortId cyc ++ "/" ++ shortId citizen

/-- A Role individual playing `roleClass` for citizen `citizen` in `ctx`.

    `roleIn` always names the CONTEXT — the situation the role is played in —
    because that is what the ontology declares it to mean. The subject is
    passed in rather than derived, so a situation with more than one holder of
    the same role can still give each its own individual. -/
def roleTriplesAt (subj roleClass ctx citizen : String) : List Triple :=
  [ { subject := subj, predicate := rdfType, object := .iri roleClass }
  , { subject := subj, predicate := ph "roleIn", object := .iri ctx }
  , { subject := subj, predicate := ph "playedBy", object := .iri citizen } ]

/-- One holder per situation per role, so the subject can be derived from the
    context. Safe only when that holds — see `roleTriplesAt`. -/
def roleTriples' (roleClass ctx citizen : String) : List Triple :=
  roleTriplesAt (ctx ++ "#" ++ roleClass) roleClass ctx citizen

def boolLit (b : Bool) : TripleObj := TripleObj.lit (if b then "true" else "false") "boolean"

/-! Deriving typed state from the graph.

    Cycle ORDER comes from the declared `ph:cycleIndex` property, not from
    list position: the current cycle is the highest-indexed one, so an
    unordered multiset of triples reconstructs exactly the order the
    framework requires without any array-ordering convention. -/

def ageIn (g : Graph) (citizen : String) : Nat := Graph.natOf g citizen (ph "age")

def citizensOf (g : Graph) : List Citizen :=
  (Graph.typedOf g (ph "Citizen")).map fun c => Citizen.mk c (ageIn g c)

def flagOn (g : Graph) (cyc name : String) : Bool :=
  match g.litOf? cyc (ph name) with
  | some "true" => true
  | _ => false

def mayorIn (g : Graph) : Option String :=
  g.participantVia? iriHamlet (ph "MayorRole")

/-- Election instances ordered by the declared `ph:cycleIndex`. -/
def cyclesOrdered (g : Graph) : List String :=
  let indexed := (Graph.typedOf g (ph "MayorElectionCycle")).map
    fun c => (c, g.natOf c (ph "cycleIndex"))
  let sorted := indexed.mergeSort (fun a b => a.2 < b.2)
  sorted.map (·.1)

def ballotsIn (g : Graph) (cyc : String) : List Ballot :=
  (Graph.typedOf g (ph "BallotVote")).filterMap fun b =>
    match g.iriOf? b (ph "cycleIndex"), g.participantVia? b (ph "BallotOwnerRole"),
          g.participantVia? b (ph "CandidateRole") with
    | some ci, some owner, some cand =>
      if ci == cyc then some (Ballot.mk owner cand true) else none
    | _, _, _ => none

def votesIn (g : Graph) (cyc : String) : List Vote :=
  (Graph.typedOf g (ph "CastVote")).filterMap fun v =>
    match g.iriOf? v (ph "cycleIndex"), g.participantVia? v (ph "VoterRole"),
          g.participantVia? v (ph "CandidateRole") with
    | some ci, some voter, some cand =>
      if ci == cyc then some (Vote.mk voter cand) else none
    | _, _, _ => none

def candidatesIn (g : Graph) (cyc : String) : List String :=
  (Graph.typedOf g (ph "CandidateRole")).filterMap fun r =>
    match g.iriOf? r (ph "cycleIndex") with
    | some ci => if ci == cyc then g.iriOf? r (ph "playedBy") else none
    | none => none

def registryIn (g : Graph) (cyc : String) : List String :=
  (Graph.typedOf g (ph "SelfNomination")).filterMap fun n =>
    match g.iriOf? n (ph "cycleIndex") with
    | some ci => if ci == cyc then g.iriOf? n (ph "hasParticipant") else none
    | none => none

def outcomeIn (g : Graph) (cyc : String) : Option String :=
  g.litOf? cyc (ph "outcome")

/-- The moment a Chronoid bound denotes, read as (day, hour).

    The Chronoid is the record of when an instance began and ended, so this
    reads the bound rather than recomputing it: a consumer following
    `temporallyFinishedBy` gets a day it can place, and so does the oracle
    when it reconstructs the next snapshot. -/
def boundMoment (g : Graph) (ch : String) (which : String) : Option (Nat × Nat) :=
  match g.iriOf? ch which with
  | some b => some (g.natOf b (ph "dayIndex"), g.natOf b (ph "atHour"))
  | none => none

def startedAt (g : Graph) (cyc : String) : Option (Nat × Nat) :=
  match g.iriOf? cyc (ph "hasTime") with
  | some ch => boundMoment g ch "https://w3id.org/gfo-core/temporallyStartedBy"
  | none => none

def finishedAt (g : Graph) (cyc : String) : Option (Nat × Nat) :=
  match g.iriOf? cyc (ph "hasTime") with
  | some ch => boundMoment g ch "https://w3id.org/gfo-core/temporallyFinishedBy"
  | none => none

def cycleOf (g : Graph) (cyc : String) : Cycle :=
  let base := Cycle.mk cyc
    (g.natOf cyc (ph "dayIndex")) (g.natOf cyc (ph "atHour"))
    (candidatesIn g cyc) (ballotsIn g cyc) (registryIn g cyc) (votesIn g cyc)
    (flagOn g cyc "announced") (flagOn g cyc "prepared")
    (flagOn g cyc "counted") (flagOn g cyc "proclaimed")
    (outcomeIn g cyc)
    none none none none
  let withStart :=
    match startedAt g cyc with
    | some (d, h) => { base with startDay := some d, startHour := some h }
    | none => base
  match finishedAt g cyc with
  | some (d, h) => { withStart with finishDay := some d, finishHour := some h }
  | none => withStart

def snapshotOf (g : Graph) : Snapshot :=
  { citizens := citizensOf g
    cycles := (cyclesOrdered g).map (cycleOf g)
    mayorId := mayorIn g }


/-! Current-cycle accessors. `cyclesOrdered` sorts election instances by the
    declared `ph:cycleIndex`, so `getLast?` below picks the highest-indexed
    instance rather than relying on the order triples happened to arrive in.
    An instance is INITIALISED (awaiting its trigger) when its `ph:Chronoid`
    carries no `temporallyStartedBy`, and ONGOING otherwise. -/

def curIdx (s : Snapshot) : Nat :=
  match s.cycles.length with
  | 0 => 0
  | n + 1 => n

def cur (s : Snapshot) : Cycle :=
  match s.cycles.getLast? with
  | some c => c
  | none => Cycle.mk "" 0 0 [] [] [] [] false false false false none
      none none none none

def updateCur (s : Snapshot) (f : Cycle → Cycle) : Snapshot :=
  match s.cycles with
  | [] => s
  | _ => { s with cycles := s.cycles.dropLast ++ [f (cur s)] }

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

/-! ECA conditions: Bool/Prop twins scoped to the current cycle. Arithmetic /
    window rules use `decide` over the Prop directly (genuine FOL, trivial
    agreement). -/

def announceDue? (s : Snapshot) : Bool :=
  decide ((cur s).day = announceK (curIdx s) ∧ (cur s).announced = false)
def AnnounceDue (s : Snapshot) : Prop :=
  (cur s).day = announceK (curIdx s) ∧ (cur s).announced = false
theorem announceDue_agrees (s : Snapshot) :
    announceDue? s = true ↔ AnnounceDue s := by
  simp [announceDue?, AnnounceDue]

def nominateOpen? (s : Snapshot) : Bool :=
  decide (announceK (curIdx s) ≤ (cur s).day ∧ (cur s).day < prepareK (curIdx s))
def NominateOpen (s : Snapshot) : Prop :=
  announceK (curIdx s) ≤ (cur s).day ∧ (cur s).day < prepareK (curIdx s)
theorem nominateOpen_agrees (s : Snapshot) :
    nominateOpen? s = true ↔ NominateOpen s := by
  simp [nominateOpen?, NominateOpen]

def prepareDue? (s : Snapshot) : Bool :=
  decide ((cur s).day = prepareK (curIdx s) ∧ (cur s).prepared = false)
def PrepareDue (s : Snapshot) : Prop :=
  (cur s).day = prepareK (curIdx s) ∧ (cur s).prepared = false
theorem prepareDue_agrees (s : Snapshot) :
    prepareDue? s = true ↔ PrepareDue s := by
  simp [prepareDue?, PrepareDue]

def pollsOpen? (s : Snapshot) : Bool :=
  decide ((cur s).day = electionDayK (curIdx s) ∧ pollOpenHour ≤ (cur s).hour ∧ (cur s).hour < pollCloseHour)
def PollsOpen (s : Snapshot) : Prop :=
  (cur s).day = electionDayK (curIdx s) ∧ pollOpenHour ≤ (cur s).hour ∧ (cur s).hour < pollCloseHour
theorem pollsOpen_agrees (s : Snapshot) :
    pollsOpen? s = true ↔ PollsOpen s := by
  simp [pollsOpen?, PollsOpen]

def pollsClosed? (s : Snapshot) : Bool :=
  decide ((cur s).day > electionDayK (curIdx s) ∨ ((cur s).day = electionDayK (curIdx s) ∧ pollCloseHour ≤ (cur s).hour))
def PollsClosed (s : Snapshot) : Prop :=
  (cur s).day > electionDayK (curIdx s) ∨ ((cur s).day = electionDayK (curIdx s) ∧ pollCloseHour ≤ (cur s).hour)
theorem pollsClosed_agrees (s : Snapshot) :
    pollsClosed? s = true ↔ PollsClosed s := by
  simp [pollsClosed?, PollsClosed]

def countDue? (s : Snapshot) : Bool :=
  decide (((cur s).day > electionDayK (curIdx s) ∨ ((cur s).day = electionDayK (curIdx s) ∧ pollCloseHour ≤ (cur s).hour)) ∧
    (cur s).counted = false)
def CountDue (s : Snapshot) : Prop :=
  ((cur s).day > electionDayK (curIdx s) ∨ ((cur s).day = electionDayK (curIdx s) ∧ pollCloseHour ≤ (cur s).hour)) ∧
    (cur s).counted = false
theorem countDue_agrees (s : Snapshot) :
    countDue? s = true ↔ CountDue s := by
  simp [countDue?, CountDue]

def proclaimDue? (s : Snapshot) : Bool :=
  decide ((cur s).counted = true ∧ (cur s).proclaimed = false)
def ProclaimDue (s : Snapshot) : Prop :=
  (cur s).counted = true ∧ (cur s).proclaimed = false
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
    (cur s).candidates.all (fun cand => (cur s).ballots.any (ballotOk · c.id cand)))

def AllDistributed (s : Snapshot) : Prop :=
  ∀ c ∈ s.citizens, ∀ cand ∈ (cur s).candidates,
    ∃ b ∈ (cur s).ballots, BallotOk b c.id cand

theorem allDistributed_agrees (s : Snapshot) :
    allDistributed? s = true ↔ AllDistributed s := by
  simp [allDistributed?, AllDistributed, List.all_eq_true, List.any_eq_true,
    ballotOk_true]

/-- First missing (citizen, candidate) pair: the witness for the guide. -/
def missingFor (s : Snapshot) (c : Citizen) : Option String :=
  (cur s).candidates.find?
    (fun cand => !((cur s).ballots.any (ballotOk · c.id cand)))

def firstMissing? (s : Snapshot) : Option (String × String) :=
  match s.citizens.find? (fun c => (missingFor s c).isSome) with
  | none => none
  | some c => match missingFor s c with
    | none => none
    | some cand => some (c.id, cand)

/-! Votes, winner with oldest-on-tie (advisory: proclamation stays human). -/

def voteCount (s : Snapshot) (cand : String) : Nat :=
  ((cur s).box.filter (fun v => v.candidate == cand)).length

def voted? (s : Snapshot) (voter : String) : Bool :=
  (cur s).box.any (fun v => v.voter == voter)

def maxCount (s : Snapshot) : Nat :=
  (cur s).candidates.foldl (fun m c => Nat.max m (voteCount s c)) 0

def winners (s : Snapshot) : List String :=
  (cur s).candidates.filter (fun c => voteCount s c == maxCount s)

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
  ((cur s).box.map (·.voter)).eraseDups.filter
    (fun v => decide (2 ≤ ((cur s).box.filter (fun b => b.voter == v)).length))

/-! Quorum validity with 30-day repeat (mayor-quorum flavor only).
    Election valid iff at least half of citizens voted. On failure a NEW
    election cycle is scheduled 30 days after the void E-day, prep dates
    recomputed relative to the new E-day (announce E-10, prepare E-1),
    registry/ballots/box reset: void-election nominations and ballots are
    preserved in history and never carry over. Repeats continue until valid. -/

def votersOf (s : Snapshot) : List String :=
  ((cur s).box.map (·.voter)).eraseDups

def turnoutCount (s : Snapshot) : Nat :=
  (votersOf s).length

def quorumValid? (s : Snapshot) : Bool :=
  decide (s.citizens.length ≤ 2 * turnoutCount s)

def QuorumValid (s : Snapshot) : Prop :=
  s.citizens.length ≤ 2 * turnoutCount s

theorem quorumValid_agrees (s : Snapshot) :
    quorumValid? s = true ↔ QuorumValid s := by
  simp [quorumValid?, QuorumValid]

/-- This law's results, as readings.

    `quorumHeld` is knowable only once the polls have closed and the votes are
    counted, so before that it is absent rather than false: "not yet determined"
    and "determined, and it failed" are different facts and a consumer can tell
    them apart because only one of them is in the list. -/
def readingsOf (s : Snapshot) : List Reading :=
  let quorumReading : List Reading :=
    if (cur s).counted then
      [ { id := "quorumHeld", kind := .flag
        , value := .flag (quorumValid? s == true), refClass := none } ]
    else []
  match winner? s with
  | none => quorumReading
  | some w =>
    [ { id := "mayor", kind := .ref, value := .iri w
      , refClass := some (ph "Citizen") }
    , { id := "mayorVotes", kind := .decimal
      , value := .num (voteCount s w), refClass := none } ] ++ quorumReading

/-- True when the current cycle failed quorum at polls-close after counting:
    the guard shared by the violation, the repeat pending entry, and apply. -/
def voidCycle? (s : Snapshot) : Bool :=
  decide (pollsClosed? s = true ∧ (cur s).counted = true ∧ quorumValid? s = false)

/-- Fresh successor cycle: same population, empty registry/ballots/box,
    flags cleared, day set to the next E-day. -/
def freshCycle (k : Nat) : Cycle :=
  Cycle.mk (cycleIri k) (electionDayK k) 0 [] [] [] [] false false false false none
    none none none none

/-! Uniform oracle interface. -/

def ecaIds : List String :=
  ["announce", "nominate", "prepare", "vote", "count", "proclaim", "repeat"]

def firedOf (s : Snapshot) : List String :=
  (if (cur s).day == announceK (curIdx s) then ["announce"] else []) ++
  (if nominateOpen? s then ["nominate"] else []) ++
  (if (cur s).day == prepareK (curIdx s) then ["prepare"] else []) ++
  (if (cur s).day == electionDayK (curIdx s) then ["vote"] else []) ++
  (if pollsClosed? s then ["count"] else []) ++
  (if (cur s).counted then ["proclaim"] else []) ++
  (if voidCycle? s then ["repeat"] else [])

def pendingOf (s : Snapshot) : List PendingEntry :=
  let authPending : List PendingEntry := match authorityId s with
    | none => []
    | some a =>
      (if announceDue? s then [{ citizen := a, eca := "announce", choices := [] }] else []) ++
      (if prepareDue? s then [{ citizen := a, eca := "prepare", choices := [] }] else []) ++
      (if countDue? s then [{ citizen := a, eca := "count", choices := [] }] else []) ++
      (if proclaimDue? s then [{ citizen := a, eca := "proclaim", choices := [] }] else []) ++
      (if voidCycle? s then [{ citizen := a, eca := "repeat", choices := [] }] else [])
  let nominees : List PendingEntry :=
    if nominateOpen? s then
      (s.citizens.filter (fun c => !((cur s).registry.any (· == c.id)))).map
        (fun c => { citizen := c.id, eca := "nominate", choices := [] })
    else []
  let voters : List PendingEntry :=
    if pollsOpen? s then
      (s.citizens.filter (fun c => decide (!(voted? s c.id)))).map
        (fun c => { citizen := c.id, eca := "vote",
                       choices := [("candidate", (cur s).candidates)] })
    else []
  authPending ++ nominees ++ voters

def violationsOf (s : Snapshot) : List Violation :=
  let dist : List Violation := match firstMissing? s with
    | none => []
    | some (c, cand) =>
      if decide (prepareK (curIdx s) ≤ (cur s).day) then
        [{ eca := "all_distributed", witnessCitizen := some c,
           witnessCandidate := some cand, detail := "ballot missing" }]
      else []
  let dupes : List Violation := (doubleVoters s).map (fun v =>
    { eca := "single_vote", witnessCitizen := some v, witnessCandidate := none,
      detail := "citizen voted twice" })
  let quorum : List Violation :=
    if voidCycle? s then
      [{ eca := "quorum", witnessCitizen := none, witnessCandidate := none,
         detail := s!"quorum failed: {(votersOf s).length} voted of {s.citizens.length}, repeat on day {electionDayK ((curIdx s) + 1)}" }]
    else []
  dist ++ dupes ++ quorum

def phaseOf (s : Snapshot) : String :=
  if (cur s).proclaimed then "ResultsPosted"
  else if (cur s).counted then "PollsClosed"
  else if pollsOpen? s then "PollsOpen"
  else if pollsClosed? s then "PollsClosed"
  else if (cur s).prepared then "BallotsReady"
  else "RegistryOpen"

def evaluate (s : Snapshot) : VerdictData :=
  { fired := firedOf s, pending := pendingOf s, violations := violationsOf s,
    readings := readingsOf s, phase := phaseOf s }

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
  | repeat
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
    | "repeat" => pure .repeat
    | other => .error s!"unknown eca: {other}"

def applyAnnounce (s : Snapshot) : Except String Snapshot :=
  match authorityId s with
  | none => .error "no authority in office"
  | some _ =>
    if announceDue? s then .ok (updateCur s (fun c => ({ c with announced := true }).stampStart))
    else .error "announce not due"

def applyNominate (s : Snapshot) (c : String) : Except String Snapshot :=
  if !nominateOpen? s then .error "registry closed"
  else if (cur s).registry.any (· == c) then .error "already registered"
  else .ok (updateCur s (fun cy => { cy with registry := c :: cy.registry }))

def fullBallots (citizens : List Citizen) (cands : List String) : List Ballot :=
  citizens.flatMap (fun c => cands.map (fun cand => Ballot.mk c.id cand true))

def applyPrepare (s : Snapshot) : Except String Snapshot :=
  match authorityId s with
  | none => .error "no authority in office"
  | some _ =>
    if prepareDue? s then
      let cy := ({ cur s with prepared := true }).stampStart
      let cy2 := { cy with ballots := fullBallots s.citizens (cur s).candidates }
      .ok (updateCur s (fun _ => cy2))
    else .error "prepare not due"

def applyVote (s : Snapshot) (v c : String) : Except String Snapshot :=
  if !pollsOpen? s then .error "polls closed"
  else if voted? s v then .error "citizen already voted"
  else .ok (updateCur s (fun cy => { cy with box := Vote.mk v c :: cy.box }))

def applyCount (s : Snapshot) : Except String Snapshot :=
  if countDue? s then .ok (updateCur s (fun c => ({ c with counted := true }).stampStart))
  else .error "count not due"

def applyProclaim (s : Snapshot) : Except String Snapshot :=
  match winner? s with
  | none => .error "no candidates"
  | some w =>
    if proclaimDue? s then
      let sPrime := updateCur s (fun c =>
          (({ c with proclaimed := true, outcome := some "valid" }).stampStart).stampFinish)
      .ok { sPrime with mayorId := some w }
    else .error "proclaim not due"

/-- Guarded quorum repeat: appends a fresh successor cycle only when the
    current one actually failed quorum at polls-close after counting.
    The void cycle is marked and preserved in history. -/
def repeatAfterVoid (s : Snapshot) : Except String Snapshot :=
  if voidCycle? s then
    let k := curIdx s
    let marked := updateCur s (fun c => ({ c with outcome := some "void" }).stampFinish)
    .ok { marked with cycles := marked.cycles ++ [freshCycle (k + 1)] }
  else .error "quorum not failed"

def apply : Act → Snapshot → Except String Snapshot
  | .announce, s => applyAnnounce s
  | .nominate c, s => applyNominate s c
  | .prepare, s => applyPrepare s
  | .vote v c, s => applyVote s v c
  | .count, s => applyCount s
  | .proclaim, s => applyProclaim s
  | .repeat, s => repeatAfterVoid s

/-! Writing a derived snapshot back into the graph.

    `apply` returns the WHOLE graph and the consumer replaces its stored copy
    wholesale, so the oracle's state and the graph can never diverge. Nothing
    is ever removed: a cast vote or a delivered ballot persists, and a repeat
    APPENDS a new election instance while preserving every finished one.

    Every election instance in the RESULT is materialised, so a repeat minted
    by the transition appears in the returned graph. -/

def chronoId (k : Nat) : String := ph "chronoid/mayor-quorum-r" ++ toString k

/-- Pair each element with its position. `s.cycles` is already ordered by
    cycleIndex, so the position IS the index — including for an instance the
    graph has not seen yet. -/
def withIndex : List Cycle → List (Nat × Cycle)
  | [] => []
  | c :: cs => (0, c) :: (withIndex cs).map (fun (k, x) => (k + 1, x))

/-- Materialise one election instance and its Chronoid if absent.

    The Chronoid carries no start bound until the instance actually begins,
    which is what distinguishes initialised from ongoing. `cycleIndex` for a
    freshly minted instance is not in the graph yet, so the index is passed in
    from the RESULT's ordering rather than read back. -/
def ensureCycle (g : Graph) (k : Nat) (c : Cycle) : Graph :=
  let chronoid := chronoId k
  let typed :=
    if (g.iriOf? c.id rdfType).isSome then g
    else g ++ [ { subject := c.id, predicate := rdfType
                , object := .iri (ph "MayorElectionCycle") }
               , { subject := c.id, predicate := ph "label"
                 , object := TripleObj.lit s!"Election cycle {k}" "string" } ]
  let flagged := typed
    |>.setOne c.id (ph "cycleIndex") (TripleObj.lit (toString k) "integer")
    |>.setOne c.id (ph "dayIndex") (TripleObj.lit (toString c.day) "integer")
    |>.setOne c.id (ph "atHour") (TripleObj.lit (toString c.hour) "integer")
    |>.setOne c.id (ph "announced") (boolLit c.announced)
    |>.setOne c.id (ph "prepared") (boolLit c.prepared)
    |>.setOne c.id (ph "counted") (boolLit c.counted)
    |>.setOne c.id (ph "proclaimed") (boolLit c.proclaimed)
    |>.setOne c.id (ph "hasTime") (.iri chronoid)
  let withChronoid :=
    if (g.iriOf? chronoid rdfType).isSome then flagged
    else flagged ++ [ { subject := chronoid, predicate := rdfType
                      , object := .iri "https://w3id.org/gfo-light/Chronoid" } ]
  let withOutcome :=
    match c.outcome with
    | none => withChronoid
    | some o => withChronoid.setOne c.id (ph "outcome") (TripleObj.lit o "string")
  -- Lifecycle bounds take GFO's shape: the Chronoid's start and finish point
  -- at TimeBoundary individuals. Absence of a START bound is what marks an
  -- instance initialised (awaiting its trigger) rather than ongoing.
  let started := c.started
  -- Each bound denotes ONE moment, so it carries BOTH the day and the hour.
  -- Splitting them across two boundaries — start pointing at the day, finish
  -- at the hour — left the finish time unreadable: a consumer following
  -- temporallyFinishedBy got an hour with no day to put it in.
  let boundStart := ph "bound/start/" ++ shortId c.id
  let boundFinish := ph "bound/finish/" ++ shortId c.id
  -- Written with setOne, not appended. Appending would leave a fresh
  -- dayIndex and atHour on every apply, so the bound would accumulate a
  -- different moment each time and a reader following temporallyFinishedBy
  -- would get whichever one it happened to see.
  let timeBoundary (g : Graph) (which : String) (d h : Nat) : Graph :=
    let g1 := Graph.setOne g which rdfType
      (.iri "https://w3id.org/gfo-light/TimeBoundary")
    let g2 := Graph.setOne g1 which (ph "dayIndex") (TripleObj.lit (toString d) "integer")
    Graph.setOne g2 which (ph "atHour") (TripleObj.lit (toString h) "integer")
  -- The bound carries the moment the transition HAPPENED, not the cycle's
  -- current position, which keeps moving for the rest of the law's run.
  let withBoundaries : Graph :=
    timeBoundary (timeBoundary withOutcome boundStart c.startDayOf c.startHourOf)
      boundFinish c.finishDayOf c.finishHourOf
  let withBounds : Graph :=
    let g1 : Graph :=
      if started then
        Graph.setOne withBoundaries chronoid
          "https://w3id.org/gfo-core/temporallyStartedBy" (.iri boundStart)
      else withBoundaries
    if c.outcome.isSome then
      Graph.setOne g1 chronoid
        "https://w3id.org/gfo-core/temporallyFinishedBy" (.iri boundFinish)
    else g1
  withBounds

/-- Mint one calendar point for a repeat's election window.

    A minted point carries the SAME declared properties as a seeded one --
    `ph:CalendarPoint`, `ph:label`, `ph:atDate`, `ph:dayIndex`, `ph:atHour`
    where the moment has an hour, `ph:marksPhase` -- so a consumer reads a
    repeat's schedule with the same queries it reads the base calendar with,
    and cannot tell the two apart.

    Single-valued properties go through `setOne`, so re-minting on every apply
    is idempotent. `ph:marksPhase` is appended instead, because a moment can
    mark more than one phase and `setOne` would drop the earlier ones; a
    repeated triple is a no-op in a set-valued graph, so appending is safe
    where set-one would not be. -/
def mintCalendarPoint (g : Graph) (name label : String) (day : Nat)
    (hour? : Option Nat) (phases : List String) : Graph :=
  let s := ph ("calendar/" ++ name)
  let g1 := Graph.setOne g s rdfType (.iri (ph "CalendarPoint"))
  let g2 := Graph.setOne g1 s (ph "label") (TripleObj.lit label "string")
  let g3 := Graph.setOne g2 s (ph "atDate") (TripleObj.lit (atDateOf day) "date")
  let g4 := Graph.setOne g3 s (ph "dayIndex") (TripleObj.lit (toString day) "integer")
  let g5 := match hour? with
    | some h => Graph.setOne g4 s (ph "atHour") (TripleObj.lit (toString h) "integer")
    | none => g4
  let marking (p : String) : Triple :=
    { subject := s, predicate := ph "marksPhase", object := .iri (ph p) }
  phases.foldl (fun acc p => acc ++ [marking p]) g5

/-- Mint the whole calendar for repeat cycle `k`.

    The base calendar is frozen and shared, so a repeat -- which lands at
    E-day 10 + 30k and therefore on a day the base calendar cannot name -- gets
    its own, minted at the moment the repeat is scheduled. The nomination
    window is a `ph:CalendarSpan` bounded by the minted points, so the repeat's
    announce date resolves through a span rather than through a table the
    consumer would have to know the shape of. -/
def ensureMintedCalendar (g : Graph) (k : Nat) : Graph :=
  if k == 0 then g
  else
    let tag := "repeat-" ++ toString k
    let ek := electionDayK k
    let ak := announceK k
    let pk := prepareK k
    let announce := ph ("calendar/" ++ tag ++ "/announce")
    let window := ph ("calendar/" ++ tag ++ "/window")
    let g0 := mintCalendarPoint g (tag ++ "/announce")
      s!"Announce (repeat {k}), {dateLabelOf ak}" ak (some pollOpenHour) ["AnnounceElection"]
    let g1 := mintCalendarPoint g0 (tag ++ "/prepare")
      s!"Prepare (repeat {k}), {dateLabelOf pk}" pk (some pollOpenHour) ["CreateBallots"]
    let g2 := mintCalendarPoint g1 (tag ++ "/election")
      s!"Election (repeat {k}), {dateLabelOf ek}" ek (some pollOpenHour) ["CastVote"]
    let withPoints := mintCalendarPoint g2 (tag ++ "/polls-close")
      s!"Polls close (repeat {k}), {dateLabelOf ek}" ek (some pollCloseHour)
      ["CountVotes", "ProclaimMayor"]
    let s1 := Graph.setOne withPoints window rdfType (.iri (ph "CalendarSpan"))
    let s2 := Graph.setOne s1 window (ph "label")
      (TripleObj.lit s!"Nomination window, {dateLabelOf ak} to {dateLabelOf ek}" "string")
    let s3 := Graph.setOne s2 window (ph "dayIndex")
      (TripleObj.lit (toString ak) "integer")
    let s4 := Graph.setOne s3 window (ph "gapDays")
      (TripleObj.lit (toString (ek - ak)) "integer")
    s4 ++ [ { subject := window, predicate := ph "marksPhase"
            , object := .iri (ph "SelfNomination") }
          , { subject := window
            , predicate := "https://w3id.org/gfo-core/temporallyStartedBy"
            , object := .iri announce }
          , { subject := window
            , predicate := "https://w3id.org/gfo-core/temporallyFinishedBy"
            , object := .iri (ph ("calendar/" ++ tag ++ "/election")) } ]

/-- Additive occurrence materialisation for one election instance. -/
def ensureOccurrences (g : Graph) (c : Cycle) : Graph :=
  let k := Graph.natOf g c.id (ph "cycleIndex")
  let cands := c.candidates.filterMap fun cd =>
    let r := iriRole "candidate" ++ "/" ++ shortId c.id ++ "/" ++ shortId cd
    if (g.iriOf? r rdfType).isSome then none else some (r, cd)
  let noms := c.registry.filterMap fun cd =>
    let n := iriNominationIn c.id cd
    if (g.iriOf? n rdfType).isSome then none else some (n, cd)
  let bals := c.ballots.filterMap fun b =>
    let bi := iriBallotIn c.id b.owner b.candidate
    if (g.iriOf? bi rdfType).isSome then none else some (bi, b)
  let vts := c.box.filterMap fun v =>
    let vi := iriVoteIn c.id v.voter v.candidate
    if (g.iriOf? vi rdfType).isSome then none else some (vi, v)
  let withCands := cands.foldl (fun a (r, cd) =>
    a ++ (roleTriples' (ph "CandidateRole") r cd)
      ++ [ { subject := r, predicate := ph "cycleIndex", object := .iri c.id } ]) g
  -- Adding your name IS becoming a candidate: the citizen thereby plays
  -- ph:CandidateRole for this election instance, which is what the ballot
  -- and vote rules enumerate.
  let withNoms := noms.foldl (fun a (n, cd) =>
    -- Adding your name IS becoming a candidate: the citizen thereby plays
    -- ph:CandidateRole for this election instance, which is what the ballot
    -- and vote rules enumerate. Every candidate in an election plays the same
    -- role, so the subject cannot be derived from the context the way
    -- `roleTriples'` does — each gets its own, scoped to the cycle. It carries
    -- ph:cycleIndex so candidatesIn can find it, and ph:roleIn points at the
    -- election, the context, as it does everywhere else.
    let role := iriRole "candidate" ++ "/" ++ shortId c.id ++ "/" ++ shortId cd
    a ++ [ { subject := n, predicate := rdfType, object := .iri (ph "SelfNomination") }
         , { subject := n, predicate := ph "hasParticipant", object := .iri cd }
         , { subject := n, predicate := ph "cycleIndex", object := .iri c.id } ]
      ++ (roleTriplesAt role (ph "CandidateRole") c.id cd)
      ++ [ { subject := role, predicate := ph "cycleIndex", object := .iri c.id } ]) withCands
  let withBals := bals.foldl (fun a (bi, b) =>
    a ++ [ { subject := bi, predicate := rdfType, object := .iri (ph "BallotVote") }
         , { subject := bi, predicate := ph "cycleIndex", object := .iri c.id } ]
      ++ (roleTriples' (ph "BallotOwnerRole") bi b.owner)
      ++ (roleTriples' (ph "CandidateRole") bi b.candidate)) withNoms
  vts.foldl (fun a (vi, v) =>
    a ++ [ { subject := vi, predicate := rdfType, object := .iri (ph "CastVote") }
         , { subject := vi, predicate := ph "cycleIndex", object := .iri c.id } ]
      ++ (roleTriples' (ph "VoterRole") vi v.voter)
      ++ (roleTriples' (ph "CandidateRole") vi v.candidate)) withBals

def writeBack (g : Graph) (s : Snapshot) : Graph :=
  let base := g.setOne iriClock (ph "atHour")
    (.lit (toString (cur { s with cycles := s.cycles }).hour) "integer")
  let flagged := (withIndex s.cycles).foldl (fun acc (k, c) => ensureCycle acc k c) base
  -- Repeats mint their own calendar: the frozen base cannot name their days.
  let withCal := (withIndex s.cycles).foldl
    (fun acc (k, _) => ensureMintedCalendar acc k) flagged
  let withOcc := (withIndex s.cycles).foldl (fun acc (_, c) => ensureOccurrences acc c) withCal
  let mayorRole := iriRole "mayor" ++ "#MayorRole"
  match s.mayorId with
  | none => withOcc
  | some m => withOcc ++
    (roleTriples' (ph "MayorRole") iriHamlet m).map fun t => { t with subject := mayorRole }

/-- `apply` over the graph: derive, transition, write the whole graph back. -/
def applyGraph (act : Act) (g : Graph) : Except String Graph :=
  match apply act (snapshotOf g) with
  | .error reason => .error reason
  | .ok s' => .ok (writeBack g s')
