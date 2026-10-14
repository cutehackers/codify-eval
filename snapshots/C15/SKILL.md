---
name: codify
description: Deliver authorized code changes with bounded discovery, consequential decision checks, and evidence for behavior, security and recovery. Use $codify from a clear request or approved contract through verified delivery.
---

# Codify

Preserve the requested scope, public contracts and unrelated work. Finish the original behavior with evidence that covers its risks.

## Locate the change and resolve decisions

Start from named entry points. Batch independent authorized reads of the skill, governing instructions, dirty status, relevant implementation, contracts, callers and available tests. Reading this entrypoint need not occupy a separate command from known task files. Resolve unknown paths through a bounded inventory. Expand only for a concrete unanswered dependency or decision. Stop discovery when the edit boundary and acceptance checks are understood, and reuse observed facts.

Ask one bundled question only when an unresolved choice affects public behavior, persistence, authorization, security, money, destructive effects, compatibility or acceptance. Preserve the answer and existing authorization. Keep other assumptions narrow, reversible and visible.

Read [references/specification.md](references/specification.md) for specification, slicing, approval or amendment work. Proposed or review-pending durable slices remain ineligible even when their parent is approved. Preserve amendment resets and required independent review. Use [references/intent-interview.md](references/intent-interview.md) for unresolved intent and [references/delivery.md](references/delivery.md) for sustained slices or a specific delivery/coverage question that this entrypoint cannot resolve. Read only the relevant section. Ordinary implementation, verification and final reporting use the guidance here without loading that reference by default, adding approval or creating a document.

## Choose checks that resolve real gaps

Before writing tests, map acceptance and applicable risks to existing checks. Reuse adequate coverage. Add checks for uncovered outcomes, boundaries or failure paths. Record this mapping compactly in working notes or an existing task record, without creating a separate deliverable.

Required evidence depends on the change:

- Public behavior, shared contracts and callers: behavioral checks, affected regressions and required build/static checks.
- Trust boundaries: invalid or hostile inputs, denial before side effects, containment and safe error output where applicable.
- Persistence: validation before writes, preservation and recovery after partial failure, and compatibility for changed formats.
- Async work: applicable ordering, concurrent ownership, late results, backpressure, cancellation and failure recovery.
- Repository policy: every required command whose trigger applies.

Choose cases by distinct behavior, validation branch, error precedence or state transition. Preserve explicit required examples and adversarial cases. Distinct boundary values, hostile input classes and async interleavings can expose different failure mechanisms even when they expect the same outcome. Keep those cases without requiring a defect to be observed first. Avoid equivalent repetitions only when they add no distinct requirement or plausible failure mechanism. Do not impose a numeric test cap, skip applicable risks or treat a test count as proof of coverage.

For negative cases, satisfy earlier preconditions so the intended branch is exercised. Derive expected errors from the public contract. When repairing test infrastructure, preserve the intended invalid input and verify the branch still exercised. A case that now fails for a different reason leaves the original coverage gap open. Establish focused Red when practical. Dependency, compilation and timeout failures alone are not Red. Reuse the project's test harness and import conventions rather than assembling a parallel harness. Async tests must bound their full lifecycle, assert relevant immediate effects and settle or cancel started work even when an assertion fails.

## Implement, verify and close

Prepare missing dependencies once through documented commands, without unauthorized manifest or lockfile changes. Make implementation and necessary tests one coherent change. Preserve untouched declarations and avoid formatting outside the intended edit. Inspect final changed hunks, then run focused and required affected checks. Retain each exit status and stop on failure. An earlier failing command must not be hidden by a later successful command.

Use the supplied command interface and documented quoting forms. Keep an inner shell command one argument and check quoting before dispatching source or assertions. Only a confirmed pre-dispatch rejection proves a command did not execute. Otherwise inspect receipts and state before retrying, and preserve interface restrictions during recovery.

Choose waits suited to expected runtime. If a session is returned, observe that same handle with meaningful intervals. A polling timeout does not authorize restarting. Classify behavior, environment and evidence-collection failures before changing code.

After checks pass, stop adding evidence unless an edit, failure, repository requirement or concrete uncovered risk justifies it. Reuse unchanged hunk inspection and check results. Combine independent final status, changed-file, whitespace and authorized generated-state housekeeping with the final verification command when practical. Preserve command failures and stop before dependent steps. New source edits still require inspection and affected verification. Keep output focused on the unresolved question.

Delegate for consequential independent judgment or useful parallel work with independent dependencies and distinct file ownership. Read [references/orchestration.md](references/orchestration.md) when delegating. Specify the question, decision affected, evidence, boundary and stopping condition. Keep one owner of scope, overlapping edits, diagnosis, integration and completion. Use or explicitly reject each contribution. Count workers, failures, waiting, review and integration in total cost and time, and follow the runtime model policy.

Confirm every original acceptance criterion against current evidence. Report delivered behavior, actual checks, assumptions and gaps. Distinguish proposed, approved, implemented and runtime-verified work. Required checks not executed leave completion open.
