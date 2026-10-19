# Design

## Context

The behaviour this change specifies lives in one requirement, `law-extraction`'s **"Assisted generation with pinned prompt"**, and the gap is in the harness rather than in the ontology. The loop itself is hosted by a pi session; this repo ships the harness contracts that session calls, plus a headless CI-only driver that proves them without a credential. The populated world the loop drafts against comes from `shared-populated-world`, a prerequisite change: the session reads the world read-only and drafts only the law overlay. Four facts from the repo shape the approach.

**`redraft.py` renders three prompts and stops.** 68 lines, no model call. It concatenates `prompts/onto-v2.md` + `---LAW---` + `law.txt` for the ontology, and additionally `---ONTOLOGY---` and `---LEAN---` into the later two so each stage sees the earlier output. `--write-drafts` puts them in `artefacts/<case>/drafts/`, which is **not** in `freeze.py`'s `TRACKED`.

**No per-case artefact records an author decision.** `TRACKED` is `["law.txt", "ontology.ttl", "population.ttl", "rules.lean"]` plus the manifest body. Everything decided during authoring is either baked into those files — invisible *as a decision* — or written by hand in a change's `design.md`. The four "Readings settled from the law text" in `mayor-quorum-transformation-rewrite` exist because that was the only place available.

**The gate already refuses an unconverged draft.** Verified by mutating a scratch case: an ontology line `ph:BallotVote rdfs:subClassOf ph:SomethingNobodyDeclared` plus a seeded individual typed by it fails `check_population` — *"is typed … which ontology.ttl does not declare as a class."* Notably `check_grounding` stays **clean** in that case; it examines properties, not class superclasses. So the enforcement lands in the population check, and this change relies on the gate as it is.

**The shared vocabulary now offers named kinds** (`ph:Pen`, `ph:Pencil` under `ph:Inscriptible`), which matters here: a richer vocabulary is precisely what moves a step from *cannot ground* to *can ground*.

## Decisions

**1. The loop reports ungroundable steps and converges when none remain.** Not a general dialogue, and not a review step: the loop terminates on a condition — the extractor's own report is empty — and a draft is not complete until it is. Any looser termination ("the author stopped answering") makes completeness undecidable, and the whole point is that it is checkable.

**2. The threshold is the extractor's own uncertainty, and that is honest.** The framework cannot distinguish a trivial assumption from a load-bearing one — writing the two rewrites, four decisions had to be *argued* rather than detected, and three of them ended in source comments. Any threshold the framework computed would be a guess wearing a rule's clothes. The extractor, by contrast, knows what it does not know, so its self-report is the one signal here that is not a guess. *Alternative considered:* a framework-computed threshold, flagging a step whose translation required choosing between capabilities. Rejected: it would flag exactly the ordinary cases — a law leaving an instrument open *is* a choice between capabilities — and so would generate noise where the process should be silent.

**3. A groundable step is encoded silently, in the declarations.** The example the author gave: a law that says a ballot vote is created without naming a medium gets paper, and "a ballot vote is a Role of a sheet of paper in the context of this election" is written into `ontology.ttl` as an ordinary declaration. Nothing else happens. This is the right home for it *because* the gate already reviews it there.

**4. No record of the exchange is kept.** Considered and rejected: a tracked `clarifications.yaml` holding question, answer and effect; RDF individuals typed by a new `ph:Assumption` in `population.ttl`. Both are worse than nothing, and for the same reason — each duplicates a fact the declarations already carry, which is the error `law-extraction` rejects for seeds. The RDF option is worse still: it puts claims about the *authoring* into the graph of the *hamlet*. What a freeze attests is a property of the artefacts; if the loop converged, the artefacts are the evidence.

**5. One new check is needed, for the shape the existing ones miss — CORRECTED after task 0.2 falsified the original reasoning.** I first concluded no check was required: an unconverged draft names something undeclared, and the existing checks already fail it. Task 0.2 tested that rather than assuming it, across three shapes, and it is **wrong for two of them**.

| shape of undeclared reference | outcome |
|---|---|
| an individual typed by an undeclared class | caught by `check_population` |
| an undeclared property used in the seed | caught by seed parity |
| **a declared class whose superclass nobody declares** | **passed every check** |
| **a property whose `rdfs:domain`/`rdfs:range` names an undeclared class** | **passed every check** |

`check_tbox` asks whether a class *reaches* GFO, and a dangling `ph:` superclass does not disturb that — the class keeps its own grounding while the invented name rides alongside it. And those two missed shapes are precisely what a drafting process produces when it invents a class name and wires it in, so the loop's central guarantee was resting on nothing.

The check is one loop in `check_tbox`, beside the grounding loop already there: **every `ph:` class a declaration names — as a superclass, a domain or a range — must itself be declared** in the merged graph, so a shared class resolves. Only `ph:` names are required to resolve; a GFO class is legitimately external and grounding is what judges it. Mutation-verified on all three missed shapes, and it is worth having independently of this change, since it catches a broken subclass axiom in any draft.

**5a. A malformed artefact set must not crash the gate.** `check.py` drove the oracle from several checks and none guarded the client's own validation, so an undeclared seeded type surfaced as a `traceback` — and `freeze.py` runs the gate first, so the caller saw an opaque crash instead of the finding. Fixed by one `attempt()` wrapper in `run()` rather than three local guards, so a check added later is covered too. *Worth recording as a mistake of my own:* the first version of that wrapper was a no-op, because `attempt("x", f(case))` evaluates `f(case)` eagerly as an argument, outside the `try`. It has to be `attempt("x", f, case)`. Nine call sites were wrong in exactly that way and the guard silently did nothing until the traceback came back unchanged.

**6. The extractor contract is a schema, and the fake serves the headless driver only.** No LLM credential exists in this environment, so a change that only works with one could not be tested. The report handoff is therefore strict and project-owned: a schema file plus a validator for the separate structured `{step, why-ungroundable}` value settled in loop task 0.1, which the pi side binds its report tool to via `outputSchema`. The deterministic fake feeds the minimal headless test driver — CI-only, never user-facing — so the loop's convergence, question round and prompt contract stay provable without a key. The fake must be able to *ask* — a fake that never has questions would make the loop look converged forever, which is the one behaviour most worth testing.

**7. Pi drives the product loop; no loop code lands in this repo.** The pi session owns iteration, questioning and re-extraction (`/draft-law`, schema-bound report tool, headless `check`/`build`/`freeze` wrappers, question UI, continuation guard). `redraft.py` stays a stateless renderer. *Alternative considered:* `redraft.py` drives with pi as the model behind an extractor interface. Rejected: it would need a transport from Python into pi's model and leave two drivers — one product, one test — interleaving passes and asking twice.

**8. Convergence is checkable on both sides by the same validator.** The headless driver and the pi session share the report schema and the gate: "empty report" means the same thing in CI and in-session, and anything else is refused by `check_tbox`'s undeclared-reference check from decision 5. Free-text parsing of model output is not a handoff — a pass that phrases uncertainty politely must not parse as converged.

**9. The session drafts the law overlay, never the world.** Inputs are `law.txt` plus the framework TBox plus the world read-only; outputs are the law TBox, the law-derived seeds (calendar, instances, states, roles), Lean and manifest, referencing world IRIs. Supply is never sized, never asked about, never restated — restating a world-owned individual fails the gate like restating a shared class.

## Risks / Trade-offs

- **[Risk] The loop converges on a wrong answer.** A question asked and confidently answered wrong is worse than a silent guess, because the answer now looks considered. → Mitigation: the answer lands in a declaration a reviewer reads anyway, and it is a *class or a mechanism*, which is exactly the thing a reviewer can check against the law text. This does not eliminate the risk; it moves it to where it is visible.
- **[Risk] The extractor under-reports, judging a step groundable when it is not.** Then the loop converges on a draft that builds and passes, and the guess is invisible. → Mitigation: this is the sharp edge of decision 2, and the only available guard is the gate's existing refusal of undeclared references. A *wrong but declared* guess is not catchable by any check here, and pretending otherwise would be worse than saying so.
- **[Risk] Prompt instructions to report uncertainty produce performative reporting.** A model asked to flag what it cannot do may flag everything, and the loop then interrogates the author about steps that were never in doubt. → Mitigation: the prompt states the threshold in the positive — proceed when a declared capability accounts for the step — and the tests assert that a well-covered law asks **nothing**, which is the failure mode that matters.
- **[Risk] Growing the vocabulary to reduce questions is a treadmill.** → Mitigation: bounded by `shared-physical-vocabulary` decision 9 as amended — kinds under capabilities, no restrictions, no inventory. A concept needing its own capability still asks, which is the signal worth having.
- **[Risk] The pi continuation loops forever.** An unconditional `continue: true` on `turn_end` re-asks a step that comes back ungrounded without end. → Mitigation: the guard against no-progress re-asking (loop task 3.4's rule) lives in the pi extension as a continuation condition, and the headless driver asserts the same rule against the fake.
- **[Risk] A headless pi run has nobody to ask.** In `pi -p` print/JSON mode there is no `ctx.ui`. → Mitigation: the contract is fixed here — a headless run writes drafts plus the strict report and exits non-zero, never invents answers.
- **[Trade-off] The loop is only as good as its host.** The contract is the deliverable here and the fake pins it for CI; pi-side quality (question UI, skill routing, guard wording) is built via pi and reviewed there. Accepted: this change defines what pi calls, not how pi behaves.
- **[Trade-off] `6.3` unblocks against a fake, not a model.** Its verification is of *the prompt's* content, not of a model's behaviour, so a fake is the more faithful thing to verify against. Accepted, and worth saying plainly rather than leaving implied.

## Migration Plan

No existing artefact changes. `redraft.py` keeps its current behaviour unconditionally — it never grew a driver, so there is nothing to keep reachable behind a flag; the three prompts still render exactly as they do today. The world prerequisite (`shared-populated-world`) lands first; this change consumes it.

**World dependency (noted for `shared-populated-world` task 6.2).** This loop takes the shared world as read-only background: the pi session loads `framework/world.ttl` plus the framework TBox alongside `law.txt`, drafts only the law overlay (law TBox, law seeds, Lean, manifest) referencing world IRIs, and never writes the world. No changes were needed on the world side to support this — the reference-by-IRI contract, the strict report shape, and the headless CI driver all landed there complete.

## Recurring questions (input to `shared-physical-vocabulary` decision 6)

Decision 6 of the shared vocabulary left open whether the same local class
appearing across laws is worth revisiting. The loop now answers that with
evidence rather than a guess: a question asked twice is the signal.

Drove the headless driver plus fake against both election laws over the world
fixture (`scripts/test_clarification_loop.py` 4.1 plus the quorum run below).
Both converged to drafts the gate passes. Their pass-0 questions:

- **Delivery round (asked by BOTH laws).** *"They must put these papers in the
  mailbox of each citizen"* — the text states no window and no bearer for
  getting papers into mailboxes, and no declared capability accounts for it.
  The author answer given in-loop ("the mayor delivers into each mailbox
  during the preparation day") lands in the declarations, but the next law
  will ask again: the shared stage has `ph:Deposit` (putting a thing into a
  container) and no notion of a due-windowed delivery round.
- **Sheet→ballot pairing (asked by BOTH laws).** *"One paper per candidate
  for each citizen"* — the text never says how one citizen's papers are
  chosen from supply. `ph:ownedBy` groups the world's sheets per citizen, but
  the pairing rule itself is law-stated, so every election law re-asks it.
- **Voiding (mayor-quorum ONLY).** *"Nominations and ballots from the void
  election do not carry over"* — no declared action un-delivers sheets
  already sitting in mailboxes. Law-specific, correctly asked once.

The two recurring questions are the evidence decision 6 asked for. Per loop
task 6.2 the vocabulary is NOT grown here: a concept needing its own
capability is the signal worth having, and answering it in this change would
convert a question into an assumption without anyone deciding to.

## Open Questions

- **Which pi model, and who holds the credential?** Deliberately not decided here. The contracts are the deliverable; the model and key are pi-side configuration.
- **Where does the pi package live?** In-repo package directory versus a separate repo — decides versioning against `prompts/` and trust via `.pi/settings.json`. Pi-side build question; does not change the contracts here.
