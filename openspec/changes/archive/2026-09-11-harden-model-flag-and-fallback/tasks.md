## 1. Testing

- [x] 1.1 Add a test: a command ending in `--model` with a fallback model does not raise; the model value is applied or the run fails cleanly.
- [x] 1.2 Add a test: `GenericCommandAdapter` without the model-flag opt-in does not gain a `--model` argument; the model travels via `AGENT_MODEL` only.
- [x] 1.3 Add a test: an all-`supports_model==False` chain raises `ModelChainExhausted` with skips recorded and the loop stops cleanly without evidence handling errors.
- [x] 1.4 Add a test: mixed supported/skipped chains record both attempts and skips in order.

## 2. Single-owner model injection

- [x] 2.1 Move per-model command construction into the adapter; remove the loop's `--model` index rewrite (or guard it against trailing flags during migration).
- [x] 2.2 Add the generic-adapter model-flag opt-in and keep env-only delivery otherwise.

## 3. Fallback accounting

- [x] 3.1 Record skipped models in `try_fallback` and surface them via `ModelChainExhausted` + `model_attempts`.
- [x] 3.2 Handle `last_result=None` (no attempt ran) in the loop's exhausted-chain path.

## 4. Documentation and validation

- [x] 4.1 Document the opt-in marker and the single-owner rule in `docs/adapters.md`.
- [x] 4.2 Run focused tests, the full suite, `ruff check`, `compileall`, and `openspec validate --all --strict`.
