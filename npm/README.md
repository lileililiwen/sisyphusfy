# sisyphusfy

Cross-platform launcher for [Sisyphusfy](https://github.com/lileililiwen/sisyphusfy).

## Installation

```bash
npm install -g sisyphusfy
```

If this command reports `E404`, the package is not currently published on the
npm public registry. Maintainers should follow the [npm publication setup](../docs/deployment.md#npm-package-publication).

## Usage

```bash
sisyphusfy --help
sisyphusfy run my-change
sisyphusfy loop --task-path TASKS.md --adapter opencode
```

## How it works

This package downloads the platform-specific Sisyphusfy release artifact and runs it locally. It does not reimplement any Python runner logic.

## Links

- Repository: https://github.com/lileililiwen/sisyphusfy
- Website: https://about.tooosall.uk/
- Releases: https://github.com/lileililiwen/sisyphusfy/releases
