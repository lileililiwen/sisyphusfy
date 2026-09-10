# Design: Bound subprocess lifecycle and output

## Explore & Reuse

Reuse `runner.run_agent`, `_pump`, `_stop`, progress callbacks, diagnostic log
writing, and hook/workflow result types. Replace duplicated direct subprocess
calls with a shared internal execution primitive; do not make the loop depend
on Git, OpenSpec, or a language runtime.

## Design

The shared primitive will launch commands without a shell, apply a hard timeout,
use a new process session where supported, and terminate the complete process
group on timeout or interruption. It will stream output to the existing
progress sink while retaining only configured bounded stdout/stderr in the
structured result. Full streams will be written to a component-labelled local
diagnostic log when requested.

The primitive will distinguish command-not-found, non-zero exit, timeout, and
interrupt outcomes. Cleanup and reader draining will have bounded grace periods
and will report cleanup limitations on platforms without process groups.

## Verification

Add tests for noisy output, descendants of verification/workflow/hooks, timeout
classification, interruption, command-not-found, and progress preservation.
Run focused tests, full tests, lint/compile checks, and strict OpenSpec validation.

## Approval gate

Implementation requires human approval of this design.
