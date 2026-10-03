---
name: gfo-light-ontology
description: GFO-light and GFO-core upper ontology for OWL domain modeling. Use when modeling entities, qualities, roles, processes, states, or importing w3id.org/gfo-light.
---

# GFO-Light Ontology

GFO-light is a simplified General Formal Ontology (GFO) top-level ontology
for founding domain/application ontologies in OWL.
Use it for Potato Hamlet to give game entities (players, resources,
buildings, hamlet, constitution, Spirit guide) a shared, interoperable
upper structure.

Canonical sources (fetched 2026-09-27 via Firecrawl):

- Spec: `https://w3id.org/gfo-light` (release `2025-10-01`)
- Core spec: `https://w3id.org/gfo-core` (release `2025-10-01`)
- Repo: `https://github.com/Onto-Med/gfo-light`
- User guide: `https://github.com/Onto-Med/gfo-light/blob/main/docs/README.md`
- Full GFO: `https://github.com/Onto-Med/GFO`, `https://w3id.org/gfo`

Citation: Schäfermeier R. et al. GFO-Light: A Simplified Top-Level
Ontology — Introduction and Biomedical Case Studies. MIE 2026.
DOI: `10.3233/SHTI260386`.
Background: Loebe F. et al. (2022). GFO: The General Formal Ontology.
DOI: `10.3233/AO-220264`. License: CC-BY-4.0.

## Import

```turtle
@prefix gfo-core: <https://w3id.org/gfo-core/> .
@prefix gfo-light: <https://w3id.org/gfo-light/> .
@prefix ph: <https://potato-hamlet.example/ontology/> .

# Import one of:
# https://w3id.org/gfo-light          # full light (extends core)
# https://w3id.org/gfo-light/release/latest
# https://w3id.org/gfo-light/release/2025-10-01  # pinned
# https://w3id.org/gfo-core           # minimal only
```

GFO-light extends GFO-core. GFO-core alone suffices as a minimal
top-level. Prefer pinned version IRIs for reproducibility.

## Core Rule

Create domain classes as subclasses of `Continuant`, `Attributive`,
`Situation`, or `TimeEntity` — **the more specific the better**.
Create domain properties as subproperties of GFO-core/light properties
where possible.

Do NOT use GFO-full categories (`Presential`, `Persistant`, `Situoid`,
`Configuroid`, `Stratum`, `Level`) in GFO-light models. GFO-light has
only temporally extended `Continuant`s, not point-like presentials.

## GFO-core Categories

- `gfo-core:Entity` > `gfo-core:Individual` + `gfo-core:Category`
- `gfo-core:Individual` > `gfo-core:ConcreteIndividual` +
  `gfo-core:TimeEntity`
- `gfo-core:ConcreteIndividual` > `Continuant`, `Attributive`, `Situation`
- `gfo-core:Continuant` — 3D objects persisting through time, wholly
  present at each time. Participants in situations.
- `gfo-core:Attributive` — dependent individuals: qualities, relators,
  roles. Link via `hasAttributive / attributiveOf`.
- `gfo-core:Situation` — contextually related attributives.
  Subclasses: `Process` (dynamic, e.g. football match, illness course,
  potato growth) and `State` (static, e.g. end-of-match state, risk state).
- `gfo-core:TimeEntity` > `Chronoid` (interval) + `TimeBoundary`
  (point). Assign via `hasTime / timeOf`, `temporallyStartedBy`,
  `temporallyFinishedBy`, or data shortcuts `dateTimeValue`,
  `startedByDateTimeValue`, `finishedByDateTimeValue`.

Key core relations: `hasPart/partOf`, `hasParticipant/participatesIn`,
`hasSituationPart/situationPartOf`, `leadsTo/resultsFrom`,
`causes/causedBy`, `hasTime/timeOf`, Allen relations under
`temporallyRelatedWith` (`before/after`, `during`,
`temporallyContains`, `temporallyEqual`, `temporallyMeets/MetBy`,
`temporallyOverlaps/OverlappedBy`, `temporallyStarts/StartedBy`,
`temporallyFinishes/FinishedBy`).

## GFO-light Extensions

Continuants (`Continuant` subclasses):

- `gfo-light:Object` — independent social/material entity
  (person, computer, stadium). `InformationObject` subclass for
  symbolic entities (`represents/representedBy`): titles, models,
  code, constitution text.
- `gfo-light:ObjectAggregate` — group forming a unit (team, research
  group). Membership: `hasMember/memberOf` (loose), not `hasPart`.
- `gfo-light:ObjectPart` — dependent material part (part of bone).
  Use `hasPart/partOf` (firm connection).
- `gfo-light:ObjectBoundary` > `Surface` (2D), `Line` (1D),
  `Point` (0D). Assign via `hasOwner/ownerOf`,
  `hasBoundary/boundaryOf` (+ `hasNaturalBoundary`,
  `hasInnerBoundary`). Lines connect points via
  `spatiallyPassesThrough`, `spatiallyStartsOn`, `spatiallyEndsOn`.

Attributives (`Attributive` subclasses):

- `gfo-light:Quality` — inhering characteristic with optional value.
  Two patterns: (a) simple value → domain data property as
  subproperty of `decimalValue/stringValue/booleanValue/dateTimeValue`
  asserted directly on bearer; (b) reified → subclass of `Quality`,
  instance linked via `hasQuality/qualityOf`, values + `hasTime` on
  the instance, joinable to situations via `situationPartOf`.
- `gfo-light:Role` — links player `Continuant` to context
  (object, aggregate, situation, relator). Always model both sides:
  `roleIn/containsRole` (role → context) + `plays/playedBy`
  (role ↔ player). No fixed role subclasses in light; context
  implies functional / social / processual / situational /
  relational flavor. If roles need no lifetime and are not situation
  parts, a plain object property (e.g. `homeTeamOf`) is acceptable.
- `gfo-light:Relator` — reified n-ary relation instance connecting
  players via roles (marriage, winner-loser, relative-location).
  Use `containsRole`, `relates/relatedBy`. Prefer a relator over a
  plain object property when the relation needs an existence time or
  must be a situation part.

Situations: `SituationAggregate` for contextually but not temporally
connected collections (league season, lecture series). Combine
`Process` + `State` members via `hasMember/memberOf`.
`States` contain only static parts; `Processes` may contain static
and dynamic parts. Continuants join via `participatesIn`,
locations via `locatedIn` (e.g. match in stadium).

## Potato Hamlet Mapping

- Player avatar, tree, potato plant, house, fence → `Object`
  (or `ObjectPart` for e.g. house wall firmly attached).
- Hamlet / cooperative / team → `ObjectAggregate`
  (`hasMember` players). Pre-assembly kit → aggregate; assembled
  house → `Object`. Unconnected components merely `locatedIn` case.
- Hunger, energy, health, soil health, water purity, yield →
  `Quality` (simple data-property pattern for current values;
  reified `Quality` subclass when history / validity time matters).
- Farmer, forester, builder, mayor, voter roles; home-team style
  processual roles (harvest participant); scorer-style situational
  roles → `Role` with `roleIn` + `playedBy`.
- Trade, co-housing contract, vote, marriage-analog household →
  `Relator` with relational roles.
- Constitution text, map drawing, Blender model, music track,
  AI texture prompt → `InformationObject` (`represents` building /
  rule). For full content-vs-carrier modeling use IAO / DS-AO.
- Gathering wood, growing potatoes, building, sleeping, election,
  illness course → `Process` (`hasParticipant` players,
  `locatedIn` hamlet plot, `hasSituationPart` halves/phases).
- Post-harvest store state, soil-depleted state, adopted-constitution
  state → `State` (static parts only).
- Season, legislature period, hamlet history → `SituationAggregate`.
- Spirit of the Hamlet readings → `Quality` values + `State`
  snapshots surfaced to players; constitutional procedures
  (propose law, election, dispute) → `Process` classes with role
  restrictions.

## Minimal Example (Potato Hamlet)

```turtle
ph:Player rdfs:subClassOf gfo-light:Object .
ph:Hamlet rdfs:subClassOf gfo-light:ObjectAggregate .
ph:PotatoPlot rdfs:subClassOf gfo-light:Object .
ph:SoilHealth rdfs:subClassOf gfo-light:Quality .  # qualityOf some ph:PotatoPlot
ph:MayorRole rdfs:subClassOf gfo-light:Role .      # roleIn some ph:Hamlet
ph:Harvest rdfs:subClassOf gfo-core:Process .      # hasParticipant some ph:Player
ph:AdoptedConstitution rdfs:subClassOf gfo-core:State .

ph:numberOfPotatoes rdfs:subPropertyOf gfo-core:decimalValue .
ph:harvestOfSeasonA a ph:Harvest ;
  gfo-core:hasParticipant ph:player1 ;
  gfo-light:locatedIn ph:plot7 ;
  gfo-core:temporallyStartedBy ph:seasonStart .
```

## When Applying This Skill

- Ground game mechanics in Continuant / Attributive / Situation
  rather than ad-hoc labels; keep the three Hamlet poles
  (community ≈ aggregates + social roles, individual ≈ objects +
  qualities, environment ≈ plots + qualities + processes).
- Prefer reified `Quality`/`Relator`/`Role` instances when time,
  provenance, or constitution-enforced procedure matters;
  otherwise use lightweight subproperties.
- Validate OWL with the GFO-light consistency tests / reasoner
  before committing ontology changes.
