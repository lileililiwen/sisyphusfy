# Contributing to Sisyphusfy

Contributions should preserve the project-agnostic boundary. New support for a specific agent, task format, or project workflow belongs in an adapter or example configuration rather than in the loop engine.

Before opening a pull request:

1. add tests for new behavior;
2. use a fake agent command for process-level tests;
3. verify timeout, failure, and blocked states;
4. document security implications of command execution;
5. keep the default prompt short and generic.
