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

/-- A ballot is not a thing: it is a MEANING a sheet plays in one election.

    A sheet of paper does not become a ballot by being written on. It plays the
    role of one, so the sheet is the holder (`sheet`), the election is the
    situation, and `candidate` is resolved through the Role's `ph:denotes` --
    never by comparing the written literal to a name, which is why `candidate`
    can differ from the text on the paper and still be right.

    `delivered` is read off the graph, not set at construction: it is true when
    the Role records that this ballot reached its owner's mailbox. -/
structure Ballot where
  sheet : String
  owner : String
  candidate : String
  delivered : Bool
deriving Repr, DecidableEq

/-- A thing, and the citizen whose it is.

    A structure rather than a `String × String` because two `Snapshot` fields
    carry this shape -- the paper supply and the mailboxes -- and in the quorum
    flavour they were built in OPPOSITE orders, so a caller with the other
    convention in mind got a citizen's IRI where a mailbox was expected and the
    law refused a delivery the seed had plainly supplied. A named field cannot be
    transposed. -/
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
  /-- Blank sheets the hamlet has, each with the citizen whose papers it is, in
      canonical order. The supply is SEEDED rather than minted, because law.txt:11
      requires one paper per candidate for each citizen and that count is fixed
      by the registry at preparation time -- not knowable when the world is
      seeded. `prepare` writes on what it needs from here and refuses naming a
      shortfall if the registry asks for more than the drawer holds. -/
  sheets : List Owned
  /-- Things qualified to inscribe. Seeded as a QUALIFICATION rather than a
      kind: law.txt never says what is held, so this is every individual bearing
      `ph:Inscriptible` whatever else it happens to be. -/
  instruments : List String
  /-- The mailboxes, each with the citizen whose it is, as law.txt:12 states it
      ("the mailbox of each citizen"). A duty whose premise fails here is refused
      naming the citizen rather than inventing somewhere to put the papers. -/
  mailboxes : List Owned
  /-- The ballot boxes, in canonical order. A named thing, not a supply: a vote
      has nowhere to go without one, so `vote` refuses rather than recording a
      vote that reached no box. -/
  ballotBoxes : List String
  /-- The moments this election's Chronoid bounds denote, read back from them.
      Absent means not begun / not ended -- which is how a consumer tells an
      initialised instance from an ongoing one. -/
  startedAt : Option (Nat × Nat)
  finishedAt : Option (Nat × Nat)
deriving Repr, DecidableEq

/-- Record the moment the instance began, if it has not been recorded.

    From the clock, never from a stored day: the clock is the only carrier of
    the present, so a bound taken from anything else would name a schedule
    rather than a moment. -/
def stampStartAt (s : Snapshot) : Snapshot :=
  { s with
    startedAt := some (match s.startedAt with
      | some m => m
      | none => (s.day, s.hour)) }

def stampFinishAt (s : Snapshot) : Snapshot :=
  { s with
    finishedAt := some (match s.finishedAt with
      | some m => m
      | none => (s.day, s.hour)) }

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

private def getOptStr (j : Json) (k : String) : Except String (Option String) :=
  match j.getObjVal? k with
  | .error _ => .ok none
  | .ok Json.null => .ok none
  | .ok v => (Option.some ·) <$> FromJson.fromJson? (α := String) v

/-- A list of owned things, defaulting to empty when absent. The paper supply
    and the mailboxes are seeded facts about the hamlet, so a snapshot that
    predates them still parses rather than failing the round-trip. -/
private def getOwnedList (j : Json) (k : String) : List Owned :=
  match j.getObjVal? k with
  | .error _ => []
  | .ok v => match FromJson.fromJson? (α := List Owned) v with
    | .ok xs => xs
    | .error _ => []

/-- A list of IRIs, defaulting to empty when absent. -/
private def getListStr (j : Json) (k : String) : List String :=
  match j.getObjVal? k with
  | .error _ => []
  | .ok v => match FromJson.fromJson? (α := List String) v with
    | .ok xs => xs
    | .error _ => []

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
    -- The paper supply, the instruments and the mailboxes are SEEDED facts about
    -- the hamlet, so they are re-derived from the graph on every `snapshotOf`.
    -- Read leniently so a snapshot that predates them still round-trips.
    let sheets := getOwnedList j "sheets"
    let instruments := getListStr j "instruments"
    let mailboxes := getOwnedList j "mailboxes"
    let ballotBoxes := getListStr j "ballotBoxes"
    return Snapshot.mk day hour citizens candidates ballots registry box
      announced prepared counted proclaimed mayorId
      sheets instruments mailboxes ballotBoxes
      none none

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
def gfoTimeBoundary : String := "https://w3id.org/gfo-light/TimeBoundary"
def iriElection : String := ph "election/mayor-2027-r0"

/-- A stable short name for an entity, from the last path segment of its IRI.
    Minted IRIs must be deterministic from the act's parameters so a replayed
    act addresses the same individual. -/
def shortId (iri : String) : String :=
  match (iri.splitOn "/").getLast? with
  | some s => s
  | none => iri
def chronoElection : String := ph "chronoid/mayor-2027-r0"

/-- The moment a Chronoid bound denotes, read the way a consumer reads it.

    Each bound names ONE moment, so it carries both the day and the hour. -/
def boundMoment (g : Graph) (which : String) : Option (Nat × Nat) :=
  match g.iriOf? iriElection (ph "hasTime") with
  | none => none
  | some ch =>
    match g.iriOf? ch which with
    | none => none
    | some b =>
      match g.iriOf? b (ph "dayIndex"), g.iriOf? b (ph "atHour") with
      | some _, some _ => some (g.natOf b (ph "dayIndex"), g.natOf b (ph "atHour"))
      | _, _ => none
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

/-- Where this ballot was put, in this election. `none` while it is undelivered.

    On the ROLE, not the sheet. A sheet is a reusable physical object -- one
    supply of paper serves every election -- so a sheet left in its owner's
    mailbox by one election is still there for the next, and a delivery recorded
    against the sheet would make the next election's ballots read as delivered
    before anyone carried them. The Role's IRI is a function of the occurrence,
    so scoping delivery to it costs nothing. -/
def deliveredTo? (g : Graph) (role : String) : Option String :=
  g.iriOf? role (ph "deliveredTo")

/-- The ballots, read back as Roles.

    The candidate comes from `ph:denotes` -- the Role's relation to the citizen
    it stands for -- and the owner from the sheet's own `ph:ownedBy`. The written
    literal is never consulted, which is why the text on the paper may spell the
    name differently from the citizen's label and still resolve to the same
    person.

    Each Role carries exactly one `ph:playedBy`, the sheet. The owner is
    therefore not a second role on it but the sheet's own fact, which keeps one
    place in the graph answering "whose ballot is this" rather than two. -/
def ballotsOf (g : Graph) : List Ballot :=
  (Graph.typedOf g (ph "BallotVote")).filterMap fun r =>
    match g.iriOf? r (ph "roleIn"), g.iriOf? r (ph "playedBy"),
          g.iriOf? r (ph "denotes") with
    | some ctx, some sheet, some cand =>
      if ctx == iriElection then
        match g.iriOf? sheet (ph "ownedBy") with
        | some owner => some (Ballot.mk sheet owner cand ((deliveredTo? g r).isSome))
        | none => none
      else none
    | _, _, _ => none

/-- The ballot boxes, in canonical order. law.txt:13 requires a big closed box
    standing in the townhall where everyone can see it. It is a NAMED thing
    rather than a supply: there is one, it is seeded, and a vote has nowhere to
    go without it. -/
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

/-- Things qualified to inscribe. The qualification, not the kind: the law never
    says what is held, so this is every individual bearing `ph:Inscriptible`
    whatever else it happens to be. -/
def instrumentsOf (g : Graph) : List String :=
  ((Graph.typedOf g (ph "Inscriptible")).mergeSort (fun a b => a < b))

/-- The mailboxes, each with the citizen whose it is, in canonical order. -/
def mailboxesOf (g : Graph) : List Owned :=
  ((Graph.typedOf g (ph "Mailbox")).filterMap fun m =>
    match g.iriOf? m (ph "ownedBy") with
    | some owner => some (Owned.mk m owner)
    | none => none).mergeSort (fun a b =>
      a.owner < b.owner || (a.owner == b.owner && a.thing < b.thing))

/-- The mailbox a citizen receives at, if the seed supplies one. law.txt:12 says
    each citizen has one; where the seed does not, this is `none` and the duty
    has no object to act on, which is what `applyDeliver` refuses on. -/
def mailboxOf? (g : Graph) (citizen : String) : Option String :=
  ((Graph.typedOf g (ph "Mailbox")).filterMap fun m =>
    if g.iriOf? m (ph "ownedBy") == some citizen then some m else none).head?

/-- The sheet a citizen's ballot for a candidate is played by, if they have one.

    A citizen who was never issued a paper has cast a vote all the same -- the law
    does not make receiving a ballot a precondition of voting -- so this is `none`
    and only the `CastVote` occurrence is recorded. -/
def sheetFor (s : Snapshot) (owner cand : String) : Option String :=
  ((s.ballots.find? fun b => b.owner == owner && b.candidate == cand)).map (·.sheet)

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

/-- The current position, from the single `ph:Clock` the framework fixes,
    FLOORED at every moment the graph already records.

    The clock is untrusted input and the graph's only free variable, so a value
    earlier than a recorded moment would let the world contradict itself --
    rewinding to before polls close would reopen the box and admit a vote into
    an election already counted. The floor is every `gfo-light:TimeBoundary` the
    graph holds, because those are moments an act recorded. -/
def recordedMoments (g : Graph) : List (Nat × Nat) :=
  (Graph.typedOf g gfoTimeBoundary).map fun b =>
    (g.natOf b (ph "dayIndex"), g.natOf b (ph "atHour"))

/-- Lexicographic order on a moment: day first, then hour. -/
def momentAfter (a b : Nat × Nat) : Bool :=
  decide (a.1 > b.1 ∨ (a.1 == b.1 ∧ a.2 > b.2))

def clockOf (g : Graph) : Nat × Nat :=
  let now := (g.natOf iriClock (ph "dayIndex"), g.natOf iriClock (ph "atHour"))
  (recordedMoments g).foldl (fun acc m => if momentAfter m acc then m else acc) now

def snapshotOf (g : Graph) : Snapshot :=
  let (d, h) := clockOf g
  { day := d
    hour := h
    citizens := citizensOf g
    candidates := candidatesOf g
    ballots := ballotsOf g
    registry := registryOf g
    box := votesOf g
    announced := flagOn g "announced"
    prepared := flagOn g "prepared"
    counted := flagOn g "counted"
    proclaimed := flagOn g "proclaimed"
    mayorId := mayorIn g
    sheets := sheetsOf g
    instruments := instrumentsOf g
    mailboxes := mailboxesOf g
    ballotBoxes := boxesOf g
    startedAt := boundMoment g "https://w3id.org/gfo-core/temporallyStartedBy"
    finishedAt := boundMoment g "https://w3id.org/gfo-core/temporallyFinishedBy" }

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

/-- Papers may go into mailboxes from the moment they are written until the
    polls open. `prepared = true` means the making act ran on the prepare day,
    and the clock only moves forward, so no lower bound is needed -- and the
    upper bound is the law's own: the papers must be there before anyone votes,
    which is 9am on election day (law.txt:15). -/
def deliverDue? (s : Snapshot) : Bool :=
  decide (s.prepared = true ∧
    (s.day < electionDay ∨ (s.day = electionDay ∧ s.hour < pollOpenHour)))
def DeliverDue (s : Snapshot) : Prop :=
  s.prepared = true ∧
    (s.day < electionDay ∨ (s.day = electionDay ∧ s.hour < pollOpenHour))
theorem deliverDue_agrees (s : Snapshot) :
    deliverDue? s = true ↔ DeliverDue s := by
  simp [deliverDue?, DeliverDue]

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

/-- This law's results, as readings.

    Before anyone has won there is no result to report, so the list is empty
    rather than carrying a `mayor` entry with nothing in it. -/
def readingsOf (s : Snapshot) : List Reading :=
  match winner? s with
  | none => []
  | some w =>
    [ { id := "mayor", kind := .ref, value := .iri w
      , refClass := some (ph "Citizen") }
    , { id := "mayorVotes", kind := .decimal
      , value := .num (voteCount s w), refClass := none } ]

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
  ["announce", "nominate", "prepare", "deliver", "vote", "count", "proclaim"]

/-- A ballot Role's IRI: a function of the SHEET it is played by.

    It no longer names the candidate. A sheet plays at most one ballot role, so
    the sheet identifies it, and deriving the IRI from the sheet is what makes
    re-deriving it a no-op: writing the same sheet again lands on the same
    individual rather than minting a second one. -/
def iriBallot (sheet : String) : String :=
  ph "ballot/" ++ shortId sheet
def iriNomination (citizen : String) : String :=
  ph "nomination/" ++ shortId citizen
def iriVote (voter cand : String) : String :=
  ph "vote/" ++ shortId voter ++ "-" ++ shortId cand

/-- Citizens whose papers are still not in a mailbox. Sorted and deduplicated
    because "each citizen" is what delivery iterates over: one entry per citizen
    with something outstanding, however many of their ballots that is. -/
def awaitingDelivery (s : Snapshot) : List String :=
  ((s.ballots.filterMap fun b =>
    if b.delivered then none else some b.owner).mergeSort (fun a b => a < b)) |>.eraseDups

/-- Which ECAs' conditions currently hold.

    Each entry calls the SAME guard `apply` enforces, rather than restating the
    condition. Restating it let the two drift: `fired` listed `announce` on the
    day it had already been announced and `vote` after the polls had shut, while
    `apply` refused both. `fired` is what a consumer reads to show what is
    happening, so advertising an act the oracle will reject is worse than
    advertising nothing -- it offers a button that cannot work.

    `mayor-quorum` had the same drift on `vote` and was corrected the same way. -/
def firedOf (s : Snapshot) : List String :=
  (if announceDue? s then ["announce"] else []) ++
  (if nominateOpen? s then ["nominate"] else []) ++
  (if prepareDue? s then ["prepare"] else []) ++
  (if deliverDue? s && !(awaitingDelivery s).isEmpty then ["deliver"] else []) ++
  (if pollsOpen? s then ["vote"] else []) ++
  (if countDue? s then ["count"] else []) ++
  (if proclaimDue? s then ["proclaim"] else [])

def pendingOf (s : Snapshot) : List PendingEntry :=
  let authPending : List PendingEntry := match authorityId s with
    | none => []
    | some a =>
      (if announceDue? s then [{ citizen := a, eca := "announce", process := iriElection, choices := [] }] else []) ++
      (if prepareDue? s then [{ citizen := a, eca := "prepare", process := iriElection, choices := [] }] else []) ++
      -- One duty, offered once, with the recipients as its choices: the holder
      -- is the authority throughout, and "each citizen" is what it iterates.
      (if deliverDue? s && !(awaitingDelivery s).isEmpty then
        [{ citizen := a, eca := "deliver", process := iriElection,
           choices := [("recipient", awaitingDelivery s)] }]
       else []) ++
      (if countDue? s then [{ citizen := a, eca := "count", process := iriElection, choices := [] }] else []) ++
      (if proclaimDue? s then [{ citizen := a, eca := "proclaim", process := iriElection, choices := [] }] else [])
  let nominees : List PendingEntry :=
    if nominateOpen? s then
      (s.citizens.filter (fun c => !(s.registry.any (· == c.id)))).map
        (fun c => { citizen := c.id, eca := "nominate", process := iriElection, choices := [] })
    else []
  let voters : List PendingEntry :=
    if pollsOpen? s then
      (s.citizens.filter (fun c => decide (!(voted? s c.id)))).map
        (fun c => { citizen := c.id, eca := "vote", process := iriElection,
                       choices := [("candidate", s.candidates)] })
    else []
  authPending ++ nominees ++ voters

def violationsOf (s : Snapshot) : List Violation :=
  let dist : List Violation := match firstMissing? s with
    | none => []
    | some (c, cand) =>
      if decide (prepareDay ≤ s.day) then
        -- The citizen first, because that is what the duty is owed to and what a
        -- consumer acts on. Then the candidate whose ballot is missing. Then the
        -- ballot ITSELF where one was made: that is the difference between
        -- "Alice never got a ballot for Cara" and "Alice's ballot for Cara was
        -- written and never carried", and only the second names an individual a
        -- reader can go and look at.
        let refs := match sheetFor s c cand with
          | some sheet => [c, cand, iriBallot sheet]
          | none => [c, cand]
        [{ eca := "all_distributed", witness := Witness.ofRefs refs,
           detail := match sheetFor s c cand with
             | some _ => "ballot written but not delivered"
             | none => "ballot missing" }]
      else []
  let dupes : List Violation := (doubleVoters s).map (fun v =>
    { eca := "single_vote", witness := Witness.ofRefs [v],
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
    | other => .error s!"unknown eca: {other}"

def applyAnnounce (s : Snapshot) : Except String Snapshot :=
  match authorityId s with
  | none => .error "no authority in office"
  | some _ =>
    if announceDue? s then
      let cy := stampStartAt { s with announced := true }
      .ok cy
    else .error "announce not due"

def applyNominate (s : Snapshot) (c : String) : Except String Snapshot :=
  if !nominateOpen? s then .error "registry closed"
  else if s.registry.any (· == c) then .error "already registered"
  else .ok { s with registry := c :: s.registry }

/-! Making the ballots.

    law.txt:11-12 requires "one paper per candidate for each citizen". That count
    is fixed by the registry AT PREPARATION TIME, which is not knowable when the
    world is seeded -- so the paper is not minted here. The seed supplies blank
    sheets, what this hamlet has in the drawer, and this act writes on them.

    Nothing is conjured: a paper that the drawer does not hold is a refusal
    naming the shortfall, not a silent shortfall. -/

/-- One citizen's ballots: one paper per candidate, each on a sheet of their own.
    `none` when their supply is short of the registry.

    The pairing is positional within ONE citizen's sheets, which is stable
    because both the sheet list and the candidate list are canonically ordered. -/
def ballotsFor (s : Snapshot) (c : Citizen) : Option (List Ballot) :=
  let mine := sheetsFor s c.id
  let cands := s.candidates
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
    (c.id, (sheetsFor s c.id).length, s.candidates.length)

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
        .ok (stampStartAt { s with prepared := true, ballots := bals })

/-! Putting the ballots in the mailboxes.

    One act, one recipient. law.txt:11-12 gives the authority ONE duty -- "they
    must put these papers in the mailbox of each citizen" -- and "each citizen"
    is what it iterates over, so iterating here keeps the duty the authority's
    while making a partial delivery a state that exists: with one act per
    recipient, some citizens' mailboxes are filled and others' are not, and
    `allDistributed` reports that with the undelivered citizen as the witness. -/

def applyDeliver (s : Snapshot) (recipient : String) : Except String Snapshot :=
  if !deliverDue? s then
    .error "papers cannot go into mailboxes yet: nothing has been made, or the polls are open"
  else
    let mine := s.ballots.filter (fun b => b.owner == recipient)
    if mine.isEmpty then
      .error s!"no papers were made out for {shortId recipient}"
    else if !((s.mailboxes.map (·.owner)).contains recipient) then
      -- law.txt:12 says each citizen has a mailbox. Where the seed does not
      -- supply one, the honest answer is that the duty has no object to act on.
      .error s!"no mailbox is seeded for {shortId recipient}"
    else if mine.all (·.delivered) then
      .error s!"{shortId recipient}'s papers are already in their mailbox"
    else
      .ok { s with ballots := s.ballots.map (fun b =>
        if b.owner == recipient then { b with delivered := true } else b) }

def applyVote (s : Snapshot) (v c : String) : Except String Snapshot :=
  if !pollsOpen? s then .error "polls closed"
  else if voted? s v then .error "citizen already voted"
  else if s.ballotBoxes.isEmpty then
    -- law.txt:13 requires a big closed box standing in the townhall. This is the
    -- one individual this law declares an act as acting on: it is named, seeded,
    -- and a vote has nowhere to go without it. So the act refuses naming it
    -- rather than recording a vote that reached nothing -- which would let the
    -- tally be counted from ballots no one ever put anywhere.
    .error "there is no ballot box in the hamlet, so a vote has nowhere to go"
  else .ok { s with box := Vote.mk v c :: s.box }

def applyCount (s : Snapshot) : Except String Snapshot :=
  if countDue? s then
      let cy := stampStartAt { s with counted := true }
      .ok cy
  else .error "count not due"

def applyProclaim (s : Snapshot) : Except String Snapshot :=
  match winner? s with
  | none => .error "no candidates"
  | some w =>
    if proclaimDue? s then
      let cy := stampFinishAt (stampStartAt { s with proclaimed := true, mayorId := some w })
      .ok cy
    else .error "proclaim not due"

def apply : Act → Snapshot → Except String Snapshot
  | .announce, s => applyAnnounce s
  | .nominate c, s => applyNominate s c
  | .prepare, s => applyPrepare s
  | .deliver r, s => applyDeliver s r
  | .vote v c, s => applyVote s v c
  | .count, s => applyCount s
  | .proclaim, s => applyProclaim s

/-! Writing a snapshot back into the graph.
    `apply` returns the WHOLE graph and the consumer replaces its stored copy
    wholesale, so the oracle's state and the graph can never diverge. Nothing
    is ever removed: a cast vote or a delivered ballot persists for the rest
    of the simulation, and a later rule may only change how it is counted. -/


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
  -- The clock is the runtime's one write; it is echoed back unchanged. Echoing
  -- it from anything else would make the oracle a second writer on it.
  let base :=
    g.setOne iriClock (ph "dayIndex") (.lit (toString s.day) "integer")
     |>.setOne iriClock (ph "atHour") (.lit (toString s.hour) "integer")
     |>.setOne iriElection (ph "announced") (boolLit s.announced)
     |>.setOne iriElection (ph "prepared") (boolLit s.prepared)
     |>.setOne iriElection (ph "counted") (boolLit s.counted)
     |>.setOne iriElection (ph "proclaimed") (boolLit s.proclaimed)
     |>.setOne iriElection (ph "hasTime") (.iri chronoElection)
  -- Lifecycle bounds take GFO's shape: the Chronoid's start and finish point at
  -- TimeBoundary individuals, each denoting ONE moment (day AND hour together).
  -- Absence of a start bound is what marks this instance initialised rather than
  -- ongoing. A bound is written only when the moment EXISTS -- a placeholder day
  -- for a bound nothing points at would put a `ph:dayIndex` in the graph naming
  -- a moment no act ever recorded.
  let timeBoundary (base : Graph) (which : String) (m : Option (Nat × Nat)) : Graph :=
    match m with
    | some (d, h) =>
      let b1 := Graph.setOne base which rdfType (.iri gfoTimeBoundary)
      let b2 := Graph.setOne b1 which (ph "dayIndex") (.lit (toString d) "integer")
      Graph.setOne b2 which (ph "atHour") (.lit (toString h) "integer")
    | none => base
  let bStart := ph "bound/start/mayor-2027-r0"
  let bFinish := ph "bound/finish/mayor-2027-r0"
  let withChronoid :=
    let c1 := Graph.setOne base chronoElection rdfType
      (.iri "https://w3id.org/gfo-light/Chronoid")
    timeBoundary (timeBoundary c1 bStart s.startedAt) bFinish s.finishedAt
  let withBounds :=
    let g1 : Graph :=
      if s.startedAt.isSome then
        Graph.setOne withChronoid chronoElection
          "https://w3id.org/gfo-core/temporallyStartedBy" (.iri bStart)
      else withChronoid
    if s.finishedAt.isSome then
      Graph.setOne g1 chronoElection
        "https://w3id.org/gfo-core/temporallyFinishedBy" (.iri bFinish)
    else g1
  let base := withBounds
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
  --
  -- DELIVERY belongs to the Role, so it is scoped to the election that carried
  -- it. Recorded once, and never removed -- taking a paper back out would be an
  -- erasure the gate forbids, and a Role's delivery is a thing that happened.
  let withBallots := s.ballots.foldl (fun a b =>
    let bi := iriBallot b.sheet
    let written := (Graph.litOf? a b.candidate (ph "label")).getD ""
    let a1 := Graph.setOne a b.sheet (ph "label") (.lit written "string")
    let a2 := if (Graph.iriOf? a1 bi rdfType).isSome then a1
      else a1 ++
        [ { subject := bi, predicate := rdfType, object := .iri (ph "BallotVote") }
        , { subject := bi, predicate := ph "roleIn", object := .iri iriElection }
        , { subject := bi, predicate := ph "playedBy", object := .iri b.sheet }
        , { subject := bi, predicate := ph "denotes", object := .iri b.candidate } ]
    match if b.delivered then mailboxOf? a2 b.owner else none with
    | none => a2
    | some mailbox =>
      if (Graph.iriOf? a2 bi (ph "deliveredTo")).isSome then a2
      else a2 ++ [ { subject := bi, predicate := ph "deliveredTo",
                     object := .iri mailbox } ]) withNominations
  let votes := s.box.filterMap fun v =>
    match g.iriOf? (iriVote v.voter v.candidate) rdfType with
    | some _ => none
    | none => some v
  -- A CAST VOTE is a `ph:Deposit` -- the shared act of putting a thing into a
  -- container -- so where the ballot went is recorded with the shared
  -- `ph:placedIn`, on the SHEET, because that is the physical fact: the paper is
  -- in the box. (Contrast a ballot's DELIVERY to a mailbox, which is contextual
  -- and lives on the Role.)
  --
  -- The sheet is the citizen's own ballot for that candidate where they have one.
  -- A citizen who was never issued a paper has cast a vote all the same -- the law
  -- does not make receiving a ballot a precondition of voting -- so there is
  -- nothing to place and only the `CastVote` occurrence is recorded.
  let placedTriples (v : Vote) : List Triple :=
    match s.ballotBoxes.head? with
    | none => []
    | some box => match sheetFor s v.voter v.candidate with
      | some sheet => [ { subject := sheet, predicate := ph "placedIn",
                          object := .iri box } ]
      | none => []
  withBallots ++ (votes.flatMap fun v =>
    [ { subject := iriVote v.voter v.candidate, predicate := rdfType
      , object := .iri (ph "CastVote") } ] ++
    (roleTriples' (ph "VoterRole") (iriVote v.voter v.candidate) v.voter) ++
    (roleTriples' (ph "CandidateRole") (iriVote v.voter v.candidate) v.candidate) ++
    (placedTriples v))

/-- `apply` over the graph: derive, transition, write the whole graph back. -/
def applyGraph (act : Act) (g : Graph) : Except String Graph :=
  match apply act (snapshotOf g) with
  | .error reason => .error reason
  | .ok s' => .ok (writeBack g s')
