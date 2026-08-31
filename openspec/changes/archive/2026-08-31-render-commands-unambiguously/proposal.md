# Proposal: Render commands unambiguously

## Why

Every place that shows a command joins the argument list with plain spaces. For
a command whose arguments are single words that reads correctly, but the agent
command is not like that: the default prompt is passed as **one** argument, so
`opencode run <long prompt>` is rendered as

```text
command: opencode run Read /home/paul/code/openlearning/openspec/changes/responsive-design-system/tasks.md and any handoff at /home/paul/code/openlearning/HANDOFF.md. Implement one task. ...
```

That looks like a malformed command missing quotes around several arguments.
It is not: the process receives a correct argument list and no shell is
involved. The rendering is what is wrong, and it is worst exactly where it
matters most — the diagnostic log is now the primary artifact for a failed
agent run, so the first thing a user reads is a command line that looks broken.

The same join is used for the verification command in the human result, in the
timeout report, in `doctor` and dry-run, and in the low-level single-command
output. Any argument containing a space is misleading in all of them.

## What changes

- Add one shared command formatter that renders an argument list the way a
  shell would need it quoted, and use it everywhere a command is displayed:
  the diagnostic log, the agent-failure and timeout reports, the verification
  status line, `doctor` and dry-run, and the low-level single-command output.
- Leave simple commands unchanged: an argument list without special characters
  renders exactly as it does today, so existing output does not churn.

## Non-goals

- No change to execution. Commands remain argument lists passed to the
  subprocess runner without a shell, and no quoting affects what runs.
- No change to structured output. JSON keeps `command` as a list of strings.
- No change to how commands are constructed by adapters, and no change to
  prompt content or prompt templates.
- No attempt to make the rendered line directly copy-pasteable into a shell
  for every possible argument; the goal is that argument boundaries are
  visible.

## Success criteria

A command containing a multi-word argument is displayed with that argument
quoted, a command of single-word arguments is displayed unchanged, and the
diagnostic log and human reports all agree. Focused tests and strict OpenSpec
validation must pass.
