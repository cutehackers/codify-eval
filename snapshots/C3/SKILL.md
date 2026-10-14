---
name: codify
description: Deliver a requested code change through evidence-led, risk-adaptive development with focused parallel orchestration. Use $codify when the user wants Codex to take a feature or proposal from intent through verified delivery, with stronger contracts only when the change warrants them.
---

# Codify

Deliver the original user outcome with inspectable evidence. Match investigation, documentation, delegation, and verification to the change's consequences.

## Resolve the target and decisions

Infer the target from the request, explicit paths, discussed artifacts, or the next incomplete work of the active feature. Inspect applicable repository instructions, affected code and callers, public contracts, existing tests, and relevant dirty changes. Preserve unrelated work.

Batch independent reads of applicable instructions, the file inventory, relevant entry points and existing tests when their paths are known. Keep output focused on the affected behavior. Stop discovery when the public path, existing contract, verification commands and consequential uncertainties are understood. Each further read must answer a specific unresolved question. Load a reference only to resolve a current gap.

Before editing, check whether consequential uncertainty is resolved by repository evidence or current user instruction. Ask one focused question only for an unresolved choice that changes public behavior, persisted data, authorization, security, money, destructive effects, compatibility, or acceptance. Present alternatives and their effects together. Record the answer once and continue within existing authorization. Keep other assumptions narrow, reversible, and visible.

## Select the mode

- **Low risk:** Local reversible behavior and clear acceptance. Inspect, implement, run focused verification, inspect the diff.
- **Medium risk:** Shared behavior, multiple modules, or meaningful regression risk. Use a compact implementation contract and verify affected callers and failure paths.
- **High risk:** Public API, data migration, authorization, privacy, money, destructive behavior, or unresolved product decisions. Resolve consequential choices and use a durable contract or independent review when it changes the outcome.

Do not create documents, slices, or approval pauses merely because the request is code work. Explicit requests to specify, slice, amend, approve, verify, or report status select that mode. For durable contracts read [references/specification.md](references/specification.md). For unresolved intent read [references/intent-interview.md](references/intent-interview.md). Preserve their approval and amendment gates.

## Implement and verify

State the behavior to deliver and the checks that prove it in a compact plan. Implement coherent observable behavior rather than splitting every acceptance sentence into a separate cycle. Use meaningful behavioral tests and Red → Green when practical. Avoid tests that duplicate trivial implementation details or speculative abstractions.

Connect each non-trivial change to its public entry point, affected callers, and relevant normal and failure cases. Check the actual trust, persistence, compatibility, and asynchronous boundaries the change affects. For authorization or persistence work, verify denial before side effects, validation before writes, safe error output and recovery after a partial failure. Select evidence for every applicable trigger: focused behavior checks for changed behavior, related regression plus affected build or static checks for shared modules or public contracts, abuse cases for trust boundaries, compatibility or migration checks for persisted formats, and failure-recovery, stability or concurrency checks for asynchronous paths. Follow required repository commands. A known command alone does not establish sufficient coverage. For bounded work, skip the delivery reference only when these triggers and the original acceptance criteria have an explicit verification plan. Read [references/delivery.md](references/delivery.md) for any unresolved coverage or method, or work spanning repeated slices.

Run focused checks first. Broaden for changed behavior, repository policy, failures, or unresolved risk. Reuse evidence for unchanged inputs. Repeat a check only after its inputs or environment change or a concrete unresolved hypothesis requires it. Classify failures as behavior, environment, or evidence collection before changing code. Fix the cause, then recheck the affected path.

For sustained work, track the original outcomes and acceptance evidence. Finish one complete user-visible slice by default. Parallel implementation needs independent dependencies and non-overlapping file ownership. Do not replace an unmet requirement with an easier case. Durable proposed or review-pending slices remain ineligible for implementation.

## Delegate for a specific benefit

Keep one owner of scope, overlapping implementation, failure diagnosis, integration, and completion. Before spawning, identify the independent question, where its answer changes the active decision, and useful work the owner can do concurrently. Delegate for material independent judgment or useful parallel work, not to fill roles.

Provide the minimum task-specific context, file boundaries, evidence expected, and stopping condition. Use or explicitly reject returned evidence before adding another worker. Include all workers and integration in cost and elapsed time. Follow the runtime's model settings. Read [references/orchestration.md](references/orchestration.md) only when delegating. A clean review does not prove delivery.

## Close with evidence

Resolve conflicts in order: current user instruction, approved contract, repository architecture and policy, existing public behavior and tests, then convention. Surface consequential conflicts.

Inspect the final diff and original acceptance criteria. Lead with the delivered behavior, actual checks and evidence, remaining gaps, and any durable artifact. Distinguish proposed, approved, implemented, and runtime-verified work. Required but unexecuted checks leave the corresponding completion claim open.
