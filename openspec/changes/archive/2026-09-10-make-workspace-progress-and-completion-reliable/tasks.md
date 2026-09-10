## 1. Testing

- [x] 1.1 Add failing tests for source-only changes being reported as progress.
- [x] 1.2 Add false-positive blocker, uppercase checklist, and malformed TOML tests.
- [x] 1.3 Add path-boundary tests for task, handoff, and workflow paths.

## 2. Workflow and configuration implementation

- [x] 2.1 Add configurable workspace-change evidence without requiring Git.
- [x] 2.2 Tighten blocker and checklist parsing while preserving custom markers.
- [x] 2.3 Validate configured paths and return structured configuration errors.

## 3. Documentation and verification

- [x] 3.1 Document progress evidence, path trust modes, and configuration errors.
- [x] 3.2 Run focused tests, full tests, lint, compile checks, and strict OpenSpec validation.
