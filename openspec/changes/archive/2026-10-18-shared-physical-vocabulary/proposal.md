# Proposal

## Why

Laws are written about physical things and physical doings, and the framework has nowhere to put either.

`mayor-quorum`'s law text says to put the papers "in the mailbox of each citizen", to put "a big closed box, the ballot box, in the townhall", to write results "on the big board", and to "write their name in the candidate registry book". Its ontology declares `ph:Townhall`, `ph:Mailbox`, `ph:BallotBox`, `ph:ResultsBoard`, and `ph:CandidateRegistry` in response. `population.ttl` seeds an individual of none of them. The law's duties are performed on objects the simulation does not contain, and the gap is invisible because nothing checks whether a law's duties have anything to be performed on.

But the objects are only half of it. The law also says what is *done* to them — "one paper per candidate for each citizen", "write these papers in the mailbox", "put their vote into the box" — and the framework has no vocabulary for the doing either. That matters because the doing is what carries the law's meaning: writing a name on a sheet makes it a ballot, and dropping that sheet in the box makes it a cast vote. The same sheet is one physical thing that becomes two different things in two situations, and what it becomes is decided by the law, not by the physics of paper. If the framework supplied only objects, each law would have to invent the verbs as well as the nouns, and two laws that both write on paper would end up with unrelated ways of saying so.

`runtime-time-and-minting-contract` settles what an act may do to an individual that exists — a transformation is a Role in a situation, and an act declares its inputs. That is the semantics. This change is the stage those semantics act on: the physical things, and the actions performable on them, declared once so that a law supplies only what its own text makes of them. Without it, the transformation requirement has nothing to name and the laws that would use it invent the ontology per law, which is the problem the requirement was written against.

## What Changes

- Add a shared physical vocabulary as a framework artefact, available to every law. It declares three things: the **objects** governance texts presuppose — a citizen's dwelling places, the containers and surfaces a duty is performed on, the instruments a duty is performed with; the **actions** that can be performed on an object to change what it is or where it is; and the **capabilities** that qualify an object for an action, such as an instrument being one a thing may be inscribed with. All three are subclassed in GFO and carry `rdfs:label`, and the relations a physical individual takes part in are declared alongside them. An action is declared as the physical gesture it is — writing on a thing, putting a thing into a container — and says nothing about what any law makes of it.
- A capability is declared as a class an instrument belongs to, not as a restriction saying which instrument does which action. The ontology names the kind of thing that can inscribe and the kind that can be inscribed; which particular instruments and surfaces those are, and which combinations work, is left to the oracle to evaluate per act, because an ontology restriction can only say that some such object is involved and cannot say that one can and another cannot. A law's text that leaves the instrument open — "write their names", naming neither pen nor pencil — SHALL NOT be read as naming one, and a law requiring an instrument qualifies it by capability rather than by a named kind.
- The vocabulary is **available, not required**. A law draws on it as far as its text needs, and a law with no physical concerns declares none of it. This is the load-bearing decision: making it required would force `requisitions` to declare a paper and a pen it never mentions, which is a seed it would have to justify and cannot.
- A law needing a physical concept nobody has declared declares it locally. That escape hatch is deliberate and bounded: it keeps the shared vocabulary from having to anticipate every law's nouns, at the cost that such a concept is that law's alone. It is the point at which shared and law-local vocabulary diverge, and it should be visible rather than silent.
- Extend the freeze hash to cover the shared vocabulary, so a case cannot verify while the vocabulary underneath it has moved. Every case's freeze names the shared file it was frozen against.
- Require the shared vocabulary's classes to be usable as the declared inputs of a transformation act, and require a law's act inputs to be typed by a class resolved from either source — the shared file or the law's own ontology — so "available" does not weaken the existing rule that every subject is typed by a declared class.
- Extend the extraction prompt so a drafted law names the physical concepts its text presupposes and draws on the shared vocabulary for the ones it recognises, rather than inventing a class per noun.

**Deliberately not changed:** the transformation semantics themselves, which `runtime-time-and-minting-contract` lands; no law is rewritten here, so `mayor-quorum` continues to create its ballots out of nothing and continues to seed no physical individual — `mayor-quorum-transformation-rewrite` is that work. Also unchanged: the framework invariants that remain mandatory. `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint`, and `ph:CalendarSpan` are not part of this vocabulary, because they are what a law-agnostic consumer operates on rather than what a law's text presupposes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `law-extraction`: the variant layout gains the shared vocabulary as a resolvable source of declared classes, the freeze covers it, the prompt asks for the physical concepts a law's text presupposes, and the gate resolves declared classes from both sources when checking a subject's type.
- `law-framework`: the ontology profile distinguishes classes every law must declare from classes every law may draw on, states that a law-local class for a concept the shared vocabulary could have covered is a divergence to be visible, and adds the requirement that separates what a physical action is from what a law makes of it.

## Impact

- **New framework artefact**, a Turtle file outside `artefacts/<case>/`, holding the shared physical classes, the actions performable on them, the capabilities qualifying an object for an action, and their relations, with a review and freeze of its own. Its IRI base is shared, so a law's `ontology.ttl` references rather than redeclares.
- **`mayor-quorum`'s `inscribe` act qualifies its instrument by capability**, so the act takes an instrument rather than a pen and a hamlet with only pencils satisfies it. This corrects an earlier reading in which the act named a pen, which the law's own text does not say.
- **`scripts/freeze.py`** gains the shared file in its hash and names the version a case froze against.
- **`scripts/check.py`** resolves a subject's type against the merged graph of the law's ontology and the shared vocabulary, and reports a law-local class whose name collides with a shared one.
- **`artefacts/mayor-quorum/ontology.ttl`** and **`artefacts/requisitions/ontology.ttl`** reference the shared classes instead of declaring `ph:Mailbox`, `ph:BallotBox`, `ph:Townhall`, `ph:ResultsBoard` locally. No `population.ttl` gains an individual.
- **`prompts/onto-v2.md`** asks for the physical concepts the law text presupposes.
- **No oracle change.** No Lean changes, no protocol change, no new verdict key.