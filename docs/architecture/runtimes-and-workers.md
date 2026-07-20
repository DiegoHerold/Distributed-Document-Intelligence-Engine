# Runtimes e Workers

O Eixo separa a decisao de processamento da execucao fisica das tarefas.

## Contrato comum

`ExecutionRuntime` define a interface comum para runtimes:

- `execute(...)`: executa e aguarda o resultado.
- `submit(...)`: submete em segundo plano dentro do processo.
- `start()`: inicializa recursos.
- `shutdown()`: encerra recursos.

Esse contrato permite que `LocalRuntime` e um futuro `TemporalRuntime` sejam intercambiaveis no `DocumentEngine`.

## LocalRuntime

O `LocalRuntime` executa tarefas localmente, sem banco, Redis, filas ou Temporal.

Modos:

- `async`: aguarda handlers assincronos no event loop atual.
- `thread`: executa funcoes bloqueantes em `ThreadPoolExecutor`.
- `process`: executa funcoes CPU-bound serializaveis em `ProcessPoolExecutor`.

## Workers futuros

Workers fisicos ainda nao existem nesta fase. Futuramente, um runtime distribuido podera mapear tarefas para workers CPU, GPU ou semanticos.

## Limites

O runtime nao escolhe capabilities, nao faz roteamento, nao implementa parsers e nao contem logica documental.

