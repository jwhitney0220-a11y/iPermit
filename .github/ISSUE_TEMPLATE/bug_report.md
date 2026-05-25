---
name: Bug report
about: Report a defect in iPermit code or behavior (not a regulatory rule issue)
title: "[Bug] "
labels: ["bug", "triage"]
assignees: []
---

<!--
For incorrect, missing, or outdated regulatory data (permit triggers, forms,
jurisdictions, citations), use the "Regulatory rule add/change" template instead —
that path routes to the analyst review queue.
-->

## Summary

<!-- One or two sentences describing the bug. -->

## Affected area

- [ ] Rules engine (`services/rules-engine`)
- [ ] GIS engine (`services/gis-engine`)
- [ ] AI assistant (`services/ai-assistant`)
- [ ] Web app (`apps/web`)
- [ ] Analyst portal (`apps/analyst-portal`)
- [ ] Shared schemas / packages
- [ ] Infrastructure / CI
- [ ] Other (describe):

## Steps to reproduce

1.
2.
3.

## Expected behavior

## Actual behavior

## Environment

- Branch / commit:
- Local, staging, or production:
- Browser / OS (if frontend):

## Evidence

<!-- Logs, screenshots, stack traces, or a minimal failing input. -->

## Severity

- [ ] Blocker — production down or wrong permit output reaching consultants
- [ ] High — major feature broken, no workaround
- [ ] Medium — feature broken with a workaround
- [ ] Low — minor or cosmetic
