---
name: codify
description: Deliver authorized code changes with bounded discovery, consequential decision checks, and evidence for behavior, security and recovery. Use $codify from a clear request or approved contract through verified delivery.
---

# Codify

Preserve the requested scope, public contracts and unrelated work. Finish the original behavior with evidence that covers its risks.

## Locate the change and resolve decisions

Start from named entry points. Gather confirmed governing instructions, dirty status, relevant source, interfaces, callers and tests in one bounded read, including this entrypoint when possible. Check optional instruction paths without allowing their absence to stop required reads. Resolve an unknown path or unavailable tool once through an authorized fallback, then gather the remaining known inputs together. Include line numbers when locations will be needed. Reuse unchanged source, requesting only missing ranges or changed hunks instead of another complete rendering. Expand only for a concrete unresolved dependency or decision, and stop discovery when the edit boundary and acceptance checks are understood. Distinguish enforced interface limits from adjustable output budgets. Capture necessary evidence with an authorized budget, splitting when a limit or missing evidence requires it.

Ask one bundled question only when an unresolved choice affects public behavior, persistence, authorization, security, money, destructive effects, compatibility or acceptance. Preserve the answer and existing authorization. Keep other assumptions narrow, reversible and visible.

Read [references/specification.md](references/specification.md) for specification, slicing, approval or amendment work. Proposed or review-pending durable slices remain ineligible even when their parent is approved. Preserve amendment resets and required independent review. Use [references/intent-interview.md](references/intent-interview.md) for unresolved intent and [references/delivery.md](references/delivery.md) for sustained slices or a specific delivery/coverage question that this entrypoint cannot resolve. Read only the relevant section. Ordinary implementation, verification and final reporting use the guidance here without loading that reference by default, adding approval or creating a document.

## Choose checks that resolve real gaps

Before writing tests, map acceptance and applicable risks to existing checks. Reuse adequate coverage. Add checks for uncovered outcomes, boundaries or failure paths. Record this mapping compactly in working notes or an existing task record, without creating a separate deliverable.

Required evidence depends on the change:

- Public behavior, shared contracts and callers: behavioral checks, affected regressions and required build/static checks.
- Trust boundaries: invalid or hostile inputs, denial before side effects, containment and safe error output where applicable. At external or injectable boundaries, verify successful outputs against the public format, authorization and reporting guarantees before writes or final success. Check that returned metadata agrees with committed state. Use defined failure behavior without inventing an error code or validation order.
- Persistence: validation before writes, preservation and recovery after partial failure, and compatibility for changed formats.
- Async work: applicable ordering, concurrent ownership, late results, backpressure, cancellation and failure recovery.
- Repository policy: every required command whose trigger applies.

Choose cases by distinct behavior, validation branch, error precedence or state transition. Preserve explicit required examples and adversarial cases. Distinct boundary values, hostile input classes and async interleavings can expose different failure mechanisms even when they expect the same outcome. Keep those cases without requiring a defect to be observed first. Avoid equivalent repetitions only when they add no distinct requirement or plausible failure mechanism. Do not impose a numeric test cap, skip applicable risks or treat a test count as proof of coverage.

For negative cases, satisfy earlier preconditions so the intended branch is exercised. Derive expected errors from the public contract. When repairing test infrastructure, preserve the intended invalid input and verify the branch still exercised. A case that now fails for a different reason leaves the original coverage gap open. Establish focused Red when practical. Dependency, compilation and timeout failures alone are not Red. Reuse the project's test harness and import conventions rather than assembling a parallel harness. Async tests must bound their full lifecycle, assert relevant immediate effects and settle or cancel started work even when an assertion fails.

## Implement, verify and close

Confirm dependency readiness for this checkout and source revision. Reuse valid installed dependencies with documented check options that avoid resolving them again. Prepare genuinely missing dependencies once through documented commands, without unauthorized manifest or lockfile changes. Retain every explicitly required setup and verification command. After a dependency timeout, inspect readiness and the documented environment or cache mode before another resolution attempt. Make implementation and necessary tests one coherent change. Apply targeted edits that preserve untouched declarations. Format the edited range when supported. If a formatter changes unrelated declarations, restore them before verification. Inspect changed hunks against the starting scope and contracts before running focused and required affected checks. Retain each exit status and stop on failure. An earlier failing command must not be hidden by a later successful command.

Use the supplied command interface, literal-argument example and documented payload keys and types. Semantic report sections are not API fields. Put findings, command results and limitations into the allowed report fields without inventing keys. Resolve a consequential missing interface detail before a dependent call, using authorized documentation or the interface response. Keep an inner shell command one argument and check both outer and inner shell expansion before dispatching source or assertions. JSON serialization is not shell quoting. Use serialization for the receiving parser and shell quoting for each shell argument without adding an extra shell layer. Only a confirmed pre-dispatch rejection proves a command did not execute. Otherwise inspect receipts and state before retrying, and preserve interface restrictions during recovery.

Choose waits suited to expected runtime. If a session is returned, observe that same handle with meaningful intervals. A polling timeout does not authorize restarting. Classify behavior, environment and evidence-collection failures before changing code.

Plan the final required verification command to also report changed files, whitespace and status, and remove only authorized generated files created by this task after successful checks. Keep each exit status visible and stop dependent steps on failure. Retain required evidence and settle asynchronous work before cleanup. A separate cleanup-only call is unnecessary when its permitted paths and order were already known. If cleanup needs a new decision, or verification fails, keep it separate. After checks pass, add evidence only for a new edit, failure, repository requirement or concrete uncovered risk. Reuse unchanged hunk inspection and check results. New source edits still require inspection and affected verification.

Delegate for consequential independent judgment or useful parallel work with independent dependencies and distinct file ownership. Preserve explicitly required reviews and independent challenge for material correctness, security, compatibility or persistence risks. Before dispatch, include the relevant public rules themselves or a confirmed accessible location, current source revision, confirmed input paths and tool availability, the specific question and decision affected, read/write boundary and stopping condition. Clause labels alone are insufficient. Include interacting guarantees needed to judge the assigned risk. Ordinary bounded read-only review can use this entrypoint. Read [references/orchestration.md](references/orchestration.md) for multiple workers, write ownership, or consequential closure. Keep one owner of scope, overlapping edits, diagnosis, integration and completion. Use or explicitly reject each contribution. Count workers, failures, waiting, review and integration in total cost and time, and follow the runtime model policy.

Tell the reviewer which checks the owner has completed or will run. For completed checks, identify source revision, covered behavior, actual runner and result. Planned checks remain unverified. Ask the reviewer to challenge uncovered risks and reproduce actionable findings. Reuse matching results unless independent execution is required, source changed, evidence is missing or a concrete counterexample warrants another check. Never attribute an owner-run check to the reviewer. Worker-scoped evidence does not replace final verification of the integrated source.

Confirm every original acceptance criterion against current evidence. Report delivered behavior, actual checks, assumptions and gaps. Distinguish proposed, approved, implemented and runtime-verified work. Required checks not executed leave completion open.
