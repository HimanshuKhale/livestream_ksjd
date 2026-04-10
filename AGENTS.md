# AGENTS.md

## Project purpose

This repository is a Django-based live cricket scoring and analytics MVP.

The product has two layers:

1. **Operational scoring layer**
   - match setup
   - innings setup
   - ball-by-ball event entry
   - public live scoreboard
   - scorer-friendly workflow

2. **Analytics and intelligence layer**
   - structured APIs for match, player, and team analytics
   - selector-facing insights
   - spectator-facing live insights
   - later: chat, reports, cards, and computer vision

The current priority is to make the **scoring engine and scoring console robust** before expanding analytics or AI features.

---

## Architecture expectations

- Keep the project in Django.
- Keep Django templates for the current MVP.
- Prefer incremental refactors over rewrites.
- Do not break existing routes unless explicitly required.
- Preserve the current domain model unless a change is justified and documented.
- Business logic should live in small reusable helpers/services, not bloated views or templates.
- UI changes should preserve existing backend behavior unless the task explicitly changes the workflow.

---

## Current source of truth

The scoring flow should revolve around these core concepts:

- `Match`
- `Innings`
- `Team`
- `Player`
- `BallEvent`

`BallEvent` is the key event model and should remain the source of truth for scoring progression.

---

## Product direction

The scorer console must evolve from a generic CRUD form into a **workflow-driven live scoring console**.

The scoring workflow should support:

- next-ball defaults from previous events
- over and ball progression
- striker / non-striker persistence
- strike swapping based on ball outcome
- wicket-driven next batter suggestion
- bowler persistence within over
- bowler reset on new over
- admin override at all times

The operator experience matters more than visual flash.

---

## UX priorities

Optimize for:

- fast scoring during a live match
- low operator error rate
- clear grouping of actions
- visible current state
- visual selection where useful
- graceful fallback to standard form controls

The innings scoring page should eventually have:

- a compact top summary bar
- a workflow-oriented scoring console
- delivery / wicket / shot-location grouping
- a previous-ball context card
- clickable selectors for field zone and pitch zone
- visual shot-type selection

---

## Coding preferences

- Write clear, readable, idiomatic Python.
- Keep functions small and single-purpose.
- Add targeted comments only for non-obvious logic.
- Avoid unnecessary abstraction.
- Prefer explicitness over cleverness.
- Preserve admin override even when automation is added.
- Prefer server-side correctness first, then frontend convenience.
- Use lightweight JavaScript enhancements where helpful.
- Do not introduce a large frontend framework for this phase.

---

## Validation expectations

The scoring system must guard against invalid states.

Examples:

- striker and non-striker cannot be the same
- bowler cannot belong to batting team
- dismissed player must be one of the active batters
- wicket type is required when wicket fell is true
- next batter suggestions must not reuse dismissed batters
- over and ball progression must remain valid
- wides/no-balls should not incorrectly increment legal-ball progression

If a validation rule is added, make the error user-friendly.

---

## Constraints and do-not rules

- Do not remove current match/innings creation flows.
- Do not redesign the entire project structure unless asked.
- Do not add heavy external dependencies without justification.
- Do not add speculative AI features in a scoring-engine task.
- Do not build analytics features on top of broken scoring logic.
- Do not hide important operator controls behind automation.
- Do not assume perfect cricket rules without checking current repository behavior and task scope.

---

## Preferred implementation style for complex tasks

For complex or ambiguous tasks:

1. inspect the relevant files first
2. identify the current behavior
3. propose a plan
4. implement incrementally
5. summarize changed files, logic, and limitations

If the task is large, break it into milestones and complete the most foundational milestone first.

---

## Testing and verification

When making scoring changes, verify at least these flows:

1. first ball of innings
2. normal legal delivery, no wicket
3. odd runs causing strike swap
4. even runs preserving strike
5. over-end logic
6. wicket flow
7. wicket with next batter suggestion
8. wide/no-ball not incrementing legal balls incorrectly
9. bowler persists within over
10. bowler resets at start of new over

If there are no automated tests yet, still describe how you manually verified the flow.

---

## Done means

A change is complete only if:

- the code is readable
- the behavior is correct for the defined flow
- existing routes still work
- templates render without breaking forms
- core validation is preserved or improved
- the implementation is summarized clearly

---

## Important repository focus right now

Current top priority order:

1. scoring state engine
2. scorer console workflow redesign
3. conditional wicket/extras flows
4. visual selection for shot/pitch/zone
5. scoring APIs
6. analytics APIs
7. reports / cards
8. chat and CV later

If a task conflicts with this order, prefer strengthening the scoring foundation first.