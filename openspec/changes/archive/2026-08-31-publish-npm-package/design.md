# Design: Publish the npm launcher

## Explore & Reuse

Reuse the existing tag-triggered `.github/workflows/release.yml`, the
`npm/package.json` package root, and the repository's release workflow tests.
The existing PyPI job demonstrates the dependency on `publish-release` and
OIDC permissions; npm publication follows the same release boundary.

## Workflow

Add a `publish-npm` job that depends on `publish-release`, checks out the
repository, configures Node 24 and the public npm registry, prints the npm
version, and runs `npm publish --access public` with `npm/` as its working
directory. The job grants only `contents: read` and `id-token: write`; npmjs.org
must be configured with this repository and workflow filename as its trusted
publisher.

## Verification and documentation

Add static YAML-contract tests for the job, dependency, registry, OIDC, publish
command, and absence of token authentication. Update the main and npm READMEs
and deployment guide with the publication behavior and one-time maintainer
steps. The existing v0.1.0 package must be published once manually because
workflow changes cannot retroactively run for that tag.
