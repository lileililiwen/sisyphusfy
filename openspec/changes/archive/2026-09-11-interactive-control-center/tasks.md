## 1. Testing

- [x] 1.1 Add tests: slash parser handles `/models`, `/models <name>`, `/compact`, `/help`, `/resume`, `/stop`, and unknown `/foo` (help + re-prompt, never forwarded as answer).
- [x] 1.2 Add tests: fake-tty REPL session switching models mid-blocked-flow changes subsequent invocation models and records the switch.
- [x] 1.3 Add tests: `/compact` compacts the handoff, reports counts, and the next prompt renders the compacted file.
- [x] 1.4 Add tests: ESC (lone byte) sets pending-pause honored at the next iteration boundary with resume/stop choice; CSI arrow sequences do not pause.
- [x] 1.5 Add tests: non-interactive (`--json`/piped) ignores keys and slash handling is unreachable.

## 2. Control module

- [x] 2.1 Add `control.py`: raw-mode key reader (POSIX, Windows fallback), ESC/CSI parsing, pending-pause flag.
- [x] 2.2 Add slash-command parser + dispatcher (`/models`, `/compact`, `/help`, `/resume`, `/stop`) with help text.

## 3. Loop integration

- [x] 3.1 Host the REPL in the blocked prompt; consume slash input, forward only plain-text answers to `_augment_prompt`.
- [x] 3.2 Check pending-pause at iteration boundaries and in the REPL; offer resume / stop / step-once.
- [x] 3.3 Record pause count, model switches, and compactions on telemetry/`LoopResult`.

## 4. Documentation and validation

- [x] 4.1 Document ESC semantics (boundary pause, Windows limitation), all slash commands, and the v1 no-SIGSTOP scope.
- [x] 4.2 Run focused tests, the full suite, `ruff check`, `compileall`, and `openspec validate --all --strict`.
