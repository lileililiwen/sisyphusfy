# Design: Distribution and Installers

## Explore & Reuse

Reuse the existing Python package entry point, `pyproject.toml` metadata, README installation guidance, and GitHub repository as the source of truth. Distribution wrappers invoke or install the published package/artifact; they must not duplicate runner behavior.

## Public endpoints

- Repository: `https://github.com/lileililiwen/sisyphusfy`
- Website: `https://about.tooosall.uk/`
- Releases: `https://github.com/lileililiwen/sisyphusfy/releases`
- Raw bootstrap fallback: `https://raw.githubusercontent.com/lileililiwen/sisyphusfy/main/install.sh`

The custom domain is a website/GitHub Pages concern, not a replacement for the repository URL. DNS ownership and GitHub Pages configuration remain manual release prerequisites.

## Distribution paths

1. Python users may install the package with `pipx` or `pip`.
2. npm users install a thin `sisyphusfy` launcher that selects the platform and downloads a pinned release artifact.
3. POSIX users run a versioned shell installer; Windows users use a PowerShell installer.

Every downloaded artifact MUST use HTTPS, a pinned version, and a published SHA-256 checksum. Installers default to a user-writable directory and print PATH instructions. Root installation is explicit, never implicit.

## Verification and safety

Release CI builds artifacts for supported platforms, generates checksums, tests the npm launcher and installers in clean environments, and verifies that the documented repository and website links resolve. Installer tests use local fixtures; they do not pipe arbitrary network content into a shell.
