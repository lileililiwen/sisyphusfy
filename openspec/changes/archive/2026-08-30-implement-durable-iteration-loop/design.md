# Design: Durable Iteration Loop

## Explore & Reuse

Reuse the archived minimal runner's `run_agent` process boundary and `RunResult` classification. Add orchestration around it; do not duplicate subprocess handling or add agent-specific behavior to the loop engine.

## Architecture

Add a loop service that loads a generic configuration, asks a state adapter whether work remains, renders a short prompt, invokes one agent attempt, runs optional verification, and persists a bounded run record. State adapters expose `has_work`, `snapshot`, and `changed`; the first implementation supports a configurable external completion command and Markdown checkbox strategy.

The loop starts a fresh process for every attempt. It never restores an agent conversation. A provider/process failure may return `RETRYABLE`; task failure, permission/choice blocking, unchanged state, and verification failure stop with explicit classifications.

## Safety and verification

Every agent and verification process has a timeout. No permission prompt receives a guessed answer. Tests use fake commands and temporary workspaces. The loop must be deterministic without network services or a real project layout.
