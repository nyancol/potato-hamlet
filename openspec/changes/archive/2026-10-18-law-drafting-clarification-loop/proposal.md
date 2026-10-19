# Proposal

## Why

Turning a law text into artefacts is one-shot, and the one shot is a person.

`scripts/redraft.py` renders three prompts — `onto-v2.md`, `lean-v1.md`, `manifest-v2.md` — with the case's inputs appended, and stops. Its own closing line is *"next: produce drafts, save as ontology.ttl/rules.lean/manifest.yaml, run scripts/check.py"*, and its docstring says *"No LLM API call here — the human (or a later agentic loop) pastes the rendered prompt."* There is no later agentic loop.

So the process has no way to say **I don't know how this law's step works in the physical world**, and no way to be told. It guesses, the gate catches whatever the guess broke, and the human works backwards from a diagnostic to the question the extractor should have asked. That gap is why `shared-physical-vocabulary` task 6.3 has been blocked: it wants to verify the shared-vocabulary prompt section against a generated draft, and no draft is ever generated.

The guessing is not hypothetical, and it is not visible. Four decisions in `mayor-quorum` and `mayor-2027` were not determined by `law.txt` at all: whether a *sheet* carries an owner or the ballot Role does; which of fifteen unowned sheets becomes whose ballot; the window in which delivery is due, which the law never states; and whether delivery gets a calendar span. Every one produced a law that built, passed the gate, and read plausibly. Three of them were argued in source comments after the fact. **A reader of the frozen artefacts cannot tell any of them from a decision the text did determine.**

## What Changes

- **Generation becomes a loop, driven by a pi session.** The extractor reports the steps of the law text it cannot translate into the physical world; the session puts them to the author as questions; the draft is not presented as complete while any remain. The loop lives in pi, not in this repo: `redraft.py` stays a stateless renderer and this change ships the contracts the session calls.
- **The threshold is the extractor's own uncertainty.** A step it *can* ground — by choosing among the objects and capabilities the shared vocabulary already declares, acting on individuals the shared world already contains — is encoded as an ordinary declaration, silently. The law's text leaving an instrument open is a decision the ontology makes, not a question the author answers.
- **No record of the exchange is kept.** An answer belongs in the declarations it changed. A sidecar of questions would duplicate facts the artefacts already carry, which is the error `law-extraction` already rejects for seeds — *"a value no condition consults is a description of nothing the law permits."*
- **A runnable loop with a headless test double.** The product loop runs in pi, which needs a credential this environment does not have — so the loop's convergence, question round and prompt contract stay testable here through a minimal headless test driver feeding a deterministic fake, CI-only and never user-facing, and `6.3` unblocks against it.
- **The populated world is a prerequisite, not a product of the loop.** `shared-populated-world` populates the shared reality once; the session reads it read-only as background and drafts only the law overlay — law TBox, law-derived seeds, Lean, manifest — referencing world individuals by IRI and never restating them.
- **The vocabulary's coverage is what bounds the interruption.** A concept two laws both need and neither finds declared is a question asked twice, and that repetition is the signal that the shared stage is incomplete — which is the concrete answer `shared-physical-vocabulary` decision 6 left open (*"worth revisiting if the same local class appears across laws"*).

**One new gate check, plus a gate that reports instead of crashing.** A loop that stopped early names something undeclared, and two of the three ways it can do so were already refused — an individual typed by an undeclared class fails `check_population`, an undeclared property fails seed parity. But a class naming an undeclared **superclass**, or a property whose `rdfs:domain`/`rdfs:range` names one, passed every check: `check_tbox` asks whether a class *reaches* GFO, and an invented name wired alongside a real superclass does not disturb that. Those are exactly the shapes an extractor produces when it invents a class name, so the loop's central guarantee was resting on nothing. One new loop in `check_tbox` closes it. Separately, `check.py` **traced back** instead of reporting on a malformed set, and `freeze.py` runs the gate first — so the caller saw an opaque crash rather than the finding.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `law-extraction`: "Assisted generation with pinned prompt" gains iteration, the grounding threshold, the absence of a persisted record, and the reliance on existing checks to refuse an unconverged draft. The requirement already covers this behaviour's territory — it is where draft generation is specified — so it is modified rather than added.

## Impact

- **`scripts/redraft.py` stays render-and-stop.** It keeps its rendering, gains machine-readable render output plus the report-schema validator the pi session is bound to, and never grows a loop driver: no loop code lands in this repo.
- **A report schema and validator instead of an extractor module.** The strict handoff — a separate structured `{step, why-ungroundable}` value, never a fenced block in a draft — is owned here as a schema file plus a validator; the pi side exposes the schema-bound tool. The pi extension itself (session command, headless-tool wrappers, question UI, drafting skill) is built via pi, not here: this change defines the contracts it calls, and the deterministic fake serves the headless test driver only.
- **`prompts/onto-v2.md`, `lean-v1.md`, `manifest-v2.md`** each gain an instruction to report ungroundable steps in a form the harness can read, and — equally important — an instruction *not* to invent a mechanism to avoid reporting one.
- **`scripts/check.py`** gains one check — every `ph:` class a declaration names, as superclass, domain or range, must itself be declared — and an `attempt()` wrapper so a check that cannot complete on a malformed set reports rather than crashing. The first version of that wrapper was a no-op (`attempt("x", f(case))` evaluates `f(case)` eagerly, outside the `try`); it is recorded in `design.md` 5a because it is the kind of guard that looks correct and protects nothing.
- **`shared-physical-vocabulary` task 6.3** unblocks, since a draft now exists to run the gate on — verified against the headless driver plus fake.
- **`shared-populated-world` is a prerequisite.** The loop drafts against the world it populates; law overlays reference it and freezes pin it.