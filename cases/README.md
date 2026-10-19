# Artefacts

One directory per law variant: `cases/<case>/`.

## Layout

```
cases/mayor-2027/
  law.txt         # source governance text (single source of truth)
  ontology.ttl    # frozen TBox: classes and properties only
  population.ttl  # seeded individuals the law starts from
  rules.lean      # ECA conditions + holders as Bool/Prop twins
  manifest.yaml   # loader + display glue
  oracle          # compiled binary (rebuilt by tools/lawgen/build_oracle.py)
```

`law.txt` in, drafts out, machine checks, human freeze. The TUI loads only
frozen sets; `tools/lawgen/freeze.py --verify cases/<case>` is its entry point.
See the `law-extraction` spec for the gate.

## The world vs the law

One hamlet, one people, one present — populated once, before any law:

- `framework/world.ttl` holds who and what the hamlet *has*: the citizen
  roster, the hamlet, townhall, ballot box, registry, board, mailboxes, the
  paper supply, instruments, and the single `ph:Clock` individual. Reviewed
  and frozen once (`framework/world.freeze`); the clock's *reading* is
  runtime-owned and excluded from the hash, only its identity is pinned.
- `population.ttl` holds what the law *derives*: its calendar, its process
  instances, its states and its roles. It references world individuals by
  IRI and never restates them — a case declaring a world-owned IRI fails
  the gate the way restating a shared class does.

Placing an individual: if the hamlet would still have it with no law in
force (a citizen, a sheet, a mailbox, the present moment), it lives in the
world. If it exists because this law says so (an election cycle, a poll
closing, a role), it lives in `population.ttl`.

`ontology.ttl` holds **no individuals** — it is a frozen schema. Seeded
individuals live in `population.ttl` in the same RDF serialisation, and
individuals created during simulation are minted into the runtime knowledge
graph. A law may also mint further `ph:CalendarPoint` / `ph:CalendarSpan`
individuals during `apply`: the frozen calendar is a seed, not a ceiling, so a
process that schedules work at a moment not fixed at review time still has a
displayable calendar. Only Lean computes a minted individual's date or day
index.

## The knowledge graph is the snapshot

There is no bespoke JSON state object. `check` and `apply` exchange **typed
instance triples** — the ABox — and the ontology's class declarations *are* the
schema. Only the ABox crosses the wire; the TBox never does.

### Wire format

```json
{"graph": [
  ["<subject-iri>", "<predicate-iri>", "<object-iri>"],
  ["<subject-iri>", "<predicate-iri>", {"lit": "Announce, Jan 2", "type": "string"}]
]}
```

- An IRI is a bare JSON string; a literal is `{"lit": ..., "type": ...}` where
  `type` is the XSD datatype local name (`"string"`, `"integer"`, `"boolean"`,
  `"date"`).
- **The list is unordered.** Nothing may depend on the order triples arrive in,
  so two round-trips of one graph produce byte-identical verdicts — including
  the order of a violation witness's `refs`. `tests/test_client.py` asserts
  this by permuting the wire.
- `apply` returns the **whole** graph: the graph you sent, extended by the
  encoding of whatever the act changed. Individuals that existed and did not
  change are still there, unchanged; individuals that changed carry their new
  values; individuals that came into being appear with the declared properties
  of their class. The consumer **replaces** its stored graph with the one
  returned rather than splicing it into what it already holds — not because the
  oracle merges, but so the consumer never reconstructs a graph the oracle did
  not send. A returned subject typed by a class the ontology does not declare —
  or carrying no type at all — is an error, and it is an error *before* any
  write, so a rejected graph leaves the store untouched.

### Lifecycle and identity

A process instance relates to a `Chronoid` by `ph:hasTime`; the Chronoid carries
`gfo-core:temporallyStartedBy` / `temporallyFinishedBy` pointing at
`gfo-light:TimeBoundary` individuals, each denoting one moment (both
`ph:dayIndex` and `ph:atHour`). A **historical** instance carries a finish bound
and an outcome; the current instance is the one without a finish bound. Current
position follows from that declaration, never from an ordering convention like
"the current cycle is the last element".

**The clock is the only carrier of the present.** `ph:Clock` holds it, the
runtime is its only writer, and nothing else in the graph carries a position:
`ph:dayIndex` and `ph:atHour` are declared on `gfo-light:TimeBoundary`, so they
belong on the clock, on a calendar point, and on a minted bound, and on no
process instance. A process instance's *schedule* is derived from its declared
index and the law's day arithmetic; a *moment it occupies* is recorded on a
bound. Since the clock is the graph's only free variable, an oracle reads it
floored at every moment the graph already records — totality is total over
absurd values, and monotonicity is what stops a rewound clock contradicting a
recorded one.

Every IRI is deterministic from `(case, index)`; a Role is played *by* a citizen
(`ph:playedBy`) *in* a context (`ph:roleIn`).

Every IRI is deterministic from `(case, index)`; a Role is played *by* a citizen
(`ph:playedBy`) *in* a context (`ph:roleIn`).

### Relationship vocabulary

Declared once, each grounded in GFO, rather than reused from GFO directly:

| property | grounding |
|---|---|
| `ph:hasPhase` | `gfo-core:hasSituationPart` |
| `ph:hasParticipant` | `gfo-core:hasParticipant` |
| `ph:hasTime` | `gfo-core:hasTime` |
| `ph:causedBy` | `gfo-core:causedBy` |
| `ph:relates`, `ph:containsRole` | `gfo-light:relates`, `gfo-light:containsRole` |
| `ph:qualityOf` | `gfo-light:qualityOf` |
| `ph:roleIn`, `ph:playedBy` | `gfo-light:roleIn`, `gfo-light:playedBy` |
| `ph:atDate` | `gfo-core:dateTimeValue` |
| `ph:age`, `ph:atHour`, `ph:dayIndex` | `gfo-core:decimalValue` |
| `ph:label` | `rdfs:label` |
| `ph:marksPhase` | grounded **by type**: domain `gfo-light:Chronoid`, `gfo-light:TimeBoundary`, range `gfo-core:Process` |

`ph:marksPhase` is not the inverse of `gfo-core:hasTime`: that relation runs
situation → time and its object is an *individual*, whereas `marksPhase`'s
object is a phase **class** — the frozen shared calendar can name a phase type
but no instance exists yet at review time. It is grounded by declaring GFO
classes as its domain and range instead.

**Sequencing lives in the calendar, not the schema.** No ordering relation
appears between phases: they overlap, so a chain would assert something false,
and the calendar bounds already answer ordering and overlap from one source.
`ph:causedBy` states a *permitted* dependency that a `gfo-core:State` can bring
about in a Process. Whether the State actually holds — and so whether the change
fires — is evaluated only by the Lean guard. Nothing in the artefacts asserts
that a dependency has fired.

## CLI protocol (cold-spawn, stateless)

```
oracle list                      -> {"ecas": [...]}
oracle check < graph.json        -> verdict JSON, exit 0
oracle check < file.json         -> same, reading the graph from a file argument
oracle apply < envelope.json     -> new graph JSON, exit 0
```

`check` reads the graph from a file argument if given, otherwise from stdin;
`apply` always reads stdin. `list` must equal the manifest's ECA ids or the gate
refuses the set. An unknown verb prints usage and exits 2; bad input prints to
stderr and exits 1.

```
$ oracle list
{"ecas":["announce","nominate","prepare","deliver","vote","count","proclaim"]}
```

That is `mayor-2027`, which has no quorum and therefore no repeat:

```
$ oracle list
{"ecas":["announce","nominate","prepare","deliver","vote","count","proclaim","repeat"]}
```

That is `mayor-quorum`. Both serve `deliver`, because both law texts state making
the ballots and carrying them as two separate duties.

`apply` takes an act plus the whole graph, and on success returns the whole
updated graph — not a delta:

```json
{"act": {"eca": "vote",
         "voter": "https://potato-hamlet.example/ontology/citizen/alice",
         "candidate": "https://potato-hamlet.example/ontology/citizen/bob"},
 "graph": [["<subject>", "<predicate>", "<object>"], ...]}
```

A rejected act returns `{"error": "<guard reason>"}` with exit 1 and the stored
graph is unchanged. Reasons name the failed guard: `"quorum not failed"`,
`"already voted"`, `"registry closed"`, `"polls closed"`, `"no candidates"`.

There is no `tick` verb. The driver writes `ph:Clock` directly, because
advancing time is a simulation control rather than a rule and a cold subprocess
spawn on the most frequent interaction would be a latency regression. The cost
is that the clock is untrusted Lean input, which is why `check` and `apply` owe
totality over it — the gate exercises both far outside the law's calendar.

## Verdict schema

```json
{
  "fired": ["vote", "count", "proclaim", "repeat"],
  "pending": {
    "https://potato-hamlet.example/ontology/citizen/alice": [
      {"eca": "proclaim",
       "process": "https://potato-hamlet.example/ontology/election/mayor-quorum-r0"},
      {"eca": "repeat",
       "process": "https://potato-hamlet.example/ontology/election/mayor-quorum-r0"}
    ]
  },
  "phase": "PollsClosed",
  "readings": [
    {"id": "mayor", "kind": "ref",
     "refClass": "https://potato-hamlet.example/ontology/Citizen",
     "value": "https://potato-hamlet.example/ontology/citizen/alice"},
    {"id": "mayorVotes", "kind": "decimal", "value": 1},
    {"id": "quorumHeld", "kind": "flag", "value": false}
  ],
  "violations": [
    {"eca": "quorum",
     "witness": {
       "counts": [{"name": "voted", "value": 1}, {"name": "total", "value": 7}],
       "refs": ["https://potato-hamlet.example/ontology/citizen/ada",
                "https://potato-hamlet.example/ontology/citizen/barnaby",
                "https://potato-hamlet.example/ontology/citizen/bob",
                "https://potato-hamlet.example/ontology/citizen/cara",
                "https://potato-hamlet.example/ontology/citizen/cleo",
                "https://potato-hamlet.example/ontology/citizen/dara"]},
     "detail": "quorum failed: 1 voted of 7, repeat on day 40"}
  ]
}
```

- `fired` — ECAs whose conditions currently hold. Advisory.
- `pending` — citizen IRI → duties owed now. Each entry names its ECA, the
  process **instance** it belongs to, and `choices`: the options available at
  this instant for any parameter the manifest sources from `choices`. That is
  what lets a consumer build a complete act without reading law-specific state,
  so no consumer needs a per-law parameter table.
- `phase` — the current state, resolvable by IRI from a declared
  `gfo-core:State` subclass. Top-level.
- `readings` — the law's results, reported without a verdict field of their own.
  Each carries a law-chosen `id`, a `kind` from the closed set
  `decimal` / `ref` / `flag`, and a `value`. A `ref` reading also carries
  `refClass`, the ontology class of the individual it points at, so the label
  resolves from the graph without knowing the law. **A law with no result of a
  shape emits no reading** — absence is how a consumer learns there is nothing,
  so there is never a null to mistake for a value. The manifest's `readings`
  block declares each one with its id, class, label and template; the gate
  refuses a set where the oracle emits a reading the manifest does not declare.
- `violations` — each carries a structured witness plus a display string. The
  witness names the individuals that break a quantified condition under `refs`,
  and quantities that fell short under `counts`, each count giving a `name` and
  a `value`. That pair suffices for the framework's FOL subset — universal or
  existential over finite sets plus counting — so no law needs a witness field
  of its own. `detail` is for display only.

No field is named for any single process concept, so a law with a genuinely new
result adds a reading rather than a verdict field.

## Transition table

`apply` is the single enforcing path; `check` stays advisory. Each act is
guarded by the same conditions `check` evaluates — a failed guard returns a
rejection naming it instead of a new graph.

| act | parameters | graph effect | rejects when |
|-----|-----------|--------------|--------------|
| announce | — | `announced := true`, start bound stamped on the Chronoid | no authority; announce not due |
| nominate | `citizen` | nomination individual + `CandidateRole` played by that citizen | registry closed; already registered |
| prepare | — | `prepared := true`; one `ph:BallotVote` Role per **sheet**, played by the sheet and `ph:denotes` the candidate, with the candidate's name written as the sheet's own `ph:label` | no authority; prepare not due; nothing inscriptible in the hamlet; a citizen short of paper |
| deliver | `recipient` | `ph:deliveredTo` on that recipient's ballot Roles, naming their mailbox | not yet made, or polls open; no papers for that recipient; no seeded mailbox; already delivered |
| vote | `voter`, `candidate` | vote individual + its roles, and `ph:placedIn` from that ballot to the ballot box | polls closed; already voted; no ballot box in the hamlet |
| count | — | `counted := true` | count not due |
| proclaim | — | `proclaimed := true`, `ph:outcome := "valid"`, finish bound stamped | no candidates; proclaim not due |
| repeat (quorum flavors only) | — | appends a fresh successor cycle (`E+30`, empty registry/ballots/box), marks the void cycle `ph:outcome := "void"`, and **mints that cycle's calendar** | quorum not failed |

One table covers both election flavors because their law texts share
`law.txt:11-13` word for word -- the same two duties, the same ballot box -- and
`mayor-quorum` differs only by the quorum requirement and the repeat it adds.
So `mayor-2027` serves six ECAs and `mayor-quorum` eight; everything else in
this table is common ground.

### A ballot is a meaning a sheet plays, not a thing

`law.txt:11-13` states two duties — the authority must make
the ballot votes, and must put those papers in each citizen's mailbox — so they
are two acts with a real state between them. Three facts, each on the thing it is
about:

| fact | where | register |
|------|-------|----------|
| the marking on the paper | the sheet, as its `ph:label` | physical, present state |
| which candidate it meant | the ballot Role, as `ph:denotes` | contextual |
| whether it reached the mailbox | the ballot Role, as `ph:deliveredTo` | contextual |

The sheet is a reusable physical object: one supply of paper serves every
election, so a later election strikes the old name and writes a new one on the
same sheet. The marking is therefore the sheet's *present* state and holds one
name — re-written, never accumulated. Which candidate an earlier ballot carried is
not lost by that, because it was never on the paper to begin with: it is what that
election's Role denotes.

Delivery is on the Role for the same reason. One supply of paper means a sheet
left in a mailbox by one election is still there for the next, so delivery
recorded against the *sheet* would make the next election's ballots read as
delivered before anyone carried them — and the distribution check would pass on
nothing. A Role's IRI is a function of the occurrence, so scoping delivery to it
is free. A cast vote is different: `ph:CastVote ⊑ ph:Deposit`, and the paper being in the box is a
physical fact, so `vote` records `ph:placedIn` on the sheet.

Nothing physical is minted. `prepare` writes on sheets the seed supplied; if the
registry needs more paper than any citizen has, it refuses naming who is short
rather than conjuring a sheet. That refusal, and the four `deliver` refusals, are
what keep the distribution check meaningful rather than vacuous.

No transition removes an individual. Once a vote is cast or a ballot delivered
it persists, and what a later rule may affect is only how it is counted: when a
finished instance's outcome means its contributions do not count, the outcome
records that rather than anything being withdrawn. Erasure is not a power a law
lacks by policy — it is not a power it has. The gate asserts this as a property,
applying each ECA in turn and confirming every prior subject survives.

On quorum flavors `repeat` is a first-class ECA held by the authority
(mayor-or-oldest, modality `must`). After a void cycle, `check` offers `repeat`
on that citizen alongside the quorum violation; `apply repeat` appends; further
failures chain (`E+30` each) until quorum holds.

Each `check` / `apply` spawns the compiled binary fresh (graph in, verdict out,
exit). No warm or long-lived mode in the prototype.
