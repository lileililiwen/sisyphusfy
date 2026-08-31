# Proposal: Interactive permission prompts

## Why

When an agent run reports a permission request or an unresolved choice, sisyphusfy
stops with a `blocked` result and asks the user to resume manually. That is safe,
but it turns every routine permission prompt into a full stop: the user must read
the handoff, re-run `sisyphusfy resume`, and hope the agent picks up where it
left off. For an interactive terminal session this is needless friction — the user
is right there and could just answer.

The tricky part is that the agent process has already exited by the time the
blocked marker is detected (blocked is detected from the run's output after the
process returns). So the answer cannot be piped into the already-dead process.
The supervisor must instead capture the answer and re-engage the agent in a way
that preserves the disposable, fresh-session model.

## What changes

- Add an interactive resolution path for blocked runs. When a terminal is
  available (or `--interactive` is set) and a run is blocked, sisyphusfy pauses
  and presents the blocker to the user, captures the decision (approve / deny /
  free-text answer), and re-runs the agent in the **same iteration** with the
  answer folded into the prompt so the loop continues.
- In non-interactive contexts (piped input, CI, `--json`, or `interactive:
  false`) the behavior is unchanged: stop with `blocked`, report the blocker, and
  print the resume command. The loop must never block waiting for input when no
  terminal is present.
- A privileged or destructive blocker is never auto-approved; the prompt requires
  an explicit user response and the user may deny.

## Non-goals

- No long-lived agent session and no piping answers into a running process. The
  agent is re-invoked (fresh session), consistent with the disposable-loop model.
- No change to blocked detection itself; the marker and priority rules stay.
- No change to the non-interactive `blocked` contract (JSON shape, resume
  instruction).
- No silent approval of privileged or destructive operations, ever.

## Success criteria

In an interactive terminal, a blocked run prompts the user and, on an answer,
continues the loop in the same iteration rather than requiring a manual resume.
In a non-interactive context the run still stops and reports `blocked` without
hanging. There is a bounded number of interactive re-prompts per iteration so a
blocker that cannot be resolved cannot loop forever. Focused tests (with fake
agent commands) and strict OpenSpec validation must pass.
