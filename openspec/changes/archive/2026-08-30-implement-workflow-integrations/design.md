# Design: Workflow Integrations

## Explore & Reuse

Reuse the durable loop's state-adapter and verification boundaries. OpenSpec commands are invoked as configured external tools; the core does not import the OpenSpec implementation. Existing handoff files remain user-owned workspace state.

## Architecture

State adapters implement a common protocol: snapshot, has_work, is_complete, and explain. Markdown uses checked/unchecked task markers. JSON uses a configured command or dotted predicate. OpenSpec resolves a change directory and checks its task file plus validation command. Verification runs separately and is never inferred from task text.

## Token and safety policy

Prompt templates reference configured paths instead of embedding full documents. Handoff updates are overwrite-style concise summaries. External commands use argument vectors where possible, have timeouts, and are visible in dry-run output.
