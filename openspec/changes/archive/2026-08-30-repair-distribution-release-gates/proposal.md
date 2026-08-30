# Proposal: Repair Distribution Release Gates

## Why

The distribution implementation is committed and mostly functional, but the release gate is not green. The distribution main spec still uses change-delta headers, tests reference an archived change directory, and PowerShell validation has not been completed in a supported environment.

## New

- Canonical distribution main-spec structure.
- Tests that validate stable repository/website links without depending on active change folders.
- Portable PowerShell syntax/install verification in supported CI.

## Modified

- Distribution test and release verification paths.

## Non-goals

- No new installer behavior.
- No DNS, GitHub account, or external hosting changes.
- No replacement of the existing release artifact format.
