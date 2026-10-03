# Artefacts

One directory per law variant: `artefacts/<case>/`.

## Layout

```
artefacts/mayor-2027/
  law.txt        # source governance text (single source of truth)
  ontology.ttl   # GFO-light ontology (draft via prompts/onto-v1.md)
  rules.lean     # ECA conditions + holders as Bool/Prop twins (prompts/lean-v1.md)
  manifest.yaml  # loader + display glue (prompts/manifest-v1.md)
```

`law.txt` in, drafts out, machine checks, human freeze. The TUI (Phase 2)
loads only frozen sets. See the `law-extraction` spec for the gate.

## Snapshot schema (Python -> oracle `check`, JSON)

Flat shape (`artefacts/mayor-2027`, no quorum):

```json
{
  "day": 9,
  "hour": 10,
  "citizens": [
    {"id": "https://potato-hamlet.example/ontology/citizen/alice", "age": 71}
  ],
  "candidates": ["https://potato-hamlet.example/ontology/citizen/bob"],
  "ballots": [
    {"owner": "https://potato-hamlet.example/ontology/citizen/alice",
     "candidate": "https://potato-hamlet.example/ontology/citizen/bob",
     "delivered": true}
  ],
  "registry": ["https://potato-hamlet.example/ontology/citizen/bob"],
  "box": []
}
```

History shape (`artefacts/mayor-quorum`): per-cycle state lives inside a
cycle record; only population (`citizens`) and office (`mayorId`) are
top-level. The current cycle is the last element (invariant: at least one
cycle). Each cycle id equals its OWL `MayorElectionCycle` individual IRI,
deterministic from `(case, index)`; dates derive per index
(`E(k) = 10+30k`, announce `E-10`, prepare `E-1`, polls 9-19 on E-day).
Repeats never shift the 4-year election clock.

```json
{
  "citizens": [
    {"id": "https://potato-hamlet.example/ontology/citizen/alice", "age": 71}
  ],
  "mayorId": null,
  "cycles": [
    {"id": "https://potato-hamlet.example/ontology/election/mayor-quorum-r0",
     "day": 10, "hour": 20,
     "candidates": ["https://potato-hamlet.example/ontology/citizen/bob"],
     "ballots": [],
     "registry": [],
     "box": [{"voter": "https://potato-hamlet.example/ontology/citizen/alice",
              "candidate": "https://potato-hamlet.example/ontology/citizen/bob"}],
     "announced": true, "prepared": true,
     "counted": true, "proclaimed": false, "outcome": "void"}
  ]
}
```

- `day`: Nat day-of-cycle (election day = 10, announce = 0, prepare = 9).
- `hour`: Nat hour on `day` (polls 9-19 on election day).
- Entity ids equal the full OWL individual IRIs from `ontology.ttl`.
- Closed world: the snapshot enumerates the full finite population
  (OWL open-world vs Lean closed-world closure happens at snapshot build).

## Verdict schema (oracle `check` -> Python, JSON)

```json
{
  "fired": ["prepare"],
  "pending": {
    "https://potato-hamlet.example/ontology/citizen/alice": ["prepare"]
  },
  "violations": [
    {"eca": "all_distributed",
     "witness": {"citizen": "https://potato-hamlet.example/ontology/citizen/alice",
                 "candidate": "https://potato-hamlet.example/ontology/citizen/cara"}}
  ],
  "would_win": "https://potato-hamlet.example/ontology/citizen/bob",
  "phase": "BallotsReady"
}
```

- `pending` maps citizen IRI -> list of ECA ids whose holder is that
  citizen and whose conditions hold now.
- `violations` carry machine-readable witnesses plus display strings so
  the guide names what is missing (advisory only; humans decide/act).
- `would_win` is advisory: proclamation stays a human act of the holder.

## Transition table (drivers request through `oracle apply`)

`apply` is the single enforcing path; `check` stays advisory. Each act is
guarded by the same conditions `check` evaluates — a failed guard returns a
rejection naming it instead of a new snapshot.

| act | parameters | snapshot effect | rejects when |
|-----|-----------|-----------------|--------------|
| announce | — | `announced := true` | no authority; announce not due |
| nominate | `citizen` | `registry += citizen` | registry closed; already registered |
| prepare | — | `prepared := true`, full citizen×candidate delivered `ballots` | no authority; prepare not due |
| vote | `voter`, `candidate` | `box += one entry` | polls closed; already voted |
| count | — | `counted := true` | count not due |
| proclaim | — | `proclaimed := true`, `mayorId := winner` (oldest on tie) | no candidates; proclaim not due |
| repeat (quorum flavors) | — | appends a fresh successor cycle (`E+30`, empty registry/ballots/box, void cycle marked and preserved) | quorum not failed |

On quorum flavors `repeat` is a first-class ECA held by the authority
(mayor-or-oldest, modality `must`). After a void cycle, `check` pends
`repeat` on that citizen alongside the quorum violation; `apply repeat`
appends; further failures chain (`E+30` each) until quorum is valid.

## Oracle CLI protocol (cold-spawn, stateless)

```
oracle-mayor list
# {"ecas": ["announce", "nominate", "prepare", "vote", "count", "proclaim"]}
# Quorum flavors append "repeat".
# Must equal manifest.yaml eca ids or the loader refuses the set.

oracle-mayor check < snapshot.json
# verdict JSON per schema above; exit 0. Exit non-zero + stderr on bad input.
# Quorum history shape: {"citizens": [...], "mayorId": null, "cycles": [...]};
# an empty "cycles" list is rejected ("cycles must be non-empty").

oracle-mayor apply < envelope.json
# -> new snapshot JSON, exit 0; or {"error": "<guard reason>"}, exit 1.
# Rejection reasons name the failed guard ("quorum not failed",
# "already voted", "registry closed", ...); the stored snapshot is unchanged.
```

Envelope example (valid JSON as written):

```json
{"act": {"eca": "vote",
         "voter": "https://potato-hamlet.example/ontology/citizen/alice",
         "candidate": "https://potato-hamlet.example/ontology/citizen/bob"},
 "snapshot": {"day": 10, "hour": 12,
              "citizens": [{"id": "https://potato-hamlet.example/ontology/citizen/alice", "age": 71}],
              "candidates": ["https://potato-hamlet.example/ontology/citizen/bob"],
              "ballots": [], "registry": ["https://potato-hamlet.example/ontology/citizen/bob"],
              "box": [], "announced": true, "prepared": true,
              "counted": false, "proclaimed": false, "mayorId": null}}
```

Quorum history-shape envelope (valid JSON as written):

```json
{"act": {"eca": "repeat"},
 "snapshot": {"citizens": [{"id": "https://potato-hamlet.example/ontology/citizen/alice", "age": 71}],
              "mayorId": null,
              "cycles": [{"id": "https://potato-hamlet.example/ontology/election/mayor-quorum-r0",
                          "day": 10, "hour": 20, "candidates": [], "ballots": [],
                          "registry": [], "box": [], "announced": true,
                          "prepared": true, "counted": true,
                          "proclaimed": false, "outcome": null}]}}
```

Each `check`/`apply` spawns the compiled binary fresh (snapshot in, verdict
out, exit). No warm/long-lived mode in the prototype.
