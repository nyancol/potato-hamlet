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

/-- A ballot is not a thing: it is a MEANING a sheet plays in one election.

    A sheet of paper does not become a ballot by being written on. It plays the
    role of one, so the sheet is the holder (`sheet`), the election is the
    situation, and `candidate` is resolved through the Role's `ph:denotes` --
    never by comparing the written literal to a name, which is why `candidate`
    can differ from the text on the paper and still be right.

    `delivered` is read off the graph, not set at construction: it is true when
    the sheet sits in a mailbox. -/
structure Ballot where
  sheet : String
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
  -- No `day`/`hour` here. A cycle's SCHEDULE comes from `ph:cycleIndex` plus
  -- announceK/prepareK/electionDayK, and the PRESENT comes from `ph:Clock` and
  -- nowhere else. A per-instance position was a second copy of the clock, and
  -- the graph would then hold the present twice with no declared way to tell
  -- which was the real one.
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
  -- The DECLARED `ph:cycleIndex`, and whether the instance has finished. Both
  -- are read from the graph rather than inferred from where the instance sits
  -- in a list: a wire round-trip gives no array ordering, so position carries
  -- no meaning, and a rule that read it would be right only by accident.
  idx : Nat
  finished : Bool
deriving Repr, DecidableEq

/-- The moments the Chronoid's start and finish bounds denote, read back from
    the bound individuals. Absent means not begun / not ended, which is what
    distinguishes an initialised instance from an ongoing one. -/
def Cycle.startMoment (c : Cycle) : Option (Nat × Nat) :=
  match c.startDay, c.startHour with
  | some d, some h => some (d, h)
  | _, _ => none

def Cycle.finishMoment (c : Cycle) : Option (Nat × Nat) :=
  match c.finishDay, c.finishHour with
  | some d, some h => some (d, h)
  | _, _ => none

/-- Record the moment the instance began, if it has not been recorded.

    The moment is the clock's, supplied by the caller -- NOT the cycle's stored
    day. This law previously stamped `c.day`, which is the cycle's SCHEDULE
    rather than when anything happened, so a bound read as the day the election
    was due no matter when the act was performed. `requisitions` stamps from the
    clock the same way. -/
def Cycle.stampStartAt (c : Cycle) (day hour : Nat) : Cycle :=
  { c with
    startDay := some (match c.startDay with | some d => d | none => day)
    startHour := some (match c.startHour with | some h => h | none => hour) }

/-- Record the moment the instance ended, if it has not been recorded. -/
def Cycle.stampFinishAt (c : Cycle) (day hour : Nat) : Cycle :=
  { c with
    finishDay := some (match c.finishDay with | some d => d | none => day)
    finishHour := some (match c.finishHour with | some h => h | none => hour) }

def Cycle.started (c : Cycle) : Bool :=
  c.announced || c.prepared || c.counted || c.proclaimed

/-- A thing, and the citizen whose it is.

    A structure rather than a `String × String` because two `Snapshot` fields
    carry this shape -- the paper supply and the mailboxes -- and they were
    built in OPPOSITE orders: one was `(thing, owner)` and the other
    `(owner, thing)`. Both read correctly at their own use site and neither says
    which is which, so a caller with the other convention in mind gets a citizen's
    IRI where a mailbox was expected and the law refuses a delivery the seed had
    plainly supplied. A named field cannot be transposed. -/
structure Owned where
  thing : String
  owner : String
deriving Repr, DecidableEq

instance : FromJson Owned where
  fromJson? j := do
    let thing ← j.getObjVal? "thing" >>= FromJson.fromJson? (α := String)
    let owner ← j.getObjVal? "owner" >>= FromJson.fromJson? (α := String)
    return Owned.mk thing owner

instance : ToJson Owned where
  toJson o := Json.mkObj [("thing", toJson o.thing), ("owner", toJson o.owner)]

/-- Closed-world snapshot: enumerates the full finite population plus the
    full election-cycle history. TTL ids = JSON ids = Lean ids.
    Population (`citizens`) and office (`mayorId`) are global; everything
    else lives per cycle. The current cycle is the last element
    (invariant: at least one cycle). -/
structure Snapshot where
  /-- The current position, read from `ph:Clock` and nowhere else. A cycle's
      own `ph:dayIndex` is NOT a second copy of this: it is dropped in 1.4, and
      a cycle's schedule comes from `ph:cycleIndex` plus `announceK`/`prepareK`/
      `electionDayK`. -/
  day : Nat
  hour : Nat
  citizens : List Citizen
  cycles : List Cycle
  mayorId : Option String
  /-- Blank sheets the hamlet has, each with the citizen whose papers it is, in
      canonical order. The supply is SEEDED rather than minted, because
      law.txt:11 requires one paper per candidate for each citizen and that
      count is fixed by the registry at preparation time -- not knowable when the
      world is seeded. `prepare` writes on what it needs from here and refuses
      naming a shortfall if the registry asks for more than the drawer holds. -/
  sheets : List Owned
  /-- Things qualified to inscribe. Seeded as a QUALIFICATION rather than a
      kind: law.txt never says "with a pen", so a hamlet stocked only with some
      other inscriptible thing satisfies `prepare`, and one with none does not. -/
  instruments : List String
  /-- The mailboxes, each with the citizen whose it is, as law.txt:12 states it
      ("the mailbox of each citizen"). A duty whose premise fails here is refused
      naming the citizen rather than inventing somewhere to put the papers. -/
  mailboxes : List Owned
  /-- The ballot boxes, in canonical order. A named thing, not a supply: a vote
      has nowhere to go without one, so `vote` refuses rather than recording a
      vote that reached no box. -/
  ballotBoxes : List String
deriving Repr, DecidableEq

/-- One duty owed by one citizen, on one process instance.

    `process` names the instance the duty belongs to, so a consumer can group
    duties under the process they serve and two duties that look alike are not
    mistaken for the same one. `choices` names the options available at this
    instant for any parameter the manifest sources from `choices`, so a
    consumer can build a complete act without reading law-specific state.

    In the flat shape there is a single named instance, so `process` is
    constant; the history shape resolves it per entry, and it may not be the
    instance a past-dependent duty arose from. -/
structure PendingEntry where
  citizen : String
  eca : String
  process : String
  choices : List (String × List String)
deriving Repr, DecidableEq

/-! Structured violation witnesses.

    A violation used to carry flattened per-law fields -- `witnessCitizen` and
    `witnessCandidate` -- so the witness was only interpretable by a consumer
    that already knew which law it was reading, and a law whose violation was
    about a COUNT rather than a pair of individuals had nowhere to put it. The
    quorum failure is the case that mattered: the compiled oracle returned
    null for both fields and conveyed the counts only inside the English
    `detail` string, so nothing machine-readable survived.

    `refs` names the individuals that break a quantified condition and
    `counts` the quantities that fell short. That pair suffices for the whole
    framework FOL subset -- universal or existential over finite sets, plus
    counting -- so no law needs a witness field of its own, ever. -/

/-- One quantity that fell short, named so it can be read without the law. -/
structure CountWitness where
  name : String
  value : Nat
deriving Repr, DecidableEq

structure Witness where
  refs : List String
  counts : List CountWitness
deriving Repr, DecidableEq

def Witness.ofRefs (refs : List String) : Witness :=
  { refs := refs, counts := [] }

def Witness.withCounts (refs : List String) (counts : List (String × Nat)) : Witness :=
  { refs := refs, counts := counts.map (fun (n, v) => CountWitness.mk n v) }

instance : ToJson CountWitness where
  toJson w := Json.mkObj [("name", toJson w.name), ("value", toJson w.value)]

instance : ToJson Witness where
  toJson w :=
    Json.mkObj [
      ("refs", Json.arr (w.refs.toArray.map toJson)),
      ("counts", Json.arr (w.counts.toArray.map toJson))]

structure Violation where
  eca : String
  witness : Witness
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
    let sheet ← j.getObjVal? "sheet" >>= FromJson.fromJson? (α := String)
    let owner ← j.getObjVal? "owner" >>= FromJson.fromJson? (α := String)
    let candidate ← j.getObjVal? "candidate" >>= FromJson.fromJson? (α := String)
    let delivered ← j.getObjVal? "delivered" >>= FromJson.fromJson? (α := Bool)
    return { sheet, owner, candidate, delivered }

instance : ToJson Ballot where
  toJson b := Json.mkObj [("sheet", toJson b.sheet), ("owner", toJson b.owner),
    ("candidate", toJson b.candidate), ("delivered", toJson b.delivered)]

instance : FromJson Vote where
  fromJson? j := do
    let voter ← j.getObjVal? "voter" >>= FromJson.fromJson? (α := String)
    let candidate ← j.getObjVal? "candidate" >>= FromJson.fromJson? (α := String)
    return { voter, candidate }

instance : ToJson Vote where
  toJson v := Json.mkObj [("voter", toJson v.voter), ("candidate", toJson v.candidate)]

instance : ToJson Cycle where
  toJson c := Json.mkObj [
    ("id", toJson c.id),
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

/-- A list of IRIs, defaulting to empty when absent. The paper supply and the
    instruments are seeded facts about the hamlet, so a snapshot that predates
    them still parses rather than failing the round-trip. -/
private def getListStr (j : Json) (k : String) : List String :=
  match j.getObjVal? k with
  | .error _ => []
  | .ok v => match FromJson.fromJson? (α := List String) v with
    | .ok xs => xs
    | .error _ => []

/-- A list of owned things, defaulting to empty when absent. -/
private def getOwnedList (j : Json) (k : String) : List Owned :=
  match j.getObjVal? k with
  | .error _ => []
  | .ok v => match FromJson.fromJson? (α := List Owned) v with
    | .ok xs => xs
    | .error _ => []

instance : FromJson Cycle where
  fromJson? j := do
    let id ← j.getObjVal? "id" >>= FromJson.fromJson? (α := String)
    let candidates ← j.getObjVal? "candidates" >>= FromJson.fromJson? (α := List String)
    let ballots ← j.getObjVal? "ballots" >>= FromJson.fromJson? (α := List Ballot)
    let registry ← j.getObjVal? "registry" >>= FromJson.fromJson? (α := List String)
    let box ← j.getObjVal? "box" >>= FromJson.fromJson? (α := List Vote)
    let announced ← j.getObjVal? "announced" >>= FromJson.fromJson? (α := Bool)
    let prepared ← j.getObjVal? "prepared" >>= FromJson.fromJson? (α := Bool)
    let counted ← j.getObjVal? "counted" >>= FromJson.fromJson? (α := Bool)
    let proclaimed ← j.getObjVal? "proclaimed" >>= FromJson.fromJson? (α := Bool)
    let outcome ← getOptStr j "outcome"
    return Cycle.mk id candidates ballots registry box
      announced prepared counted proclaimed outcome
      none none none none 0 true

instance : FromJson Snapshot where
  fromJson? j := do
    let day ← j.getObjVal? "day" >>= FromJson.fromJson? (α := Nat)
    let hour ← j.getObjVal? "hour" >>= FromJson.fromJson? (α := Nat)
    let citizens ← j.getObjVal? "citizens" >>= FromJson.fromJson? (α := List Citizen)
    let cycles ← j.getObjVal? "cycles" >>= FromJson.fromJson? (α := List Cycle)
    -- The paper supply and the instruments are SEEDED facts about the hamlet,
    -- so they are re-derived from the graph on every `snapshotOf`. Read leniently
    -- here so a snapshot that predates them still round-trips.
    let sheets := getOwnedList j "sheets"
    let instruments := getListStr j "instruments"
    let mailboxes := getOwnedList j "mailboxes"
    let ballotBoxes := getListStr j "ballotBoxes"
    match cycles with
    | [] => .error "cycles must be non-empty"
    | _ =>
      let mayorId ← getOptStr j "mayorId"
      return Snapshot.mk day hour citizens cycles mayorId sheets instruments
        mailboxes ballotBoxes

instance : ToJson Snapshot where
  toJson s := Json.mkObj [
    ("day", toJson s.day), ("hour", toJson s.hour),
    ("citizens", toJson s.citizens), ("cycles", toJson s.cycles),
    ("sheets", toJson s.sheets), ("instruments", toJson s.instruments),
    ("mailboxes", toJson s.mailboxes), ("ballotBoxes", toJson s.ballotBoxes),
    ("mayorId", match s.mayorId with | none => Json.null | some m => toJson m)]

instance : ToJson Violation where
  toJson v := Json.mkObj [
    ("eca", toJson v.eca),
    ("witness", toJson v.witness),
    ("detail", toJson v.detail)]

/-- A pending entry as JSON: the ECA plus any parameter choices. -/
def pendingEntryJson (p : PendingEntry) : Json :=
  let base : List (String × Json) :=
    [("eca", toJson p.eca), ("process", toJson p.process)]
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
def gfoTimeBoundary : String := "https://w3id.org/gfo-light/TimeBoundary"
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

/-- A ballot Role's IRI: a function of the OCCURRENCE and the SHEET.

    It no longer names the candidate. A sheet plays at most one ballot role per
    election, so the sheet identifies it, and deriving the IRI from the
    occurrence is what makes re-deriving it a no-op: writing the same candidate
    twice lands on the same individual rather than minting a second one. -/
def iriBallotIn (cyc sheet : String) : String :=
  ph "ballot/" ++ shortId cyc ++ "/" ++ shortId sheet

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

/-- The population, in a canonical order.

    Sorted by IRI because everything downstream observes it: which citizen a
    missing-ballot witness names, how `absentees` orders a quorum failure's
    refs, and which of two equally old candidates `oldestId` keeps. Left in
    wire order those all vary with the order the triples happened to be sent
    in, and the wire format is an unordered list -- so two round-trips of the
    same graph would disagree, with nothing in the state having changed. -/
def citizensOf (g : Graph) : List Citizen :=
  ((Graph.typedOf g (ph "Citizen")).map fun c => Citizen.mk c (ageIn g c)).mergeSort
    (fun a b => a.id < b.id)

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

/-- Where this ballot was put, in this election. `none` while it is undelivered.

    On the ROLE, not the sheet. A sheet is a reusable physical object -- one
    supply of paper serves every election -- so a sheet left in its owner's
    mailbox by one election is still there for the next, and a delivery recorded
    against the sheet would make the next election's ballots read as delivered
    before anyone carried them. The Role's IRI is a function of the occurrence, so
    scoping delivery to it costs nothing and the distribution check stops
    passing on nothing. -/
def deliveredTo? (g : Graph) (role : String) : Option String :=
  g.iriOf? role (ph "deliveredTo")

/-- The ballots of one election, read back as Roles.

    The candidate comes from `ph:denotes` -- the Role's relation to the citizen
    it stands for -- and the owner from the sheet's own `ph:ownedBy`. The written
    literal is never consulted, which is why the text on the paper may spell the
    name differently from the citizen's label and still resolve to the same
    person.

    Each Role individual carries exactly one `ph:playedBy`: the sheet. The owner
    is therefore not a second role on the ballot but the sheet's own
    `ph:ownedBy`, which keeps one place in the graph answering "whose ballot is
    this" rather than two. -/
def ballotsIn (g : Graph) (cyc : String) : List Ballot :=
  (Graph.typedOf g (ph "BallotVote")).filterMap fun r =>
    match g.iriOf? r (ph "roleIn"), g.iriOf? r (ph "playedBy"), g.iriOf? r (ph "denotes") with
    | some ctx, some sheet, some cand =>
      if ctx == cyc then
        match g.iriOf? sheet (ph "ownedBy") with
        | some owner =>
          some (Ballot.mk sheet owner cand ((deliveredTo? g r).isSome))
        | none => none
      else none
    | _, _, _ => none

/-- The boxes a vote is put into, in canonical order.

    law.txt:13 requires a big closed box standing in the townhall where everyone
    can see it. It is a NAMED thing rather than a supply: there is one, it is
    seeded, and a vote has nowhere to go without it -- which is what makes it the
    individual this law declares an act as acting on. -/
def boxesOf (g : Graph) : List String :=
  ((Graph.typedOf g (ph "BallotBox")).mergeSort (fun a b => a < b))

/-- The blank sheets the hamlet has, each with the citizen whose papers they are,
    in canonical order.

    Sorted because the pairing below is positional -- a citizen's first ballot
    goes on their first sheet -- and the wire format is unordered: left in wire
    order, which sheet a given ballot landed on would differ between two
    round-trips of one graph. -/
def sheetsOf (g : Graph) : List Owned :=
  ((Graph.typedOf g (ph "Sheet")).filterMap fun sh =>
    match g.iriOf? sh (ph "ownedBy") with
    | some owner => some (Owned.mk sh owner)
    | none => none).mergeSort (fun a b =>
      a.owner < b.owner || (a.owner == b.owner && a.thing < b.thing))

/-- One citizen's sheets, in canonical order. -/
def sheetsFor (s : Snapshot) (citizen : String) : List String :=
  ((s.sheets.filter (fun o => o.owner == citizen)).map (·.thing))

/-- Things qualified to inscribe. The qualification, not the kind: the law
    never says what is held, so this is every individual bearing
    `ph:Inscriptible` whatever else it happens to be. -/
def instrumentsOf (g : Graph) : List String :=
  (Graph.typedOf g (ph "Inscriptible")).mergeSort (fun a b => a < b)

/-- A citizen's mailbox, as law.txt:12 states it: each citizen has one. -/
def mailboxOf (g : Graph) (citizen : String) : Option String :=
  ((Graph.typedOf g (ph "Mailbox")).filterMap fun m =>
    if g.iriOf? m (ph "ownedBy") == some citizen then some m else none).head?

/-- The mailboxes, each with the citizen whose it is, in canonical order. -/
def mailboxesOf (g : Graph) : List Owned :=
  ((Graph.typedOf g (ph "Mailbox")).filterMap fun m =>
    match g.iriOf? m (ph "ownedBy") with
    | some owner => some (Owned.mk m owner)
    | none => none).mergeSort (fun a b =>
      a.owner < b.owner || (a.owner == b.owner && a.thing < b.thing))

def votesIn (g : Graph) (cyc : String) : List Vote :=
  (Graph.typedOf g (ph "CastVote")).filterMap fun v =>
    match g.iriOf? v (ph "cycleIndex"), g.participantVia? v (ph "VoterRole"),
          g.participantVia? v (ph "CandidateRole") with
    | some ci, some voter, some cand =>
      if ci == cyc then some (Vote.mk voter cand) else none
    | _, _, _ => none

def candidatesIn (g : Graph) (cyc : String) : List String :=
  let found := (Graph.typedOf g (ph "CandidateRole")).filterMap fun r =>
    match g.iriOf? r (ph "cycleIndex") with
    | some ci => if ci == cyc then g.iriOf? r (ph "playedBy") else none
    | none => none
  found.mergeSort (fun a b => a < b)

def registryIn (g : Graph) (cyc : String) : List String :=
  let found := (Graph.typedOf g (ph "SelfNomination")).filterMap fun n =>
    match g.iriOf? n (ph "cycleIndex") with
    | some ci => if ci == cyc then g.iriOf? n (ph "hasParticipant") else none
    | none => none
  found.mergeSort (fun a b => a < b)

def outcomeIn (g : Graph) (cyc : String) : Option String :=
  g.litOf? cyc (ph "outcome")

/-- Has this instance finished? Declared, not positional: a historical instance
    is one whose `Chronoid` carries a finish bound, so that bound is what makes
    an instance past rather than where it appears in the graph. -/
def finishedIn (g : Graph) (cyc : String) : Bool :=
  match g.iriOf? cyc (ph "hasTime") with
  | some ch => (g.iriOf? ch "https://w3id.org/gfo-core/temporallyFinishedBy").isSome
  | none => true

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
    (candidatesIn g cyc) (ballotsIn g cyc) (registryIn g cyc) (votesIn g cyc)
    (flagOn g cyc "announced") (flagOn g cyc "prepared")
    (flagOn g cyc "counted") (flagOn g cyc "proclaimed")
    (outcomeIn g cyc)
    none none none none
    (g.natOf cyc (ph "cycleIndex")) (finishedIn g cyc)
  let withStart :=
    match startedAt g cyc with
    | some (d, h) => { base with startDay := some d, startHour := some h }
    | none => base
  match finishedAt g cyc with
  | some (d, h) => { withStart with finishDay := some d, finishHour := some h }
  | none => withStart

/-- The current position, from the single `ph:Clock` the framework fixes,
    FLOORED at every moment the graph already records.

    The clock is untrusted input: it is written by the runtime and can be set to
    anything. But it is the graph's only free variable, so a value earlier than
    a moment already recorded would let the world contradict itself -- rewinding
    to before polls close reopened the polls and admitted a vote into a cycle
    that had already been counted. The floor is every `gfo-light:TimeBoundary`
    the graph holds, because those are moments an act recorded and nothing may
    retract.

    `requisitions` floors the same way. The floor is what makes totality and
    monotonicity separate guarantees: total over absurd values, monotone over
    recorded ones. -/
def recordedMoments (g : Graph) : List (Nat × Nat) :=
  (Graph.typedOf g gfoTimeBoundary).map fun b =>
    (Graph.natOf g b (ph "dayIndex"), Graph.natOf g b (ph "atHour"))

/-- Lexicographic order on a moment: day first, then hour. -/
def momentAfter (a b : Nat × Nat) : Bool :=
  decide (a.1 > b.1 ∨ (a.1 == b.1 ∧ a.2 > b.2))

def clockOf (g : Graph) : Nat × Nat :=
  let now := (Graph.natOf g iriClock (ph "dayIndex"),
              Graph.natOf g iriClock (ph "atHour"))
  (recordedMoments g).foldl (fun acc m => if momentAfter m acc then m else acc) now

def snapshotOf (g : Graph) : Snapshot :=
  let (d, h) := clockOf g
  { day := d, hour := h
    citizens := citizensOf g
    cycles := (cyclesOrdered g).map (cycleOf g)
    mayorId := mayorIn g
    sheets := sheetsOf g
    instruments := instrumentsOf g
    mailboxes := mailboxesOf g
    ballotBoxes := boxesOf g }


/-! Current-cycle accessors. `cyclesOrdered` sorts election instances by the
    declared `ph:cycleIndex`, so `getLast?` below picks the highest-indexed
    instance rather than relying on the order triples happened to arrive in.
    An instance is INITIALISED (awaiting its trigger) when its `ph:Chronoid`
    carries no `temporallyStartedBy`, and ONGOING otherwise. -/

/-- The current instance: the one that has not finished.

    Chosen by DECLARED lifecycle state -- an instance with no finish bound on
    its `Chronoid` -- rather than by being the last element. The two coincide
    only because the law always creates the successor after closing its
    predecessor; relying on the position would break the moment it did not, and
    a wire round-trip carries no array order to rely on anyway.

    `idx` is the declared `ph:cycleIndex`, so the per-repeat day arithmetic keys
    off what the graph says the instance is rather than off its rank.
-/
def ongoing (s : Snapshot) : List Cycle :=
  s.cycles.filter (fun c => !c.finished)

def highestByIdx (cs : List Cycle) : Option Cycle :=
  cs.foldl (fun best c => match best with
    | none => some c
    | some b => if c.idx > b.idx then some c else best) (none : Option Cycle)

def cur (s : Snapshot) : Cycle :=
  -- Ties are broken by the declared index, never by list position. There should
  -- never be a tie: a law running two cycles at once is exactly what 5.4 needs
  -- a second process type for.
  match highestByIdx (ongoing s) with
  | some c => c
  | none =>
    -- Every instance has finished. Fall back to the highest declared index,
    -- still not to position, so a fully historical graph reads the same way
    -- however its triples arrived.
    match highestByIdx s.cycles with
    | some c => c
    | none => Cycle.mk "" [] [] [] [] false false false false none
        none none none none 0 true

def curIdx (s : Snapshot) : Nat :=
  (cur s).idx

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
  decide (s.day = announceK (curIdx s) ∧ (cur s).announced = false)
def AnnounceDue (s : Snapshot) : Prop :=
  s.day = announceK (curIdx s) ∧ (cur s).announced = false
theorem announceDue_agrees (s : Snapshot) :
    announceDue? s = true ↔ AnnounceDue s := by
  simp [announceDue?, AnnounceDue]

def nominateOpen? (s : Snapshot) : Bool :=
  decide (announceK (curIdx s) ≤ s.day ∧ s.day < prepareK (curIdx s))
def NominateOpen (s : Snapshot) : Prop :=
  announceK (curIdx s) ≤ s.day ∧ s.day < prepareK (curIdx s)
theorem nominateOpen_agrees (s : Snapshot) :
    nominateOpen? s = true ↔ NominateOpen s := by
  simp [nominateOpen?, NominateOpen]

def prepareDue? (s : Snapshot) : Bool :=
  decide (s.day = prepareK (curIdx s) ∧ (cur s).prepared = false)
def PrepareDue (s : Snapshot) : Prop :=
  s.day = prepareK (curIdx s) ∧ (cur s).prepared = false
theorem prepareDue_agrees (s : Snapshot) :
    prepareDue? s = true ↔ PrepareDue s := by
  simp [prepareDue?, PrepareDue]

/-- Papers may go into mailboxes from the moment they are written until the
    polls open. `prepared = true` means the making act ran on the prepare day,
    and the clock only moves forward, so no lower bound is needed -- and the
    upper bound is the law's own: the papers must be there before anyone votes,
    which is 9am on election day (law.txt:15). -/
def deliverDue? (s : Snapshot) : Bool :=
  decide ((cur s).prepared = true ∧
    (s.day < electionDayK (curIdx s) ∨
      (s.day = electionDayK (curIdx s) ∧ s.hour < pollOpenHour)))
def DeliverDue (s : Snapshot) : Prop :=
  (cur s).prepared = true ∧
    (s.day < electionDayK (curIdx s) ∨
      (s.day = electionDayK (curIdx s) ∧ s.hour < pollOpenHour))
theorem deliverDue_agrees (s : Snapshot) :
    deliverDue? s = true ↔ DeliverDue s := by
  simp [deliverDue?, DeliverDue]

/-- Polls are open during the polling window AND while the box is still full.

    Once the authority has counted, the box has been opened and emptied, so the
    period is closed whatever the clock says. Without this the clock's monotonic
    floor was not enough on its own: a cycle's Chronoid carries one start and
    one finish, so the moment the polls closed is recorded by neither, and
    rewinding the clock to inside the polling window offered `vote` again and
    admitted a ballot into an election already counted. The flag is what records
    that the period closed. -/
def pollsOpen? (s : Snapshot) : Bool :=
  !(cur s).counted &&
  decide (s.day = electionDayK (curIdx s) ∧ pollOpenHour ≤ s.hour ∧ s.hour < pollCloseHour)
def PollsOpen (s : Snapshot) : Prop :=
  ¬ (cur s).counted ∧
  s.day = electionDayK (curIdx s) ∧ pollOpenHour ≤ s.hour ∧ s.hour < pollCloseHour
theorem pollsOpen_agrees (s : Snapshot) :
    pollsOpen? s = true ↔ PollsOpen s := by
  simp [pollsOpen?, PollsOpen]

def pollsClosed? (s : Snapshot) : Bool :=
  decide (s.day > electionDayK (curIdx s) ∨ (s.day = electionDayK (curIdx s) ∧ pollCloseHour ≤ s.hour))
def PollsClosed (s : Snapshot) : Prop :=
  s.day > electionDayK (curIdx s) ∨ (s.day = electionDayK (curIdx s) ∧ pollCloseHour ≤ s.hour)
theorem pollsClosed_agrees (s : Snapshot) :
    pollsClosed? s = true ↔ PollsClosed s := by
  simp [pollsClosed?, PollsClosed]

def countDue? (s : Snapshot) : Bool :=
  decide ((s.day > electionDayK (curIdx s) ∨ (s.day = electionDayK (curIdx s) ∧ pollCloseHour ≤ s.hour)) ∧
    (cur s).counted = false)
def CountDue (s : Snapshot) : Prop :=
  (s.day > electionDayK (curIdx s) ∨ (s.day = electionDayK (curIdx s) ∧ pollCloseHour ≤ s.hour)) ∧
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

/-- The ballot one citizen should have for one candidate, if it was made at all.

    A shortfall has two shapes that a consumer must be able to tell apart: never
    made, or made and not yet carried. `none` says the first, and the Role's IRI
    says the second -- which individual is sitting in a drawer or a pocket
    undelivered, as opposed to a piece of paper that does not exist. -/
def ballotFor (s : Snapshot) (owner cand : String) : Option Ballot :=
  (cur s).ballots.find? (fun b => b.owner == owner && b.candidate == cand)

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
  Cycle.mk (cycleIri k) [] [] [] [] false false false false none
    none none none none k false

/-! Uniform oracle interface. -/

def ecaIds : List String :=
  ["announce", "nominate", "prepare", "deliver", "vote", "count", "proclaim", "repeat"]

/-- Citizens whose papers are still not in a mailbox. Sorted and deduplicated
    because "each citizen" is what delivery iterates over: one entry per citizen
    with something outstanding, however many of their ballots that is. -/
def awaitingDelivery (s : Snapshot) : List String :=
  ((cur s).ballots.filterMap fun b =>
    if b.delivered then none else some b.owner).mergeSort (fun a b => a < b) |>.eraseDups

/-- Which ECAs' conditions currently hold.

    Each entry calls the SAME guard `apply` enforces, rather than restating the
    condition. Restating it let the two drift: `fired` kept listing `announce`
    on the day it had already been announced, `count` after the votes were
    counted, and `proclaim` after the winner was proclaimed -- each one while
    `apply` refused it by name. `fired` is what a consumer reads to show what is
    happening, so advertising an act the oracle will reject is worse than
    advertising nothing: it offers a button that cannot work. -/
def firedOf (s : Snapshot) : List String :=
  (if announceDue? s then ["announce"] else []) ++
  (if nominateOpen? s then ["nominate"] else []) ++
  (if prepareDue? s then ["prepare"] else []) ++
  (if deliverDue? s && !(awaitingDelivery s).isEmpty then ["deliver"] else []) ++
  (if pollsOpen? s then ["vote"] else []) ++
  (if countDue? s then ["count"] else []) ++
  (if proclaimDue? s then ["proclaim"] else []) ++
  (if voidCycle? s then ["repeat"] else [])

def pendingOf (s : Snapshot) : List PendingEntry :=
  let authPending : List PendingEntry := match authorityId s with
    | none => []
    | some a =>
      (if announceDue? s then [{ citizen := a, eca := "announce", process := (cur s).id, choices := [] }] else []) ++
      (if prepareDue? s then [{ citizen := a, eca := "prepare", process := (cur s).id, choices := [] }] else []) ++
      -- One duty, offered once, with the recipients as its choices: the holder
      -- is the authority throughout, and "each citizen" is what it iterates.
      (if deliverDue? s && !(awaitingDelivery s).isEmpty then
        [{ citizen := a, eca := "deliver", process := (cur s).id,
           choices := [("recipient", awaitingDelivery s)] }]
       else []) ++
      (if countDue? s then [{ citizen := a, eca := "count", process := (cur s).id, choices := [] }] else []) ++
      (if proclaimDue? s then [{ citizen := a, eca := "proclaim", process := (cur s).id, choices := [] }] else []) ++
      (if voidCycle? s then [{ citizen := a, eca := "repeat", process := (cur s).id, choices := [] }] else [])
  let nominees : List PendingEntry :=
    if nominateOpen? s then
      (s.citizens.filter (fun c => !((cur s).registry.any (· == c.id)))).map
        (fun c => { citizen := c.id, eca := "nominate", process := (cur s).id, choices := [] })
    else []
  let voters : List PendingEntry :=
    if pollsOpen? s then
      (s.citizens.filter (fun c => decide (!(voted? s c.id)))).map
        (fun c => { citizen := c.id, eca := "vote", process := (cur s).id,
                       choices := [("candidate", (cur s).candidates)] })
    else []
  authPending ++ nominees ++ voters

/-- Citizens who did not vote: the individuals a failed quorum is about. The
    counts say how far short it fell; these say who made it short. -/
def absentees (s : Snapshot) : List String :=
  -- Sorted because `citizensOf` is, so the witness is stable across round-trips
  -- rather than following the order the triples arrived in.
  s.citizens.filterMap fun c => if voted? s c.id then none else some c.id

def violationsOf (s : Snapshot) : List Violation :=
  let dist : List Violation := match firstMissing? s with
    | none => []
    | some (c, cand) =>
      if decide (prepareK (curIdx s) ≤ s.day) then
        -- The citizen first, because that is what the duty is owed to and what a
        -- consumer acts on. Then the candidate whose ballot is missing. Then the
        -- ballot ITSELF where one was made: that is the difference between
        -- "Alice never got a ballot for Cara" and "Alice's ballot for Cara was
        -- written and never carried", and only the second names an individual a
        -- reader can go and look at.
        let refs := match ballotFor s c cand with
          | some b => [c, cand, iriBallotIn (cur s).id b.sheet]
          | none => [c, cand]
        [{ eca := "all_distributed", witness := Witness.ofRefs refs,
           detail := match ballotFor s c cand with
             | some _ => "ballot written but not delivered"
             | none => "ballot missing" }]
      else []
  let dupes : List Violation := (doubleVoters s).map (fun v =>
    { eca := "single_vote", witness := Witness.ofRefs [v],
      detail := "citizen voted twice" })
  let quorum : List Violation :=
    if voidCycle? s then
      [{ eca := "quorum"
         , witness := Witness.withCounts (absentees s)
             [("voted", (votersOf s).length), ("total", s.citizens.length)]
         , detail := s!"quorum failed: {(votersOf s).length} voted of {s.citizens.length}, repeat on day {electionDayK ((curIdx s) + 1)}" }]
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
  | deliver (recipient : String)
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
    | "deliver" =>
      Act.deliver <$> (j.getObjVal? "recipient" >>= FromJson.fromJson? (α := String))
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
    if announceDue? s then
      .ok (updateCur s (fun c => ({ c with announced := true }).stampStartAt s.day s.hour))
    else .error "announce not due"

def applyNominate (s : Snapshot) (c : String) : Except String Snapshot :=
  if !nominateOpen? s then .error "registry closed"
  else if (cur s).registry.any (· == c) then .error "already registered"
  else .ok (updateCur s (fun cy => { cy with registry := c :: cy.registry }))

/-! Making the ballots.

    law.txt:11-12 requires "one paper per candidate for each citizen". That
    count is fixed by the registry AT PREPARATION TIME, which is not knowable
    when the world is seeded -- so the paper is not minted here. The seed
    supplies blank sheets, what this hamlet has in the drawer, and this act
    writes on them.

    Nothing is conjured: a paper that the drawer does not hold is a refusal
    naming the shortfall, not a silent shortfall. -/

/-- One citizen's ballots: one paper per candidate, each on a sheet of their
    own. `none` when their supply is short of the registry.

    The pairing is positional within ONE citizen's sheets, which is stable
    because both the sheet list and the candidate list are canonically ordered.
    -/
def ballotsFor (s : Snapshot) (c : Citizen) : Option (List Ballot) :=
  let mine := sheetsFor s c.id
  let cands := (cur s).candidates
  if cands.length > mine.length then none
  else some ((mine.zip cands).map (fun (sheet, cand) =>
    Ballot.mk sheet c.id cand false))

/-- Every citizen's ballots, or `none` if ANY citizen's supply is short --
    a shortfall is reported, never absorbed. -/
def writtenBallots (s : Snapshot) : Option (List Ballot) :=
  let parts := s.citizens.map (ballotsFor s ·)
  if parts.any (·.isNone) then none
  else some (parts.filterMap id).flatten

/-- Who is short of paper, and by how much. The refusal names the citizen rather
    than a total, because "the drawer is short" is not something anyone can act
    on and "Cara has two sheets for five candidates" is. -/
def shortfallOf (s : Snapshot) : Option (String × Nat × Nat) :=
  (s.citizens.find? (fun c => (ballotsFor s c).isNone)).map fun c =>
    (c.id, (sheetsFor s c.id).length, (cur s).candidates.length)

def applyPrepare (s : Snapshot) : Except String Snapshot :=
  match authorityId s with
  | none => .error "no authority in office"
  | some _ =>
    if !prepareDue? s then .error "prepare not due"
    else if s.instruments.isEmpty then
      -- The duty is qualified by CAPABILITY, not by a named kind of thing, so
      -- the message names the qualification rather than an instrument.
      .error "nothing in the hamlet is qualified to inscribe, so no ballot can be written"
    else
      match writtenBallots s with
      | none =>
        match shortfallOf s with
        | some (who, held, need) =>
          .error s!"prepare needs one sheet per candidate for each citizen, and \
            {shortId who} has {held} for {need} candidates -- the paper is short"
        | none => .error "prepare cannot pair every citizen with a sheet"
      | some bals =>
        let cy := ({ cur s with prepared := true }).stampStartAt s.day s.hour
        .ok (updateCur s (fun _ => { cy with ballots := bals }))

/-! Putting the ballots in the mailboxes.

    One act, one recipient. law.txt:11-12 gives the authority ONE duty -- "they
    must put these papers in the mailbox of each citizen" -- and "each citizen"
    is what it iterates over, so iterating here keeps the duty the authority's
    while making a partial delivery a state that exists: with one act per
    recipient, some citizens' mailboxes are filled and others' are not, and
    `allDistributed` reports that with the undelivered citizen as the witness.
    A single bulk act could never produce that state. -/

def applyDeliver (s : Snapshot) (recipient : String) : Except String Snapshot :=
  if !deliverDue? s then .error "papers cannot go into mailboxes yet: nothing has been made, or the polls are open"
  else
    let mine := (cur s).ballots.filter (fun b => b.owner == recipient)
    if mine.isEmpty then
      .error s!"no papers were made out for {shortId recipient}"
    else if !((s.mailboxes.map (·.owner)).contains recipient) then
      -- law.txt:12 says each citizen has a mailbox. Where the seed does not
      -- supply one, the honest answer is that the duty has no object to act on.
      .error s!"no mailbox is seeded for {shortId recipient}"
    else if mine.all (·.delivered) then
      .error s!"{shortId recipient}'s papers are already in their mailbox"
    else
      let cy := updateCur s (fun c =>
        { c with ballots := c.ballots.map (fun b =>
            if b.owner == recipient then { b with delivered := true } else b) })
      .ok cy

def applyVote (s : Snapshot) (v c : String) : Except String Snapshot :=
  if !pollsOpen? s then .error "polls closed"
  else if voted? s v then .error "citizen already voted"
  else if s.ballotBoxes.isEmpty then
    -- law.txt:13 requires a big closed box standing in the townhall. This is the
    -- one individual this law declares an act as acting on: it is named, seeded,
    -- and a vote has nowhere to go without it. So the act refuses naming it
    -- rather than recording a vote that reached nothing -- which would let the
    -- quorum be counted from ballots no one ever put anywhere.
    .error "there is no ballot box in the hamlet, so a vote has nowhere to go"
  else .ok (updateCur s (fun cy => { cy with box := Vote.mk v c :: cy.box }))

def applyCount (s : Snapshot) : Except String Snapshot :=
  if countDue? s then .ok (updateCur s (fun c => ({ c with counted := true }).stampStartAt s.day s.hour))
  else .error "count not due"

def applyProclaim (s : Snapshot) : Except String Snapshot :=
  match winner? s with
  | none => .error "no candidates"
  | some w =>
    if proclaimDue? s then
      let sPrime := updateCur s (fun c =>
          (({ c with proclaimed := true, outcome := some "valid" }).stampStartAt s.day s.hour).stampFinishAt s.day s.hour)
      .ok { sPrime with mayorId := some w }
    else .error "proclaim not due"

/-- Guarded quorum repeat: appends a fresh successor cycle only when the
    current one actually failed quorum at polls-close after counting.
    The void cycle is marked and preserved in history. -/
def repeatAfterVoid (s : Snapshot) : Except String Snapshot :=
  if voidCycle? s then
    let k := curIdx s
    let marked := updateCur s (fun c => ({ c with outcome := some "void" }).stampFinishAt s.day s.hour)
    .ok { marked with cycles := marked.cycles ++ [freshCycle (k + 1)] }
  else .error "quorum not failed"

def apply : Act → Snapshot → Except String Snapshot
  | .announce, s => applyAnnounce s
  | .nominate c, s => applyNominate s c
  | .prepare, s => applyPrepare s
  | .deliver r, s => applyDeliver s r
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
    let g1 := Graph.setOne g which rdfType (.iri gfoTimeBoundary)
    let g2 := Graph.setOne g1 which (ph "dayIndex") (TripleObj.lit (toString d) "integer")
    Graph.setOne g2 which (ph "atHour") (TripleObj.lit (toString h) "integer")
  -- The bound carries the moment the transition HAPPENED, not the cycle's
  -- current position, which keeps moving for the rest of the law's run.
  -- A bound individual is written only when the moment EXISTS. Writing a
  -- placeholder day for a bound nothing points at would put a `ph:dayIndex`
  -- in the graph that names a moment no act ever recorded.
  let boundAt (g : Graph) (which : String) (m : Option (Nat × Nat)) : Graph :=
    match m with
    | some (d, h) => timeBoundary g which d h
    | none => g
  let withBoundaries : Graph :=
    boundAt (boundAt withOutcome boundStart c.startMoment) boundFinish c.finishMoment
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
    -- No `ph:dayIndex` on the span: its start is already named by the
    -- `temporallyStartedBy` bound below, which points at the minted announce
    -- point carrying that same day. A second copy of a position on a `Chronoid`
    -- is exactly what the `ph:dayIndex` domain now forbids, and the span's
    -- length is already carried as `ph:gapDays`.
    let s3 := Graph.setOne s2 window (ph "gapDays")
      (TripleObj.lit (toString (ek - ak)) "integer")
    let s4 := s3
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
  let cands := c.candidates.filterMap fun cd =>
    let r := iriRole "candidate" ++ "/" ++ shortId c.id ++ "/" ++ shortId cd
    if (g.iriOf? r rdfType).isSome then none else some (r, cd)
  let noms := c.registry.filterMap fun cd =>
    let n := iriNominationIn c.id cd
    if (g.iriOf? n rdfType).isSome then none else some (n, cd)
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
    -- `roleTriples'` does -- each gets its own, scoped to the cycle. It carries
    -- ph:cycleIndex so candidatesIn can find it, and ph:roleIn points at the
    -- election, the context, as it does everywhere else.
    let role := iriRole "candidate" ++ "/" ++ shortId c.id ++ "/" ++ shortId cd
    a ++ [ { subject := n, predicate := rdfType, object := .iri (ph "SelfNomination") }
         , { subject := n, predicate := ph "hasParticipant", object := .iri cd }
         , { subject := n, predicate := ph "cycleIndex", object := .iri c.id } ]
      ++ (roleTriplesAt role (ph "CandidateRole") c.id cd)
      ++ [ { subject := role, predicate := ph "cycleIndex", object := .iri c.id } ]) withCands
  -- One ballot is ONE act and TWO facts:
  --
  --   * the candidate's name, written ON THE SHEET as its `ph:label`. Writing is
  --     not the creation of a thing -- a mark on paper the hamlet already had is
  --     a literal, not an individual, so nothing physical is conjured and the
  --     spec's closed list of what the oracle may mint (a meaning, an occurrence,
  --     a process instance, a calendar node, a bound) needs no sixth entry.
  --     `setOne` makes re-writing the same sheet a no-op, which is the IRI
  --     freshness requirement's purpose reached the only way it can be here:
  --     there is no new IRI to collide.
  --   * a Role individual PLAYED BY the sheet, in this election, denoting the
  --     candidate citizen. THAT is the minted individual, and it is a meaning,
  --     which the list already permits.
  --
  -- The Role carries exactly ONE holder, the sheet. The owner is NOT a second
  -- role on it: the sheet's own `ph:ownedBy` says whose papers it is, so one
  -- place in the graph answers "whose ballot is this" rather than two.
  --
  -- Writing and taking the role are not separate steps because law.txt does not
  -- make them separate steps: it says the authority must make the ballot votes
  -- and states no moment between the writing and the ballot's existence.
  let withBals := (c.ballots).foldl (fun a b =>
    let bi := iriBallotIn c.id b.sheet
    let written := (Graph.litOf? a b.candidate (ph "label")).getD ""
    -- The MARKING is on the sheet, and it is re-done on every apply: a sheet is a
    -- reusable physical object, so a later election strikes the old name and
    -- writes a new one on the same paper. `setOne` replaces, so the sheet holds
    -- one marking at a time rather than accumulating every name ever put on it --
    -- and that is the whole of what is recorded about the writing. Which name
    -- each earlier election's ballot carried is not lost, because it was never on
    -- the paper to begin with: it is what the Role of that election denotes.
    let a1 := Graph.setOne a b.sheet (ph "label") (.lit written "string")
    -- The ROLE is the only minted individual here, and it is minted once: its IRI
    -- is a function of the occurrence and the sheet, so a later apply finds it
    -- already there and leaves it alone. Roles are additive; the marking above is
    -- an update, which is why it is not behind this test.
    let a2 := if (Graph.iriOf? a1 bi rdfType).isSome then a1
      else a1 ++ (roleTriplesAt bi (ph "BallotVote") c.id b.sheet)
        ++ [ { subject := bi, predicate := ph "cycleIndex", object := .iri c.id }
           , { subject := bi, predicate := ph "denotes", object := .iri b.candidate } ]
    -- DELIVERY belongs to the Role, so it is scoped to the election that carried
    -- it. Recorded once, and never removed -- taking a paper back out would be an
    -- erasure the gate forbids, and a Role's delivery is a thing that happened.
    match if b.delivered then mailboxOf a2 b.owner else none with
    | some mailbox =>
      if (Graph.iriOf? a2 bi (ph "deliveredTo")).isSome then a2
      else a2 ++ [ { subject := bi, predicate := ph "deliveredTo",
                     object := .iri mailbox } ]
    | none => a2) withNoms
  -- A CAST VOTE is a `ph:Deposit` -- the shared act of putting a thing into a
  -- container -- so where the ballot went is recorded with the shared
  -- `ph:placedIn`, on the SHEET, because that is the physical fact: the paper is
  -- in the box. (Contrast a ballot's DELIVERY to a mailbox, which is contextual
  -- and lives on the Role: the same sheet serves every election, while the box
  -- is emptied and reused, so what is in the box is always about the vote just
  -- cast rather than about the paper's history.)
  --
  -- The sheet is the citizen's own ballot for that candidate where they have one.
  -- A citizen who was never issued a paper has cast a vote all the same -- the law
  -- does not make receiving a ballot a precondition of voting -- so there is
  -- nothing to place and only the `CastVote` occurrence is recorded.
  let boxes := boxesOf g
  vts.foldl (fun a (vi, v) =>
    let a1 := a ++ [ { subject := vi, predicate := rdfType, object := .iri (ph "CastVote") }
                   , { subject := vi, predicate := ph "cycleIndex", object := .iri c.id } ]
      ++ (roleTriples' (ph "VoterRole") vi v.voter)
      ++ (roleTriples' (ph "CandidateRole") vi v.candidate)
    match (c.ballots.find? (fun b => b.owner == v.voter && b.candidate == v.candidate)) with
    | some b => match boxes.head? with
      | some box =>
        if (a1.filter fun t =>
              t.subject == b.sheet && t.predicate == ph "placedIn"
              && t.object == .iri box).isEmpty
        then a1 ++ [ { subject := b.sheet, predicate := ph "placedIn", object := .iri box } ]
        else a1
      | none => a1
    | none => a1) withBals

def writeBack (g : Graph) (s : Snapshot) : Graph :=
  -- `ph:Clock` is NOT written here, not even echoed. The runtime owns the
  -- world's inputs: it advances time, and it alone may bring a physical thing
  -- into being. The oracle owns only interpretation -- what the state means,
  -- which duties are due, which Role an individual holds -- and time is not an
  -- interpretation.
  --
  -- The floor in `clockOf` is the right kind of answer to a rewound clock: the
  -- oracle refuses to ACT as though time were earlier than a moment already
  -- recorded, and leaves the runtime's value exactly as it found it. Writing
  -- the floored value back -- as this law did -- made the oracle a second
  -- writer on the one individual with a single writer, and on a repeat it
  -- returned the successor's hour 0, erasing the hour the runtime had set.
  let base := g
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
