# Proposal

## Why

`mayor-2027` carries the same defect `mayor-quorum` carried, and it is the last shipped law that does.

`mayor-2027/law.txt:11-13` is **word-for-word identical** to `mayor-quorum/law.txt:11-13`. Both give the authority the same two duties — to "make the ballot votes. That means one paper per candidate for each citizen" and to "put these papers in the mailbox of each citizen" — and both require "a big closed box, the ballot box, in the townhall". So there is nothing new to read here: the readings that change settled from the text settle identically for this law, and they are recorded in `mayor-quorum-transformation-rewrite/design.md` rather than re-derived.

The defect is the same too. `applyPrepare` is one function that computes `fullBallots s.citizens s.candidates` and stores it, so every `ph:BallotVote` individual comes into existence at once and `Ballot.mk owner cand true` sets `delivered` at construction. The papers are never made as distinct from being delivered; no mailbox is touched; nothing is carried anywhere. The gate says so:

```
transformation: `prepare` brought 9 new ph:BallotVote individual(s) into existence,
and it is neither a Role the individual takes on nor an occurrence of a declared
phase, so nothing accounts for it appearing.
```

That finding was **accepted at the close of `runtime-time-and-minting-contract`** as pre-existing, on the grounds that the requirement had to land before the laws that met it. `mayor-quorum-transformation-rewrite` has now met it, so the acceptance has one law left standing on it. This change removes that last one.

Two further reasons this law is not yet freezable, both recorded in the quorum change's task 6.2: its manifest names no shared-vocabulary version, so `freeze.py --verify` cannot say which vocabulary it was reviewed against; and its files changed under the prerequisite change without being re-frozen, so its recorded hash is stale.

## What Changes

- **Seed the physical world.** Mailboxes, one ballot box, the townhall, the results board, the candidate registry book, a supply of blank sheets and an instrument qualified to inscribe — the objects the law's duties are performed on and with, which this law's ontology currently declares none of.
- **Split the duty in two**, exactly as the quorum law was split: making the ballot votes, and putting those papers in each citizen's mailbox. The ECA list grows by one, so `mayor-2027` gains the `deliver` ECA the quorum law now has and the baseline never had.
- **A ballot becomes a meaning a sheet plays.** `ph:BallotVote` becomes a `gfo-light:Role` played by the sheet and denoting the candidate; the name written is the sheet's own `ph:label`. Delivery is recorded on the Role as `ph:deliveredTo`, so it is scoped to the election that carried it.
- **`vote` declares what it acts on.** The ballot box is a named seeded individual, so `vote` declares it, refuses naming it when the world has none, and records `ph:placedIn` from the citizen's ballot to the box.
- **Re-freeze**, with the shared-vocabulary version the manifest was missing.

**Deliberately not changed:** the law text, the calendar, the four-year cycle, the announce and prepare days, the polls hours, the tally, the oldest-on-tie rule, and the election's phase structure. This law has no quorum requirement and no repeat, and none is added — that is the one substantive difference from `mayor-quorum` and it is a difference in the law text, not in the framework.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None required. The framework semantics this law exercises — a transformation is a Role rather than a new individual, an act declares what it acts on and is refused when one is absent, and nothing physical is conjured — are already in `law-framework` and `law-extraction` as archived by `runtime-time-and-minting-contract`. This change is the second law to satisfy them and the first to satisfy them *without* also changing a requirement, which is the point: the requirements do not need rewriting to accept a conforming law.

## Impact

- **`artefacts/mayor-2027/population.ttl`** gains the seeded physical individuals.
- **`artefacts/mayor-2027/rules.lean`** gains an `Owned` structure and four seeded-furniture fields on `Snapshot`, splits `applyPrepare`, adds `applyDeliver` with its `deliverDue?` guard and Bool/Prop theorem, and replaces the constructor's `true` with state read off the graph. The `Act` type and its `fromJson` decoder gain a variant.
- **`artefacts/mayor-2027/manifest.yaml`** declares `deliver`, `acts_on`, `requires: Inscriptible`, and the shared-vocabulary version.
- **`artefacts/mayor-2027/ontology.ttl`** specialises the shared `ph:Inscribe` and `ph:Deposit`, makes `ph:BallotVote` a Role, and declares `ph:denotes`, `ph:deliveredTo` and `ph:ownedBy`.
- **No shared vocabulary changes.** The classes this law needs are already in `framework/physical.ttl`; this change is a consumer of them, which is what they were landed for.
- **Test suites become flavour-aware.** `test_oracle.py` and `check_apply_props.py` currently assume one mayor shape in places; they are corrected to read the shape off the oracle, so a law that has not been rewritten does not fail the suite for another law's rewrite.