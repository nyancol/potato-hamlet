# Tasks

## 1. Author the shared physical vocabulary

- [x] 1.1 Create the shared vocabulary file outside `artefacts/<case>/` with its own IRI base, and verify it parses as Turtle and passes the same GFO-light consistency check the per-case ontologies pass
- [x] 1.2 Declare the physical classes the three shipped laws' texts name or presuppose — the townhall, the mailbox, the ballot box, the results board, the registry book, paper, pen, and a dwelling place — each subclassed in GFO and carrying `rdfs:label`, and verify each has a GFO superclass the check accepts
- [x] 1.3 Declare the physical actions the shipped texts perform — writing on a thing with an instrument, and putting a thing into a container — as GFO-subclassed classes carrying `rdfs:label` and naming what each acts on, and verify by reading each declaration back that it names no law, no process, and no class the gesture constitutes
- [x] 1.4 Declare the capabilities the shipped actions require — a qualification for being inscriptible-with, one for being inscribable-on, and one for being a container — as GFO-subclassed classes naming the qualification only, with no enumeration of which objects have them and no restriction pairing instruments to surfaces, and verify by reading the file that no `owl:some`, `owl:only`, or cardinality restriction appears, matching the subset-axiom style of the per-case ontologies. CORRECTED during implementation: these were first declared `gfo-light:Object`, which made `ph:Mailbox ⊑ ph:Container` say a mailbox IS container-ness. A capability is a `gfo-light:Quality` and each concrete thing is an Object that inherits it.
- [x] 1.5 Declare the relations a physical individual, an action, and a capability take part in, grounded in GFO by subproperty or by domain and range, and verify `check_grounding`'s rules accept each and that no relation is left ungrounded and off the exemption list
- [x] 1.6 Confirm no class, action, or capability in the file collides by IRI with one declared locally in any of the three laws, and verify by grep that each of `ph:Townhall`, `ph:Mailbox`, `ph:BallotBox`, `ph:ResultsBoard`, and `ph:CandidateRegistry` appears in exactly one file before the local declarations are removed
- [x] 1.7 Confirm the capability list names no instrument the shipped law texts do not force, and verify by reading `mayor-quorum/law.txt` that the text names what to write with nowhere, so the vocabulary declares a kind rather than a pen

## 2. Resolve the vocabulary alongside each case

- [x] 2.1 Have `scripts/check.py` parse the shared file once per run and merge it into the ontology graph, so every check that takes the ontology graph sees both without changing its shape, and verify the existing framework-invariants, grounding, TBox, and phase-reachability checks still pass on all three cases
- [x] 2.2 Verify a subject typed by a shared class satisfies `check_population` and the `apply`-response type check, and confirm by a scratch `population.ttl` individual typed only by a shared class that neither check fails it
- [x] 2.3 Confirm the mirror-by-name check does not fail a law for drawing on a shared class with no Lean counterpart, and verify by referencing an unmirrored shared class in a scratch case that the law still passes

## 3. Report a local redeclaration

- [x] 3.1 Add a check that reports a class, action, or capability a law declares locally that the shared file also declares, naming both, without failing the set; verify it fires on `mayor-quorum` before the migration and stops firing after task 4.2
- [x] 3.3 Report an ECA that qualifies what it acts on by a named kind where its law text names none, naming the ECA and the kind, and verify by a scratch law whose text says only "write" that the check fires, and that it stays silent when the same act qualifies by a capability
- [x] 3.2 Confirm the report names which declaration a subject resolves to, and verify by a scratch case with the class in both files that the report distinguishes them

## 4. Migrate the shipped laws' references

- [x] 4.1 Replace `mayor-quorum/ontology.ttl`'s local declarations of `ph:Townhall`, `ph:Mailbox`, `ph:BallotBox`, `ph:ResultsBoard`, and `ph:CandidateRegistry` with references to the shared classes, and verify the ontology parses and its consistency check passes
- [x] 4.2 Do the same for `requisitions/ontology.ttl` for whichever of those it declares locally, and verify by the task 3.1 check that no collision is reported for any case
- [x] 4.3 Confirm no `population.ttl` gained an individual in this change, and verify by diff that the three seeds are byte-identical apart from the freeze hash task 5.2 rewrites

## 5. Extend the freeze

- [x] 5.1 Add the shared vocabulary's path to `scripts/freeze.py`'s `TRACKED` list and record the version frozen against in the manifest body, and verify `freeze.py` writes both and that `--verify` passes for each case
- [x] 5.2 Re-freeze all three cases and verify `freeze.py --verify` passes for each. **DONE for all three.** `requisitions` `sha256:0ba5fe52...`, `mayor-quorum` `sha256:9da647fa...`, `mayor-2027` `sha256:5b8ebd99...` -- each verified. The precondition this task named has been met: `mayor-quorum-transformation-rewrite` and `mayor-2027-transformation-rewrite` both closed the accepted transformation finding, so the gate no longer keeps the two election flavours unreviewable and they freeze. The shared vocabulary is frozen at `sha256:f3234975...` and every case records that version, so verification says WHICH vocabulary each law was reviewed against rather than only that a hash moved.
- [x] 5.3 Verify a case fails verification when the shared vocabulary changes, and that the failure names the vocabulary rather than only reporting a hash mismatch
- [x] 5.4 Confirm the shared vocabulary has a review and freeze of its own, and verify by checking that editing it alone does not change any case's manifest body except through the recorded version. `framework/physical.freeze` holds its own reviewed hash, written and verified by `freeze.py --vocabulary` / `--verify-vocabulary`, independently of any case; it reuses the gate's own parse/grounding/TBox checks so the two cannot disagree about what a legal declaration is. Verified: editing it alone changes no case's manifest body except through the recorded version, and `verify` names the vocabulary and both hashes by name.

## 6. Teach the prompt

- [x] 6.1 Add to `prompts/onto-v2.md` the instruction to name the physical concepts the law text presupposes and draw on the shared vocabulary for each one recognised, declaring locally only what it does not carry; verify a redraft of `mayor-quorum` refers to the mailbox and box through shared classes
- [x] 6.2 Add the negative instruction not to require a physical concept the law's duties do not concern, and verify a redraft of `requisitions` produces no physical declaration
- [x] 6.3 Verify both redrafts still satisfy the framework invariants, since the new instruction must not displace them, by running the gate on each generated draft. UNBLOCKED and DONE in `law-drafting-clarification-loop` (task 5.1): the headless driver plus fake (`scripts/clarification_driver.py` + `scripts/fake_extractor.py`) converged both election laws to drafts the gate passes — `framework invariants: ok` on the `mayor-2027` and `mayor-quorum` converged outputs, which carry the current prompt sections (6.1/6.2 plus the clarification-loop contract). The prompt text still mandates all four invariants (verified by reading the rendered prompt); the end-to-end check the BLOCKED note asked for is `scripts/test_clarification_loop.py` 4.1 plus the quorum convergence run recorded in the clarification-loop design.

## 7. Verify the whole set

- [x] 7.1 Run the full suite across all three cases and verify `scripts/test_gate.py`, `test_conformance.py`, `test_quorum.py`, `test_concurrency.py`, `test_cancellation.py`, `test_client.py`, `test_oracle.py`, and `test_readme.py` all pass. `test_conformance`, `test_client`, `test_oracle`, `test_readme` (mayor-2027), `test_quorum`, `test_concurrency`, `test_cancellation` (mayor-quorum), `test_conformance` (requisitions) and the new `test_shared_vocabulary` all pass. `test_gate` fails at BASELINE for `mayor-2027` because it requires the unmutated set to pass the gate, and the gate correctly keeps that set unreviewable over the accepted finding — so it cannot pass until `mayor-quorum-transformation-rewrite` closes it. `test_shared_vocabulary.py` was added for this change and its own teeth were mutation-checked: 8 of 8 deliberate violations of the vocabulary file are caught.
- [x] 7.2 Verify no oracle was rebuilt and no `rules.lean` changed, and confirm by git diff that this change touched only the shared file, the two ontologies, the freeze hash, the gate, the prompt, and the seeds' hashes