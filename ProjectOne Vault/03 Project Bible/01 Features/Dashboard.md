---
title: Dashboard
category: Project Bible/Features
status: draft
version: "0.1"
last_updated: 2026-08-14
tags: [project-bible, feature, frontend, documentation]
aliases: ["11 Dashboard"]
source_pdf: "[[12 Assets/PDF/ProjectOne_11_Dashboard_v0.1.pdf|ProjectOne_11_Dashboard_v0.1.pdf]]"
---

# ProjectOne — 11 Dashboard (Draft v0.1)

## Purpose

The Dashboard is the user's home page and provides an immediate overview of everything that matters.

## Objectives

Allow users to understand the current status of their content business within seconds and quickly access the most important actions.

## Key Components

Recent projects, active AI workflows, notifications, upcoming publications, analytics summary, AI recommendations, cost summary and quick actions.

See also: [[Projects]] · [[Analytics]] · [[Billing]]

## Quick Actions

Create Project, Continue Project, Chat with AI, Upload Files, Review Approvals and View Analytics.

See also: [[AI Chat]]

## Design Principles

Clean, fast, customizable, minimal clicks, no unnecessary information and clear visual hierarchy.

See also: [[Design System]] — the binding UI standard. [[Design Backlog and UI Vision]] holds a long-term Dashboard concept and mockup; it is **informational only** and does not change the components or objectives specified above.

## Success Criteria

A returning user can understand what needs attention and start meaningful work in less than 30 seconds.

> [!note] Implementation status (2026-08-14)
> [[STEP-24 Dashboard]] delivers the **functional foundation** of this screen: recent projects, active workflows, a workspace-wide spend glance, a circuit-breaker warning and quick actions, with notifications, cost summary and AI recommendations honestly stubbed until the domains feeding them exist.
>
> Its **visual design is deliberately provisional.** The final presentation is designed in [[STEP-26 Product Design System Foundation]] and implemented in [[STEP-80 Product-wide UI Rebuild]], so the shipped screen should be read as correct-but-unstyled rather than finished.
>
> The 30-second criterion above is measured against the rebuilt screen, not the provisional one — it is carried as a mandatory gate on [[STEP-26 Product Design System Foundation]], because it measures information hierarchy and the hierarchy is what that step decides.

---

## Navigation

- **Previous:** [[Product Bible]]
- **Next:** [[Projects]]
- **Parent:** [[Project Bible MOC]]
- **Related Notes:** [[Projects]] · [[Analytics]] · [[AI Chat]] · [[Design System]] · [[Design Backlog and UI Vision]] · [[STEP-24 Dashboard]] · [[STEP-26 Product Design System Foundation]]
