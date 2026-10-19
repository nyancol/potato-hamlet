# Proposal

## Why

`mayor-quorum`'s `prepare` act does not do what the law says, and the framework cannot currently express what the law says.

The law text gives the authority two duties. They "must make the ballot votes. That means one paper per candidate for each citizen, so everyone can choose", and they "must put these papers in the mailbox of each citizen", and they "must also put a big closed box, the ballot box, in the townhall". Three physical acts on three kinds of object.

`applyPrepare` is one function that does none of that observably. It computes `fullBallots s.citizens (cur s).candidates` and stores it, so forty `ph:BallotVote` individuals come into existence at once, and `Ballot.mk c.id cand true` sets each one's delivered flag to `true` at construction. The papers are never made as distinct from being delivered; the mailboxes and the ballot box are never touched; nothing is carried anywhere.

Three consequences follow, and the first two are already visible in the shipped artefacts. The delivered flag is set at construction, so the state in which forty ballots exist undelivered is unrepresentable — which is why the framework's missing-ballot witness can only report a shortfall as a count rather than name the paper that never arrived. And because a law may perform no duty on an object the world lacks, the ontology declares `ph:Mailbox`, `ph:BallotBox`, `ph:Townhall`, `ph:ResultsBoard` while `population.ttl` seeds none of them, so the law's duties are on objects the simulation does not contain.

`runtime-time-and-minting-contract` lands the semantics that make the honest version expressible: a transformation is a Role the individual takes on rather than a new individual, an act declares the individuals it acts on and is refused when one is absent, and nothing physical comes into existence that no seed or earlier action accounts for. `shared-physical-vocabulary` lands the stage to draw on. This change is the law that uses both, and it is the first thing that will show whether the two are usable.

## What Changes

- Seed the physical individuals the law's duties are performed on and with: a sheet per citizen per candidate, a pen for the authority, a mailbox per citizen, one ballot box, one townhall, one results board, one registry book. They exist from the start of the run, as ordinary seeded individuals with labels.
- Split `prepare` into the two duties the law states: making the ballot votes, which gives each sheet its Role in the current election and writes the candidate's name on it as a quality of that sheet, and delivering them, which moves each sheet to the mailbox its owner receives it at. The ECA list grows by one; `mayor-quorum` declares a `deliver` ECA the mayor baseline does not.
- The delivered flag becomes ordinary state rather than a constructor argument. A sheet exists, then holds a Role, then is delivered, and each step is a separate act with a separate guard.
- `prepare`'s guard now requires the sheets it acts on to be present, so the act is refused naming a missing one instead of creating forty replacements. That is the first law to exercise the input declaration the prerequisite change adds.
- The missing-ballot witness scenario becomes a fact about individuals: with delivery a separate act, an undelivered ballot is an individual that exists and is not yet delivered, so the witness names the sheet rather than inferring a shortfall from a count.

**Deliberately not changed:** the law text, the calendar, the quorum and repeat rules, the four-year clock, the tie-break, and the phase structure of the election. The nomination window, announce and prepare days, and polls hours are untouched, so the changes that follow stay the ones the law states. No new shared vocabulary beyond what this law's text names, and no Lean change outside this case's `rules.lean`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `law-extraction`: "Machine checks before human review" gains the checks that a transformation act's declared inputs are present, that the law's physical duties have objects to be performed on, and that the seeded physical individuals are typed by classes the law resolves — the gate that would have caught this law's current shape.
- `law-framework`: the quorum requirement's transition table gains the separate delivery duty, so the requirement describing what `prepare` does matches what the law text says.

## Impact

- **`artefacts/mayor-quorum/population.ttl`** gains the seeded physical individuals, which is the first time any law seeds an object rather than a person or a moment.
- **`artefacts/mayor-quorum/rules.lean`** splits `applyPrepare`, adds `applyDeliver` and its guard, and replaces the `Ballot` constructor's `true` with state the oracle tracks. The `Act` type and the `fromJson` decoder gain a variant.
- **`artefacts/mayor-quorum/manifest.yaml`** declares `deliver` with its holder role, modality, and message, so the TUI can offer it without code.
- **`artefacts/mayor-quorum/ontology.ttl`** declares the Role a sheet takes and the quality it acquires; both use `ph:playedBy`, `ph:roleIn`, and `ph:qualityOf`, which were declared and unused.
- **A second law-swap proof.** `law-simulation-tui`'s law-swap scenario currently proves itself on `repeat`, the ECA the baseline lacks. This change gives it a second: `deliver` is likewise absent from the mayor baseline, and it is driven by a player's choice of mailbox rather than by a date.
- **Re-freeze.** The set's hash changes, so `law-simulation-tui` must load the re-frozen set.