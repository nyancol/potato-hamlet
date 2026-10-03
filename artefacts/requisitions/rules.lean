-- Potato Hamlet -- purchase requisitions.
--
-- The law exists to exercise what the two mayor laws structurally cannot: a
-- PROCESS TYPE WITH SEVERAL ONGOING INSTANCES AT ONCE, and an instance that
-- ends at a moment which is not a declared calendar point.
--
--   * Requisitions are per-occurrence entities. Any number are open at the same
--     time, each with its own Chronoid and outcome, and one being decided has
--     no bearing on any other.
--   * Settling happens at the deadline, which IS a declared CalendarPoint.
--     Withdrawal may happen at any time before a decision, so it commonly ends
--     a requisition part-way through the window span instead. Both endings must
--     record their finish bound the same way, with no extra vocabulary.
--
-- The knowledge graph is the snapshot: this file derives its own state from
-- instance triples and mints everything back out. There is no second state
-- object to keep in step with the graph.
import Lean.Data.Json

open Lean

/-! ## Wire format

    `Graph` is a flat list of triples. An IRI is a bare JSON string and a
    literal is `{"lit": ..., "type": ...}`. The list is UNORDERED: nothing here
    depends on the order triples arrive in, so every enumeration below is
    sorted to keep the verdict stable across round-trips. -/

inductive TripleObj where
  | iri (v : String)
  | lit (v : String) (ty : String)
deriving Repr, DecidableEq

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
    | .iri v => toJson v
    | .lit v ty => Json.mkObj [("lit", toJson v), ("type", toJson ty)]

structure Triple where
  subject : String
  predicate : String
  object : TripleObj
deriving Repr, DecidableEq

instance : FromJson Triple where
  fromJson? j := do
    -- A triple crosses the wire as a 3-element ARRAY, so it has to be read as
    -- one. Reading it with `getObjVal? "0"` looks like it works and does not:
    -- that asks for a field named "0" on a value that has none.
    let arr ← j.getArr?
    let t ← if arr.size = 3 then
      (do
        let s ← arr[0]!.getStr?
        let pr ← arr[1]!.getStr?
        let o ← FromJson.fromJson? (α := TripleObj) arr[2]!
        pure { subject := s, predicate := pr, object := o })
    else
      Except.error "triple must be a 3-element array"
    return t

instance : ToJson Triple where
  toJson t := Json.arr #[toJson t.subject, toJson t.predicate, toJson t.object]

abbrev Graph := List Triple

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

def rdfType : String := "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
def gfoStarted : String := "https://w3id.org/gfo-core/temporallyStartedBy"
def gfoFinished : String := "https://w3id.org/gfo-core/temporallyFinishedBy"
def gfoChronoid : String := "https://w3id.org/gfo-light/Chronoid"
def gfoTimeBoundary : String := "https://w3id.org/gfo-light/TimeBoundary"

def iriHamlet : String := ph "hamlet"
def iriGoods : String := ph "goods/seed"
def iriOfficer : String := ph "role/officer#OfficerRole"
def iriStateOpen : String := ph "state/open"
def iriStateLate : String := ph "state/late"
def iriStateClosed : String := ph "state/closed"

def stateIriOf (status : String) : String :=
  match status with
  | "approved" => ph "state/approved"
  | "refused" => ph "state/refused"
  | "withdrawn" => ph "state/withdrawn"
  | _ => iriStateOpen

/-- A stable short name from the last path segment of an IRI. -/
def shortId (iri : String) : String :=
  match (iri.splitOn "/").getLast? with
  | some s => s
  | none => iri

namespace Graph

def typedOf (g : Graph) (cls : String) : List String :=
  ((g.filter fun t => t.predicate == rdfType).filterMap fun t =>
    match t.object with
    | .iri v => if v == cls then some t.subject else none
    | .lit _ _ => none).eraseDups

def iriOf? (g : Graph) (subject predicate : String) : Option String :=
  ((g.filter fun t => t.subject == subject && t.predicate == predicate).filterMap
    (fun t => match t.object with | .iri v => some v | .lit _ _ => none)).head?

def litOf? (g : Graph) (subject predicate : String) : Option String :=
  ((g.filter fun t => t.subject == subject && t.predicate == predicate).filterMap
    (fun t => match t.object with | .lit v _ => some v | .iri _ => none)).head?

def natOf (g : Graph) (subject predicate : String) : Nat :=
  match litOf? g subject predicate with
  | some v => (v.toNat?).getD 0
  | none => 0

def flagOn (g : Graph) (subject : String) (predicate : String) : Bool :=
  match litOf? g subject predicate with
  | some "true" => true
  | _ => false

/-- Replace-or-add: one value per (subject, predicate). Appending would leave a
    stale value beside the new one on every write, and a reader would get
    whichever it happened to see. -/
def setOne (g : Graph) (subject predicate : String) (object : TripleObj) : Graph :=
  (g.filter fun t => !(t.subject == subject && t.predicate == predicate)) ++
    [{ subject := subject, predicate := predicate, object := object }]

/-- The citizen playing `roleClass` in the situation `ctx`, if any. -/
def participantVia? (g : Graph) (ctx roleClass : String) : Option String :=
  ((g.filter fun t => t.predicate == rdfType && t.object == .iri roleClass).filterMap
    fun t => if iriOf? g t.subject (ph "roleIn") == some ctx
              then iriOf? g t.subject (ph "playedBy") else none).head?

/-- Has this instance finished? Declared, not positional: a historical instance
    is one whose Chronoid carries a finish bound. -/
def finishedIn (g : Graph) (inst : String) : Bool :=
  match iriOf? g inst (ph "hasTime") with
  | some ch => (iriOf? g ch gfoFinished).isSome
  | none => true

def hasType (g : Graph) (subject cls : String) : Bool :=
  (g.any fun t => t.subject == subject && t.predicate == rdfType && t.object == .iri cls)

end Graph

/-- A Role individual playing `roleClass` for `citizen` in `ctx`.

    `roleIn` always names the CONTEXT, because that is what the ontology
    declares it to mean; the subject is passed in because one citizen may hold
    the same role in several situations at once. -/
def roleTriplesAt (subj roleClass ctx citizen : String) : List Triple :=
  [ { subject := subj, predicate := rdfType, object := .iri roleClass }
  , { subject := subj, predicate := ph "roleIn", object := .iri ctx }
  , { subject := subj, predicate := ph "playedBy", object := .iri citizen } ]

def boolLit (b : Bool) : TripleObj := TripleObj.lit (if b then "true" else "false") "boolean"
def natLit (n : Nat) : TripleObj := TripleObj.lit (toString n) "integer"

/-! ## The population

    Every citizen carries `ph:age`, which the framework requires and this law
    needs anyway: clause 7 makes the Officer the OLDEST citizen who is not
    themselves a requisitioner, so the choice is real arithmetic rather than a
    lookup. -/

structure Citizen where
  id : String
  age : Nat
deriving Repr, DecidableEq

def citizensOf (g : Graph) : List Citizen :=
  let found := (Graph.typedOf g (ph "Citizen")).map
    fun c => Citizen.mk c (Graph.natOf g c (ph "age"))
  found.mergeSort (fun a b => a.id < b.id)

def ageOf (g : Graph) (citizen : String) : Nat :=
  (citizensOf g).find? (fun c => c.id == citizen) |>.map (·.age) |>.getD 0

/-! ## A requisition

    A per-occurrence entity, not a moment on a shared timeline: it is bounded
    by its OWN Chronoid, not by the calendar, which is why no calendar node
    marks `ph:Requisition` itself. The window marks it so that "this instance
    ended inside one of its calendar spans" is readable from the graph. -/

structure Req where
  id : String
  day : Nat
  hour : Nat
  requester : String
  sum : Nat
  goods : String
  status : String
  outcome : Option String
  late : Bool
  startDay : Option Nat
  startHour : Option Nat
  finishDay : Option Nat
  finishHour : Option Nat
  decidedBy : Option String
deriving Repr, DecidableEq

/-- Deterministic from (case, citizen, occurrence).

    NOT from the citizen alone: a citizen may withdraw a requisition and lodge
    another, and the two are separate occurrences with separate outcomes. Keying
    on the citizen alone made the second one collide with the first, so
    withdrawing and re-lodging silently overwrote a finished requisition -- the
    graph gained a start bound on an instance that already had a finish bound,
    and no withdrawal was ever recorded. -/
def reqIri (citizen : String) (k : Nat) : String :=
  ph ("requisition/" ++ shortId citizen ++ "-" ++ toString k)
def chronoIri (req : String) : String := ph "chronoid/requisition/" ++ shortId req

def Req.startDayOf (r : Req) : Nat :=
  match r.startDay with
  | some d => d
  | none => r.day

def Req.startHourOf (r : Req) : Nat :=
  match r.startHour with
  | some h => h
  | none => r.hour

def Req.finishDayOf (r : Req) : Nat :=
  match r.finishDay with
  | some d => d
  | none => r.day

def Req.finishHourOf (r : Req) : Nat :=
  match r.finishHour with
  | some h => h
  | none => r.hour

def Req.stampStart (r : Req) : Req :=
  { r with startDay := some r.startDayOf, startHour := some r.startHourOf }

def Req.stampStartAt (r : Req) (day hour : Nat) : Req :=
  { r with startDay := some (match r.startDay with | some _ => r.startDayOf | none => day)
          , startHour := some (match r.startHour with | some _ => r.startHourOf | none => hour) }

/-- Stamped at the CURRENT moment, not at the requisition's stored day. This is
    what lets a withdrawal end a requisition part-way through the window rather
    than on the deadline: the moment it happened is the one recorded. -/
def Req.stampFinishAt (r : Req) (day hour : Nat) : Req :=
  { r with finishDay := some (match r.finishDay with | some _ => r.finishDayOf | none => day)
          , finishHour := some (match r.finishHour with | some _ => r.finishHourOf | none => hour) }

def isOpen (r : Req) : Bool := r.status == "open"

/-- Named day arithmetic. The window opens on day 0 and closes on day 30; the
    settling deadline is day 14, and it is a POINT lying inside the window. -/
def windowOpens : Nat := 0
def windowCloses : Nat := 30
def deadlineDay : Nat := 14
def deadlineHour : Nat := 18

def announceDay : Nat := windowOpens
def settleDueDay : Nat := deadlineDay

def WindowOpen (day : Nat) : Prop := day < windowCloses
def PastDeadline (day : Nat) : Prop := deadlineDay ≤ day

-- `decide (WindowOpen day)` would not elaborate: instance resolution does not
-- unfold a user-defined Prop to see `Nat.lt` underneath it, so it cannot find a
-- `Decidable` instance. The comparison is therefore written out here, and the
-- `Prop` twins above are what the theorems below are stated against.
def windowOpen? (day : Nat) : Bool := decide (day < windowCloses)
def pastDeadline? (day : Nat) : Bool := decide (deadlineDay ≤ day)

/-- The (day, hour) a Chronoid bound denotes, if the instance has that bound. -/
def boundMoment? (g : Graph) (inst which : String) : Option Nat :=
  match Graph.iriOf? g inst (ph "hasTime") with
  | some ch =>
    match Graph.iriOf? g ch which with
    | some b => some (Graph.natOf g b (ph "dayIndex"))
    | none => none
  | none => none

def reqOf (g : Graph) (req : String) : Req :=
  { id := req
    day := Graph.natOf g req (ph "dayIndex")
    hour := Graph.natOf g req (ph "atHour")
    requester := (Graph.participantVia? g req (ph "RequisitionerRole")).getD ""
    sum := Graph.natOf g req (ph "sum")
    goods := (Graph.iriOf? g req (ph "goods")).getD iriGoods
    status := (Graph.litOf? g req (ph "status")).getD "open"
    outcome := Graph.litOf? g req (ph "outcome")
    late := Graph.flagOn g req (ph "late")
    startDay := boundMoment? g req gfoStarted
    startHour := none
    finishDay := boundMoment? g req gfoFinished
    finishHour := none
    decidedBy := Graph.iriOf? g req (ph "decidedBy") }

/-- Every requisition, in a canonical order. Sorted because a wire round-trip
    carries no array order and everything downstream observes this list. -/
def reqsOf (g : Graph) : List Req :=
  let found := (Graph.typedOf g (ph "Requisition")).map (reqOf g)
  found.mergeSort (fun a b => a.id < b.id)

def openReqs (g : Graph) : List Req :=
  (reqsOf g).filter isOpen

def openReqIris (g : Graph) : List String :=
  (openReqs g).map (·.id)

def holdsOpen (g : Graph) (citizen : String) : Bool :=
  (openReqs g).any (fun r => r.requester == citizen)

def openOf (g : Graph) (citizen : String) : Option Req :=
  (openReqs g).find? (fun r => r.requester == citizen)

/-! ## The Officer

    Clause 7: the oldest citizen who is not themselves a requisitioner, and
    the post is vacant if every citizen holds an open requisition. No framework
    rule decides this -- it is this law's rule, and a consumer reads the holder
    out of `pending` rather than computing it. -/

def eligibleOfficers (g : Graph) : List Citizen :=
  (citizensOf g).filter (fun c => !(holdsOpen g c.id))

def officerId? (g : Graph) : Option String :=
  (eligibleOfficers g).foldl (fun best c =>
    match best with
    | none => some c
    | some b => if c.age > b.age then some c else best) (none : Option Citizen)
  |>.map (·.id)

/-! ## Snapshot

    Closed world: the full finite population plus every requisition instance.
    Both are derived from the graph, so there is nothing to keep in step. -/

structure Snapshot where
  day : Nat
  hour : Nat
  citizens : List Citizen
  reqs : List Req
  officerId : Option String
  -- The standing schedule: what a requisition is for, and at what price. Read
  -- from the graph rather than hardcoded, so the law text stays the source.
  scheduleSum : Nat
deriving Repr, DecidableEq

def clockOf (g : Graph) : Nat × Nat :=
  (Graph.natOf g (ph "clock/now") (ph "dayIndex"),
   Graph.natOf g (ph "clock/now") (ph "atHour"))

def snapshotOf (g : Graph) : Snapshot :=
  let (d, h) := clockOf g
  { day := d, hour := h
  , citizens := citizensOf g
  , reqs := reqsOf g
  , officerId := officerId? g
  , scheduleSum := Graph.natOf g iriGoods (ph "sum") }

def openReqsOf (s : Snapshot) : List Req := s.reqs.filter isOpen

def holdsOpenIn (s : Snapshot) (citizen : String) : Bool :=
  (openReqsOf s).any (fun r => r.requester == citizen)

def openOfIn (s : Snapshot) (citizen : String) : Option Req :=
  (openReqsOf s).find? (fun r => r.requester == citizen)

def openReqIrisOf (s : Snapshot) : List String := (openReqsOf s).map (·.id)

def reqById (s : Snapshot) (id : String) : Option Req :=
  s.reqs.find? (fun r => r.id == id)

def updateReq (s : Snapshot) (id : String) (f : Req → Req) : Snapshot :=
  { s with reqs := s.reqs.map (fun r => if r.id == id then f r else r) }

/-! ## Conditions

    Each guard is stated twice, as a `Bool` for the executable path and as a
    `Prop` for the statement, with a theorem that they agree. One source of
    truth: `apply` refuses on exactly what `check` reports. -/

/-- Clause 1 and 2: a citizen may lodge while the window is open and holds at
    most one open requisition. -/
def lodgeDue? (s : Snapshot) (citizen : String) : Bool :=
  windowOpen? s.day && !(holdsOpenIn s citizen)

def LodgeDue (s : Snapshot) (citizen : String) : Prop :=
  WindowOpen s.day ∧ ¬ ((openReqsOf s).any (fun r => r.requester == citizen))

theorem lodgeDue_agrees (s : Snapshot) (citizen : String) :
    lodgeDue? s citizen = true ↔ LodgeDue s citizen := by
  simp [lodgeDue?, LodgeDue, windowOpen?, WindowOpen, decide_eq_true_eq,
    Bool.and_eq_true, Bool.not_eq_true, holdsOpenIn, openReqsOf, isOpen,
    List.all_eq_true, List.any_eq_true, and_assoc]

/-- Clause 3: the requester may withdraw while it is undecided. -/
def withdrawDue? (s : Snapshot) (citizen : String) : Bool :=
  (openReqsOf s).any (fun r => r.requester == citizen)

def WithdrawDue (s : Snapshot) (citizen : String) : Prop :=
  ∃ r ∈ openReqsOf s, r.requester = citizen

theorem withdrawDue_agrees (s : Snapshot) (citizen : String) :
    withdrawDue? s citizen = true ↔ WithdrawDue s citizen := by
  simp [withdrawDue?, WithdrawDue, openReqsOf, isOpen, List.any_eq_true, and_assoc]

/-- Clause 4: an open requisition is due a decision, and only while an Officer
    exists to give it. -/
def settleDue? (s : Snapshot) (req : String) : Bool :=
  (openReqsOf s).any (fun r => r.id == req) && s.officerId.isSome

def SettleDue (s : Snapshot) (req : String) : Prop :=
  (∃ r ∈ openReqsOf s, r.id = req) ∧ s.officerId.isSome

theorem settleDue_agrees (s : Snapshot) (req : String) :
    settleDue? s req = true ↔ SettleDue s req := by
  simp [settleDue?, SettleDue, openReqsOf, isOpen, Bool.and_eq_true,
    List.any_eq_true, and_assoc]

/-- The guard that makes a named instance checkable: the requisition must be one
    the law knows about. An act naming anything else is refused BY NAME rather
    than silently doing nothing. -/
def knownReq? (s : Snapshot) (req : String) : Bool :=
  s.reqs.any (fun r => r.id == req)

def KnownReq (s : Snapshot) (req : String) : Prop := ∃ r ∈ s.reqs, r.id = req

theorem knownReq_agrees (s : Snapshot) (req : String) :
    knownReq? s req = true ↔ KnownReq s req := by
  simp [knownReq?, KnownReq, List.any_eq_true]

def decisionValid? (d : String) : Bool :=
  decide (d == "approved" || d == "refused")

def DecisionValid (d : String) : Prop := d = "approved" ∨ d = "refused"

theorem decisionValid_agrees (d : String) :
    decisionValid? d = true ↔ DecisionValid d := by
  simp [decisionValid?, DecisionValid]

/-! ## Verdict

    `readings` replaces a field named for any single process: this law has no
    winner to report, only counts and a reference. A law with no result of a
    shape emits nothing, so absence is how a consumer learns there is none. -/

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

/-! Violation witnesses: `refs` names the individuals that break a quantified
    condition, `counts` the quantities that fell short. Together they cover the
    framework's FOL subset, so no law needs a witness field of its own. -/

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

instance : ToJson Violation where
  toJson v :=
    Json.mkObj [
      ("eca", toJson v.eca),
      ("witness", toJson v.witness),
      ("detail", toJson v.detail)]

/-- One duty owed by one citizen, on one process instance. -/
structure PendingEntry where
  citizen : String
  eca : String
  process : String
  choices : List (String × List String)
deriving Repr, DecidableEq

structure VerdictData where
  fired : List String
  pending : List PendingEntry
  violations : List Violation
  readings : List Reading
  phase : String
deriving Repr, DecidableEq

def pendingEntryJson (p : PendingEntry) : Json :=
  let base : List (String × Json) :=
    [("eca", toJson p.eca), ("process", toJson p.process)]
  let pairs : List (String × Json) :=
    p.choices.map (fun kv =>
      (kv.1, Json.arr (kv.2.toArray.map (fun v => toJson v))))
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

/-! ## Results and violations -/

def approvedOf (s : Snapshot) : List Req :=
  (s.reqs.filter (fun r => r.status == "approved"))

/-- The most recently settled requisition, by declared finish day then hour, so
    the choice does not depend on the order instances arrived in. -/
def lastSettledOf (s : Snapshot) : Option Req :=
  (s.reqs.filter (fun r => r.finishDay.isSome)).foldl (fun best r =>
    match best with
    | none => some r
    | some b =>
      if r.finishDayOf > b.finishDayOf then some r
      else if r.finishDayOf == b.finishDayOf && r.finishHourOf > b.finishHourOf then some r
      else best) (none : Option Req)

def readingsOf (s : Snapshot) : List Reading :=
  let counts : List Reading :=
    [ { id := "openRequisitions", kind := .decimal
      , value := .num (openReqsOf s).length, refClass := none }
    , { id := "approvedTotal", kind := .decimal
      , value := .num (approvedOf s).length, refClass := none } ]
  match lastSettledOf s with
  | none => counts
  | some r => counts ++
    [ { id := "lastSettled", kind := .ref, value := .iri r.id
      , refClass := some (ph "Requisition") } ]

/-- Clause 6: a decision after the deadline is late. -/
def lateReqs (s : Snapshot) : List Req :=
  (s.reqs.filter (fun r => r.late))

/-- An undecided requisition past the deadline, with no Officer to decide it. -/
def strandedReqs (s : Snapshot) : List Req :=
  (openReqsOf s).filter (fun r => pastDeadline? r.day && s.officerId.isNone)

def violationsOf (s : Snapshot) : List Violation :=
  let late : List Violation := (lateReqs s).map (fun r =>
    { eca := "late_decision"
    , witness := Witness.withCounts [r.requester]
        [("decided_on", r.finishDayOf), ("deadline", deadlineDay)]
    , detail := s!"decided on day {r.finishDayOf}, after the deadline on day {deadlineDay}" })
  let stranded : List Violation :=
    if (strandedReqs s).isEmpty then []
    else
      let refs := (strandedReqs s).map (·.requester)
      let detail :=
        s!"{(strandedReqs s).length} requisition(s) undecided past the deadline and no Officer in office"
      [ { eca := "no_officer"
        , witness := Witness.withCounts refs [("day", s.day), ("deadline", deadlineDay)]
        , detail := detail } ]
  late ++ stranded

/-! ## The verdict's own shape -/

def ecaIds : List String := ["lodge", "withdraw", "settle"]

def firedOf (s : Snapshot) : List String :=
  let settling : List String := if (openReqsOf s).isEmpty then ["lodge"] else ["settle"]
  let withdrawing : List String :=
    if (openReqsOf s).isEmpty then [] else ["withdraw"]
  settling ++ withdrawing ++ (if windowOpen? s.day then ["lodge"] else [])

def pendingOf (s : Snapshot) : List PendingEntry :=
  let citizens : List PendingEntry := s.citizens.flatMap (fun c =>
    (if windowOpen? s.day && !(holdsOpenIn s c.id) && lodgeDue? s c.id
      then [{ citizen := c.id, eca := "lodge", choices := []
              , process := reqIri c.id ((s.reqs.filter (fun r => r.requester == c.id)).length) }]
      else []) ++
    (match openOfIn s c.id with
      | some r => [{ citizen := c.id, eca := "withdraw", process := r.id, choices := [] }]
      | none => []))
  -- The Officer's duty names each open instance it applies to, and offers
  -- EVERY open instance as the choice, so a consumer may act in one other than
  -- the one the entry is anchored to. That is the whole point: several
  -- requisitions are ongoing at once and the act has to say which.
  let officerPending : List PendingEntry :=
    match s.officerId with
    | none => []
    | some o =>
      (openReqsOf s).map (fun r =>
        { citizen := o, eca := "settle", process := r.id
        , choices := [("requisition", openReqIrisOf s), ("decision", ["approved", "refused"])] })
  citizens ++ officerPending

def lastStatus (s : Snapshot) : String :=
  (s.reqs.foldl (fun (acc : Nat × String) r =>
    if r.finishDayOf >= acc.1 then (r.finishDayOf, r.status) else acc)
    (0, "approved")).2

def phaseOf (s : Snapshot) : String :=
  if (openReqsOf s).isEmpty then
    if s.reqs.isEmpty then iriStateClosed else stateIriOf (lastStatus s)
  else if (openReqsOf s).any (fun r => pastDeadline? s.day) then iriStateLate
  else iriStateOpen

def evaluate (s : Snapshot) : VerdictData :=
  { fired := firedOf s
  , pending := pendingOf s
  , violations := violationsOf s
  , readings := readingsOf s
  , phase := phaseOf s }

/-! ## Actions

    `apply` is the enforcing path and reuses exactly the guards `check`
    evaluates, so precondition truth has one source. -/

inductive Act where
  | lodge (citizen : String)
  | withdraw (citizen : String)
  | settle (officer requisition decision : String)
deriving Repr, DecidableEq

def actEca : Act → String
  | .lodge _ => "lodge"
  | .withdraw _ => "withdraw"
  | .settle _ _ _ => "settle"

instance : FromJson Act where
  fromJson? j := do
    let eca ← j.getObjVal? "eca" >>= FromJson.fromJson? (α := String)
    match eca with
    | "lodge" => do
      let citizen ← j.getObjVal? "citizen" >>= FromJson.fromJson? (α := String)
      return .lodge citizen
    | "withdraw" => do
      let citizen ← j.getObjVal? "citizen" >>= FromJson.fromJson? (α := String)
      return .withdraw citizen
    | "settle" => do
      let officer ← j.getObjVal? "officer" >>= FromJson.fromJson? (α := String)
      let requisition ← j.getObjVal? "requisition" >>= FromJson.fromJson? (α := String)
      let decision ← j.getObjVal? "decision" >>= FromJson.fromJson? (α := String)
      return .settle officer requisition decision
    | other => Except.error s!"unknown eca: {other}"

/-- Lodging CREATES the instance. A requisition is discovered from the graph by
    its type, so it has to be in the snapshot before writeBack can mint it --
    which is why `mints: Requisition` is declared in the manifest. -/
def applyLodge (s : Snapshot) (citizen : String) : Except String Snapshot :=
  if lodgeDue? s citizen then
    -- The occurrence index: how many requisitions this citizen has already had.
    let k := (s.reqs.filter (fun r => r.requester == citizen)).length
    let base : Req :=
      { id := reqIri citizen k
      , day := s.day
      , hour := s.hour
      , requester := citizen
      , sum := s.scheduleSum
      , goods := iriGoods
      , status := "open"
      , outcome := none
      , late := false
      , startDay := none
      , startHour := none
      , finishDay := none
      , finishHour := none
      , decidedBy := none }
    let fresh := base.stampStartAt s.day s.hour
    .ok { s with reqs := s.reqs ++ [fresh] }
  else .error "lodge not due"

def applyWithdraw (s : Snapshot) (citizen : String) : Except String Snapshot :=
  if withdrawDue? s citizen then
    match openOfIn s citizen with
    | none => .error "withdraw not due"
    | some r =>
      -- Stamped at the CURRENT moment, which is typically inside the window
      -- rather than on the deadline: the mid-span ending.
      let withdrawn := { r with status := "withdrawn", outcome := some "withdrawn" }
      let closed := withdrawn.stampFinishAt s.day s.hour
      .ok (updateReq s r.id (fun _ => closed))
  else .error "withdraw not due"

def applySettle (s : Snapshot) (officer requisition decision : String) : Except String Snapshot :=
  -- Order matters: the instance is checked by NAME first, so naming one the
  -- law has never heard of is refused as such rather than as "not due".
  if !(knownReq? s requisition) then .error s!"unknown requisition: {requisition}"
  else if !(decisionValid? decision) then .error s!"unknown decision: {decision}"
  else if s.officerId != some officer then .error "not the officer"
  else if !(settleDue? s requisition) then .error s!"settle not due: {requisition}"
  else
    match reqById s requisition with
    | none => .error s!"unknown requisition: {requisition}"
    | some r =>
      let late := pastDeadline? s.day
      let marked : Req := { r with status := decision, outcome := some decision, late := late, decidedBy := some officer }
      let decided := marked.stampFinishAt s.day s.hour
      .ok (updateReq s requisition (fun _ => decided))

def apply : Act → Snapshot → Except String Snapshot
  | .lodge c, s => applyLodge s c
  | .withdraw c, s => applyWithdraw s c
  | .settle o r d, s => applySettle s o r d

/-! ## Writing back

    Everything is minted from the snapshot, so the returned graph is the whole
    state. Nothing here removes an individual: a withdrawal closes a
    requisition and records that, rather than erasing it. -/

def ensureReq (g : Graph) (r : Req) : Graph :=
  let id := r.id
  let chrono := chronoIri id
  let g1 := Graph.setOne g id rdfType (.iri (ph "Requisition"))
  let g2 := Graph.setOne g1 id (ph "label")
    (.lit s!"Requisition of {shortId r.requester}" "string")
  let g3 := Graph.setOne g2 id (ph "dayIndex") (natLit r.day)
  let g4 := Graph.setOne g3 id (ph "atHour") (natLit r.hour)
  let g5 := Graph.setOne g4 id (ph "sum") (natLit r.sum)
  let g6 := Graph.setOne g5 id (ph "goods") (.iri r.goods)
  let g7 := Graph.setOne g6 id (ph "status") (.lit r.status "string")
  let g8 := Graph.setOne g7 id (ph "late") (boolLit r.late)
  let g9 := match r.outcome with
    | none => g8
    | some o => Graph.setOne g8 id (ph "outcome") (.lit o "string")
  let g10 := match r.decidedBy with
    | none => g9
    | some d => Graph.setOne g9 id (ph "decidedBy") (.iri d)
  let g11 := Graph.setOne g10 id (ph "hasTime") (.iri chrono)
  -- The Chronoid, with each bound denoting ONE moment: day AND hour together.
  let timeBoundary (base : Graph) (which : String) (d h : Nat) : Graph :=
    let b1 := Graph.setOne base which rdfType (.iri gfoTimeBoundary)
    let b2 := Graph.setOne b1 which (ph "dayIndex") (natLit d)
    Graph.setOne b2 which (ph "atHour") (natLit h)
  let bStart := ph "bound/start/" ++ shortId id
  let bFinish := ph "bound/finish/" ++ shortId id
  let g12 := Graph.setOne g11 chrono rdfType (.iri gfoChronoid)
  let g12a := Graph.setOne g12 chrono (ph "label")
    (.lit s!"Life of requisition {shortId id}" "string")
  let g13 := timeBoundary g12a bStart r.startDayOf r.startHourOf
  let g14 := timeBoundary g13 bFinish r.finishDayOf r.finishHourOf
  let g15 := if isOpen r then g14
    else Graph.setOne g14 chrono gfoFinished (.iri bFinish)
  let g16 := Graph.setOne g15 chrono gfoStarted (.iri bStart)
  -- The requester, as a Role played in the requisition.
  let role := ph "role/requester/" ++ shortId id
  g16 ++ (roleTriplesAt role (ph "RequisitionerRole") id r.requester)

def ensureOfficer (g : Graph) (s : Snapshot) : Graph :=
  match s.officerId with
  | none => g
  | some o => g ++ (roleTriplesAt iriOfficer (ph "OfficerRole") iriHamlet o)

def writeBack (g : Graph) (s : Snapshot) : Graph :=
  -- The clock is the driver's one local write; it is echoed back so the
  -- returned graph is the whole state.
  let withClock := (Graph.setOne (Graph.setOne g (ph "clock/now") (ph "dayIndex") (natLit s.day))
      (ph "clock/now") (ph "atHour") (natLit s.hour))
  -- Every requisition sits at the current position, so a decision made now is
  -- recorded as made now.
  let placed := s.reqs.foldl (fun acc r => ensureReq acc { r with day := s.day, hour := s.hour })
    withClock
  ensureOfficer placed s

def applyGraph (act : Act) (g : Graph) : Except String Graph :=
  match apply act (snapshotOf g) with
  | .error reason => .error reason
  | .ok s' => .ok (writeBack g s')
