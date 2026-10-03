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
