# Tasks: Distribution and Installers

## 1. Testing

- [x] Test release metadata and checksum generation.
- [x] Test npm launcher version/platform selection with local release fixtures.
- [x] Test POSIX installer success, checksum failure, unsupported platform, and user directory behavior.
- [x] Test PowerShell installer success, checksum failure, and unsupported platform behavior.
- [x] Test version override and dry-run behavior.
- [x] Test documented repository, website, and release links.

## 2. Implementation

- [x] Define release artifact names, supported platforms, and checksum manifest.
- [x] Add npm launcher package without duplicating Python runner logic.
- [x] Add POSIX shell installer.
- [x] Add PowerShell installer.
- [x] Add release CI for artifacts and checksums.
- [x] Add GitHub Pages/custom-domain deployment documentation.
- [x] Update README with canonical links and installation methods.

## 3. Verification

- [x] Run installer tests in clean environments.
- [x] Run complete tests, lint, compile, and package checks.
- [x] Verify release artifacts and checksums locally.
- [x] Validate with `openspec validate add-distribution-and-installers --strict`.
