# End-to-end examples

Each example is a complete, minimal setup: project configuration, task file, and
the command to run. All of them use the same supervisor; only
`verification_command` and the task content are project-specific.

## Python

```bash
mkdir -p myproj && cd myproj
```

`.sisyphusfy.toml`:

```toml
adapter = "opencode"
model_chain = ["mimo-v2.5"]
max_iterations = 20
agent_timeout = 2700.0
verification_command = ["pytest", "-q"]
verification_timeout = 600.0
```

`tasks.md`:

```markdown
- [ ] Add a `normalize` function to `myproj/text.py`
- [ ] Cover empty input in `tests/test_text.py`
- [ ] Keep `pytest -q` green
```

```bash
sisyphusfy run
sisyphusfy status
```

## Rust

`.sisyphusfy.toml`:

```toml
adapter = "opencode"
model_chain = ["mimo-v2.5"]
max_iterations = 15
agent_timeout = 2700.0
verification_command = ["cargo", "test", "--quiet"]
verification_timeout = 1800.0
```

`tasks.md`:

```markdown
- [ ] Add `Parser::from_str` in `src/parser.rs`
- [ ] Cover malformed input in the module tests
- [ ] Keep `cargo test` and `cargo clippy` clean
```

```bash
sisyphusfy run --project-dir .
```

## JavaScript / TypeScript

`.sisyphusfy.toml`:

```toml
adapter = "codebuddy"
model_chain = ["minimax-3"]
max_iterations = 15
agent_timeout = 1800.0
verification_command = ["npm", "test", "--silent"]
verification_timeout = 900.0
```

`tasks.md`:

```markdown
- [ ] Add `formatCurrency` to `src/format.ts`
- [ ] Cover negative amounts in `src/format.test.ts`
- [ ] Keep `npm test` green
```

```bash
sisyphusfy run my-change
sisyphusfy run my-change --dry-run   # preview before executing
```

## Flutter / Dart

`.sisyphusfy.toml`:

```toml
adapter = "opencode"
model_chain = ["mimo-v2.5"]
max_iterations = 15
agent_timeout = 2700.0
verification_command = ["flutter", "test"]
verification_timeout = 1800.0
```

`tasks.md`:

```markdown
- [ ] Add the `CounterCard` widget in `lib/widgets/counter_card.dart`
- [ ] Add a widget test for the increment action
- [ ] Keep `flutter test` green
```

```bash
sisyphusfy run
```

## .NET

`.sisyphusfy.toml`:

```toml
adapter = "opencode"
model_chain = ["mimo-v2.5"]
max_iterations = 15
agent_timeout = 2700.0
verification_command = ["dotnet", "test", "--nologo"]
verification_timeout = 1800.0
```

`tasks.md`:

```markdown
- [ ] Add `InvoiceTotals` to `src/Billing/InvoiceTotals.cs`
- [ ] Cover zero-quantity lines in `tests/Billing.Tests`
- [ ] Keep `dotnet test` green
```

```bash
sisyphusfy run
```

## OpenSpec changes

For a repository managed with OpenSpec, name the change instead of pointing at a
file:

```bash
sisyphusfy run add-invoice-totals      # openspec/changes/add-invoice-totals/tasks.md
sisyphusfy status                      # shows the discovered change
sisyphusfy run add-invoice-totals --archive   # archive only after verification passes
```

The workflow adapter counts checkboxes in the change's `tasks.md` and runs the
configured validation command before completion is accepted.

## Resuming

Every example can be interrupted and resumed. The task file and handoff file are
the durable state:

```bash
sisyphusfy resume                       # continue the durable loop
sisyphusfy resume --inspect             # read the most recent diagnostic log
sisyphusfy resume --verification-timeout 600   # raise the verification limit
```

Use `--verification-timeout N` when the project verifier (e.g. a long
`pytest`, `cargo test`, or `dotnet test` run) needs more than the 30s
default. The effective value is shown in dry-run output and in the
structured JSON result.
