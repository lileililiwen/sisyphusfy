# Proposal: Add Distribution and Installers

## Why

Sisyphusfy is intended for use across many projects and should be easy to install without requiring users to clone the repository or understand the Python development environment. The public project identity is GitHub repository `lileililiwen/sisyphusfy` with `https://about.tooosall.uk/` as the documentation and distribution website.

## New

- Release artifact and checksum publishing contract.
- npm package as a cross-platform launcher using the published artifact.
- POSIX shell installer and PowerShell installer.
- GitHub Pages/custom-domain documentation deployment.
- Installation, upgrade, version selection, and uninstall documentation.

## Modified

- README adds stable repository, website, release, and installation links.

## Non-goals

- No DNS or domain-provider changes in this repository.
- No automatic root installation.
- No installer that executes unverified remote code.
- No npm reimplementation of the Python runner.
- No automatic GitHub release publication without an explicit release workflow.
