# ADR 0001: Local-first runtime and storage

## Status

Accepted

## Context

The first version is a personal DSA workspace that executes the learner’s Python code, stores a complete local learning history, and must remain free to run. Public static hosting cannot provide the application runtime, database, and code execution boundary together. A hosted version would also require stronger isolation for untrusted code and a remote database.

## Decision

The first usable version runs locally as a Django application with SQLite persistence and a separate constrained Python runner process. The application provides versioned export and restore backups. Hosting, remote storage, and containerized execution remain later migration paths.

## Consequences

- The complete solving workflow works without network access after catalog data is available locally.
- The local runner can be replaced behind an execution interface when hosted deployment becomes a priority.
- Personal history is not automatically available across devices until a future synchronization design is approved.
- Public source synchronization must fail safely and preserve the last successful local catalog.
