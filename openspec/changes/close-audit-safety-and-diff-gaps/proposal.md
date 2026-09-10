# Proposal: Close audit safety and diff gaps

Sisyphusfy currently bounds the main agent and verifier processes, but timeout
cleanup does not reliably stop descendants. Its commit allowlist stages selected
paths without proving that unrelated pre-existing index entries will not be
committed. The human CLI also reports task state without the repository state
that an operator needs to review an agent's work.

This change adds process-tree cleanup, makes the commit hook fail closed when
the index contains unrelated staged changes, and adds read-only Git inspection
for status and diffs. The inspection is an adapter boundary: the generic loop
does not depend on Git, while the human CLI can use the adapter when a Git
repository is present. Output is bounded and available as both concise human
text and structured JSON.

## Non-goals

- Sandboxing arbitrary agent commands or restricting their user privileges.
- Automatically approving, committing, pushing, or reverting changes.
- Parsing provider-specific tool events into a universal event protocol.
- Adding a web UI or interactive diff editor.
