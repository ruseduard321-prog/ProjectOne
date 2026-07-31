---
title: "Deployment Checklist - {{release}}"
category: Deployment Checklist
status: draft
version: "1.0"
last_updated: "{{date}}"
tags: [deployment]
---

# Deployment Checklist — {{release}}

Per [[Deployment Strategy]].

## Pre-Deployment

- [ ] Automated tests passing
- [ ] Security review complete ([[Security Architecture]])
- [ ] Performance verification complete
- [ ] Staging validated

## Deployment

- [ ] CI/CD pipeline green
- [ ] Migrations applied ([[Database Standards]])
- [ ] Feature flags configured

## Post-Deployment

- [ ] Health checks passing
- [ ] Monitoring/alerting confirmed
- [ ] Rollback plan verified

## Rollback Plan

---

## Navigation

- **Parent:** [[09 Development]]
- **Related Notes:** [[Deployment Strategy]] · [[Infrastructure]]
