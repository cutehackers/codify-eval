# Model-neutral Delegation

Use delegation to gain independent judgment or reduce elapsed time. Do not use it as a default sequence of model handoffs. The workflow must work with any available session or subagent model.

## Ownership

The main agent owns target resolution, scope and risk classification, user communication, approval boundaries, implementation direction, final diff inspection, verification judgment, and the completion claim.

The customer interacts with the main agent only. Subagent creation, model selection, waiting, handoff, result collection, and integration are internal orchestration responsibilities. Never require the customer to open another session, copy a handoff, or manually combine results.

One implementation owner must own all overlapping production and test files. A subagent may implement a non-overlapping task only when the file boundary, return condition, and merge responsibility are explicit.

## When to delegate

Delegate a read-only reviewer when a high-risk change has a durable contract, a public or compatibility boundary, a security-sensitive decision, or a diff whose independent challenge can expose a material error.

Parallelize read-only discovery only when the findings are independent and the main agent can still make one coherent decision. Delegate a mechanical worker only for bounded command execution, formatting, lint, or result collection. Do not delegate contract authority, product decisions, or root-cause judgment to a mechanical worker.

For a local, well-understood change, do not delegate merely to satisfy a role pattern.

## Recommended agent pool

Use the smallest pool that proves the required result. The main agent remains the owner of scope, implementation direction, final diff inspection, verification judgment, and the completion claim.

Use role-based assignments rather than depending on named project agent files:

| Role | Use | Default timing |
|---|---|---|
| Discovery | Map execution paths, contracts, tests, and repository evidence without edits | Parallel before implementation when discovery is non-trivial |
| Review | Independently challenge correctness, security, compatibility, and test coverage | After a contract or diff exists for medium/high-risk work |
| Bounded implementation | Implement a non-overlapping task with explicit acceptance criteria | Only when file ownership and merge responsibility are explicit |

Do not start every role by default. The baseline is the main agent. Add discovery when an independent question will inform the active slice and the main agent has useful work to do alongside it. Add review when risk or independent challenge justifies it. Use a bounded implementation worker only for genuinely parallel, non-overlapping implementation. The main agent normally runs final verification directly, so a separate verifier is not part of the default pool.

## Role selection

The role defines scope, tools, write boundary, acceptance criteria, and return format. Use the runtime's configured model policy; this skill does not assign models. The implementation owner keeps the context needed for coherent decisions.

## Cost and useful parallel work

Before each worker, identify the unresolved question or implementation result, evidence needed beyond current owner checks, and useful owner work that can proceed concurrently. Distinct files alone do not establish independent work: account for shared dependencies, runnable checks and integration. Keep a bounded, understood unit local when a handoff adds waiting without useful parallel work. Preserve independent challenge for material correctness, security or compatibility risks even when it costs more. Bound the assignment by the answer needed, not a general role label.

When a worker returns, use or explicitly reject its evidence before adding another worker. Stop duplicate discovery when the required decision is resolved. Judge elapsed time from request to integrated verified result, and include every worker's tokens and integration work in cost. Fast workers do not imply a faster or cheaper delivery.

## Handoff

Give a subagent only the evidence it needs: task and role, read/write boundary, relevant paths and instructions, affected public seam, acceptance or review questions, current working-tree facts, exact commands it should run, and a stopping condition.

Frame each assignment as a bounded question or deliverable, not a generic request to review. Pass the confirmed relevant paths and tool availability, and distinguish required inputs from optional references. Gather known required inputs together. Resolve a missing optional path or unavailable tool once through an authorized fallback, preserving the original failed result. Include the relevant public guarantees themselves or accessible source locations, exact source revision, dependency readiness, excluded scope and required return format. State evidenced dependency readiness for the worker checkout and documented check options. Do not transfer readiness from a different checkout without matching evidence. Share completed checks with source version and covered outcomes, and identify checks the owner will run. Reuse matching evidence; rerun for a changed source, missing evidence, required independent execution or a concrete counterexample. Worker-scoped or stale results never replace final verification of the integrated source or an explicitly required command. For a reviewer, require evidence locations, user impact, a reproduction or concrete counterexample for actionable findings, and the unverified scope. Do not give the reviewer a desired verdict. Any worker must know it shares the workspace and must preserve others' changes.

The return must separate facts, findings, commands run and results, unresolved questions, and changed files within the runtime's accepted keys and types. A structured transport may require these sections inside one text field; use its schema rather than turning each section into an API field. The main agent evaluates findings against repository evidence, resolves or explicitly defers them according to the active slice, and updates its evidence map. Another delegation or a clean review is not itself implementation progress.

## Two review questions

When independent review is warranted, distinguish these passes:

- **Implementation review:** Does the proposed or implemented change introduce correctness, security, compatibility, or regression problems? Run it when a consequential contract or diff is concrete enough to challenge.
- **Outcome review:** Does the completed slice satisfy the original user outcome and every applicable acceptance criterion through the actual public path? Run it before closing a substantial slice. Include the original contract, current implementation, evidence map, and known limitations. Require the reviewer to identify omitted behavior and evidence that proves less than the claim, even when all tests pass.

Reuse a reviewer for focused corrections, but for consequential closure seek a perspective that has not simply followed the implementation discussion. When feasible and authorized, use a fresh reviewer with the original requirements and necessary artifacts rather than the accumulated rationale or an expected conclusion. Do not add agents just to fill roles. If delegation is unavailable or prohibited, perform a separate local outcome audit and state that it was not an independent review.

The main agent remains responsible for integration, direct verification, and closure. Do not widen an implementation review into an unrelated redesign, or substitute repeated small diff reviews for the outcome review.

## High-risk sequence

```text
Main agent investigates and prepares a reviewable contract or diff
→ Independent reviewer challenges material risks when useful
→ Resolve any consequential user decision that remains open
→ One implementation owner delivers the scoped change
→ Main agent inspects the diff and verifies the risk-triggered checks
```

Review does not approve a change. An implementation result is not a completion claim until the main agent has inspected it and the required verification evidence exists.
