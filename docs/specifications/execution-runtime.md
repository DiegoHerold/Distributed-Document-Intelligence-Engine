# ExecutionRuntime

`ExecutionRuntime` e o contrato para execucao de tarefas do Eixo.

## Tipos principais

- `ExecutionTask`: descreve uma tarefa executavel.
- `ExecutionMode`: `async`, `thread` ou `process`.
- `ExecutionOptions`: timeout e controle de timeout.
- `ExecutionResult`: resultado estruturado.
- `ExecutionHandle`: handle de uma tarefa submetida.
- `CancellationToken`: cancelamento cooperativo.
- `ProgressReporter`: progresso local independente de API.
- `RuntimeExecutionContext`: contexto preservado por tarefa.

## ExecutionTask

Campos principais:

- `task_id`;
- `name`;
- `handler`;
- `input`;
- `execution_mode`;
- `capability_id`;
- `timeout`;
- `metadata`.

## ExecutionResult

Campos principais:

- `task_id`;
- `status`;
- `value`;
- `error`;
- `warnings`;
- `started_at`;
- `completed_at`;
- `duration`;
- `execution_mode`;
- `metadata`.

Status:

- `created`;
- `queued`;
- `running`;
- `completed`;
- `failed`;
- `cancelled`;
- `timed_out`.

## Timeout

Timeout pode vir da tarefa, das opcoes de execucao ou da configuracao padrao do runtime. Timeout produz status `timed_out` e erro `execution.timeout`.

## Cancelamento

Cancelamento e cooperativo. Tarefas assincronas recebem cancelamento pelo task do event loop e por `CancellationToken`. Tarefas em thread ou processo podem ter a espera cancelada, mas a execucao bloqueante ja iniciada pode continuar ate retornar.

## Processos

Handlers em processo precisam ser serializaveis e importaveis. Funcoes locais, lambdas e objetos com estado nao serializavel devem falhar com `execution.serialization`.

