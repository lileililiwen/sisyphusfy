# Design: Repair Final Workflow Safety and Specification Integrity

## Explore & Reuse

Reuse the existing `run_agent` subprocess boundary, `run_loop` orchestration, `AgentAdapter` registry, workflow adapters, and completion hook pipeline. Fix their contracts in place; do not add parallel execution paths.

## Corrections

1. Normalize archived `agent-adapters` and `iteration-loop` main specs to the repository's canonical `## Purpose` / `## Requirements` format while preserving all requirements and scenarios.
2. Propagate dry-run through every process boundary. A dry run may inspect configuration and state but MUST not invoke an agent, verifier, workflow check, archive command, or commit command.
3. Implement commit staging as a separate explicit step using canonicalized paths under the configured working directory. Reject empty, escaping, or unrelated paths; invoke the commit command only after safe staging.
4. Construct each fallback attempt from the selected model rather than mutating or reusing a command that contains an earlier model. Preserve a fresh process and no continuation flags.
5. Test named adapters through fake executables that capture argv and stdin. Real provider credentials and network access remain unnecessary.

## Verification

Use failing tests first, then run the complete suite twice, lint, compile, package, full OpenSpec validation, and CLI dry-run smoke tests. Documentation and handoff must report only evidence from these checks.
