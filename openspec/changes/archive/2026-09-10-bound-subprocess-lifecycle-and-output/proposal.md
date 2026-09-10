# Proposal: Bound subprocess lifecycle and output

## Why

The main runner cleans POSIX process groups, but workflow checks and hooks use
separate `subprocess.run` paths. All subprocess paths also retain unbounded
stdout/stderr in memory. A noisy or descendant-spawning command can therefore
exhaust memory or survive a timeout.

## Scope

- Provide one reusable bounded subprocess execution boundary.
- Stream progress while retaining bounded result output and full local diagnostics.
- Apply process-group cleanup and timeout handling to agents, verification,
  workflow checks, and hooks.
- Preserve structured exit, timeout, interruption, and command-not-found states.

## Non-goals

- No shell execution.
- No change to which commands are authorized.
- No provider-specific process behavior.
- No unlimited log retention.

This belongs in the generic execution boundary and is reusable by all adapters.
