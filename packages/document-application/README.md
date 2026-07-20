# eixo-document-application

Transport-independent application layer. It coordinates use cases through ports
and shared contracts, including source resolution, format detection, content
hashing, content identity, artifact storage and document lifecycle.

It also owns the job application boundary:

- `JobStore` as the persistence port;
- `PersistentJobService` as the orchestration service;
- `SQLiteJobStore` as the local adapter;
- `LocalJobRecoveryService` for restart recovery.

Dependencies: `eixo-document-core`, `eixo-plugins`.
