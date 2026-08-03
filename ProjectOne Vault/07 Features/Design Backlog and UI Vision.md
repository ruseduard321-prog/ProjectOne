---
title: Design Backlog and UI Vision
category: Design
status: reference
version: "1.0"
last_updated: 2026-08-03
tags: [design, documentation, frontend]
aliases: ["Design Backlog", "UI Vision", "ProjectOne Design Backlog & UI Vision"]
source_pdf: "[[12 Assets/PDF/ProjectOne_Design_Backlog_Vision_v1.0.pdf|ProjectOne_Design_Backlog_Vision_v1.0.pdf]]"
authority: informational
---

# ProjectOne Design Backlog & UI Vision v1.0

> [!important] This document is **informational only**. It is not a specification, not a Build Plan step, and not authoritative.
> Recorded by owner instruction on 2026-08-03, and binding on how this note is used:
>
> - **It is not a [[Build Plan]] step** and does not create one. No step is added, renumbered or rescheduled because of it.
> - **It does not modify the [[Roadmap]].** Foundation, Productivity and Scale phases are unchanged.
> - **It does not change architecture.** No ADR, no schema, no API, no backend behaviour follows from it.
> - **It does not override any engineering document.** Where it and [[Design System]], the [[Engineering Handbook MOC|Engineering Handbook]] or [[CLAUDE|CLAUDE.md]] appear to disagree, **they win and this note yields** — see [[#Where This Sits in the Hierarchy]].
> - **It is the authoritative long-term UI/UX vision.** Within that single scope — where the interface is eventually going — it is the reference to design against.

## Purpose

This document defines the long-term UI vision for ProjectOne. It is intentionally separate from the engineering roadmap. It must never introduce new architecture, database changes or backend behavior. Its only responsibility is visual quality and user experience.

## Design Philosophy

ProjectOne should feel like a premium AI operating system rather than a generic admin panel. The design language should emphasize clarity, typography, spacing, subtle animations and information hierarchy. Inspirations include Linear, Vercel, Stripe, Raycast, Cursor and Apple professional applications.

See also: [[Design System]] §1–§3 · [[Design System#14. Long-Term Vision]]

## Foundation Rule

Finish Foundation (STEP-26) first. During Foundation, collect design ideas only. After Foundation, execute one dedicated UI Polish sprint that upgrades every screen consistently.

## Dashboard Vision

- AI Provider Status Bar
- Large KPI cards
- AI Spend Overview
- AI Activity Timeline
- Active Queue
- System Health
- Recent Projects
- Usage by Model
- Floating Command Palette (Ctrl+K)

See also: [[Dashboard]] — the Project Bible specification for what the Dashboard *is*; this list is what it should eventually *look like*. [[AI Cost Governance]] is where the spend and usage figures originate.

## Visual Rules

Dark interface, rounded corners (12-16px), restrained color palette, premium typography, consistent spacing, subtle blur, micro-animations (150-200ms), polished empty/loading states, high-quality charts and tables.

> [!note] These are directional, not token values
> [[Design System]] §4–§6 holds the actual scales — spacing, radius, type and the semantic colour tokens — and remains the only source a component may be built against. Where a number here (e.g. a 12–16px radius) does not match a token there, the token wins and the gap is a UI Polish candidate, not a defect in the shipped code. See [[#Where This Sits in the Hierarchy]].

## Implementation Policy

Only presentation may change. Business logic, APIs, authentication, AI routing, database schema, billing and architecture must remain untouched. This document is a design backlog, not a roadmap step.

## Concept Mockup

A single concept mockup of the Dashboard accompanies this document, illustrating the vision above as one composed screen.

![[ProjectOne_Dashboard_Concept_Mockup_v1.0.png]]

It is a **concept**, not a specification: the data, projects, figures and provider names shown are illustrative, and nothing in it constrains the Dashboard's implementation. Note in particular that it depicts navigation destinations with no scheduled build step — Media Library, Agents, Calendar — and features (notifications, command palette) that no step currently delivers. That is expected of a long-term vision and is not a gap in the [[Build Plan]].

---

## Where This Sits in the Hierarchy

Recorded here rather than left to be inferred, because a vision document with an ambiguous rank is one that eventually gets treated as a specification.

[[CLAUDE|CLAUDE.md]]'s source-of-truth hierarchy is unchanged by this note: **Engineering Handbook → CLAUDE.md → Project Bible → ADRs → code.** This document sits *outside* that chain as a reference input, not inside it as a new tier.

| Against | Outcome |
|---|---|
| [[Design System]] | Design System wins. It specifies; this note aspires. |
| [[Engineering Handbook MOC\|Engineering Handbook]] · [[CLAUDE\|CLAUDE.md]] | They win, without exception. |
| [[Project Bible MOC\|Project Bible]] (e.g. [[Dashboard]]) | Project Bible wins on *what a feature is*. This note speaks only to *how it should eventually look*. |
| [[Roadmap]] · [[Build Plan]] | They win on sequencing. This note schedules nothing. |
| Shipped code | Neither overrides the other during Foundation — see the policy below. |

Its authority is real but narrow: **on the question "where is the interface ultimately going?", this is the answer to design toward.** On every other question it defers.

## Implementation Policy During Foundation

The document's own Foundation Rule, restated as the operating instruction it becomes for [[Build Plan]] steps STEP-19 through STEP-26:

- **Reference only.** Steps STEP-19–STEP-26 may consult this note for direction. They build against [[Design System]].
- **Do not redesign existing pages because of this document.** A screen already shipped is not out of compliance for failing to match a vision explicitly scheduled for later. Rework triggered by this note during Foundation is out of scope under [[CLAUDE|CLAUDE.md]] §29 and §35.
- **Collect, don't act.** Where a Foundation step surfaces a concrete UI improvement traceable to this vision, record it in [[#UI Polish Backlog]] below and continue. Collecting is the instruction; acting on it is not.
- **After Foundation, it leads.** Once [[STEP-26 First Public Release]] is `Done`, this becomes the primary reference for a dedicated **UI Polish phase** that upgrades every screen in one consistent pass — one sprint rather than screen-by-screen drift, which is the whole reason for deferring it.

The reasoning is worth keeping: polishing screens while the surfaces beneath them are still being built means polishing twice, and a consistent visual pass is only possible once there is a complete set of screens to be consistent *across*.

## UI Polish Backlog

Candidate improvements collected during Foundation, each traceable to this vision. **Nothing here is scheduled**; this is a collection point, not a queue, and it is read by the UI Polish phase after [[STEP-26 First Public Release]].

| # | Candidate | Source | Raised by |
|---|---|---|---|
| — | *(none collected yet)* | — | — |

To add an entry: name the improvement, link the section of this note it traces to, and name the step that surfaced it. Do not implement it.

---

## Navigation

- **Previous:** [[Design System]]
- **Next:** —
- **Parent:** [[Design MOC]]
- **Related Notes:** [[Design System]] · [[Dashboard]] · [[Frontend Architecture]] · [[Roadmap]] · [[Build Plan]] · [[STEP-26 First Public Release]]
