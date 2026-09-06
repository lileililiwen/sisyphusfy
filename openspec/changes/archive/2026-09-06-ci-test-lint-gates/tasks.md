## 1. Pipeline
- [x] 1.1 Add ci.yml triggered on push/PR.
- [x] 1.2 Run `pytest`.
- [x] 1.3 Run `ruff check` and `ruff format --check`.
- [x] 1.4 Run a Python 3.11/3.12 matrix and upload coverage.
## 2. Verification
- [x] 2.1 Push a trivial change and confirm gates run.
- [x] 2.2 Run `openspec validate ci-test-lint-gates`.
