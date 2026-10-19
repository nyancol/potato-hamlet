---
name: drafting
description: Grounding guidance for drafting Potato Hamlet law artefacts. Use when extracting ontology, Lean rules, or manifest drafts from a law text, or when judging whether a law step is covered by the shared vocabulary and world.
---

# Drafting guidance

You advise extraction passes. You never drive iteration: the `/draft-law`
command owns the loop, asks the questions, and decides convergence.

## What grounding means

A law step is grounded when you can translate it by choosing among the
objects and capabilities the shared vocabulary (`framework/physical.ttl`)
already declares, acting on individuals the shared world (`framework/world.ttl`)
already contains. Name the declaration that carries each choice.

## Capability, not kind

Where the text leaves an instrument open, qualify by CAPABILITY
(`ph:Inscriptible`), not by a named kind. A hamlet stocked with pencils is
not blocked by a class its law never mentioned. Qualify by a named kind
(`ph:Pen`, `ph:Pencil`) only where the text names it.

## The positive threshold

Where a declared capability accounts for the step, proceed and declare
against it, and do not report it. A well-covered law reports nothing:
silence on a groundable step is correct, and reporting everything is the
failure mode. Report only the step no declared object, capability, or
action accounts for, as `{step, why-ungroundable}`.

## Invent nothing to stay silent

Never invent a mechanism in order to avoid reporting a step. An invented
class is checkable and a concealed guess is not: a name wired into a
superclass, domain, or range fails the gate by name, while a guess hidden
inside a plausible declaration builds, passes, and reads as if the text
determined it.

## Seeds by reference

Law-derived seeds (calendar, instances, states, roles) reference world
individuals by their full IRIs and never restate a world-owned individual.
A restated IRI fails the gate the same way a restated shared class does.
