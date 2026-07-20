# eixo-runtime-local

Local asynchronous execution runtime for Eixo.

It runs `ExecutionTask` objects in one of three modes:

- `async`: awaits async handlers on the current event loop.
- `thread`: runs blocking callables in a reusable `ThreadPoolExecutor`.
- `process`: runs CPU-bound callables in a reusable `ProcessPoolExecutor`.

Cancellation is cooperative for async tasks. For thread and process tasks, cancellation stops the caller from waiting and marks the handle as cancelled, but Python cannot forcibly interrupt already-running blocking work safely.

Dependencies: `eixo-document-core`, `eixo-plugins`.
