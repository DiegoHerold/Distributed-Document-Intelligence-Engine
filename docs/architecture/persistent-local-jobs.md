# Jobs Locais Persistentes

A Fase 2.7 substitui o servico oficial de jobs em memoria por uma composicao
local persistente baseada em SQLite.

O objetivo e dar durabilidade simples ao modo local, sem introduzir
PostgreSQL, Redis, Temporal, workers distribuidos ou infraestrutura externa.

## Componentes

| Componente | Pacote | Responsabilidade |
|---|---|---|
| `JobRecord` | `document-core` | Estado persistivel do job |
| `JobStoredResult` | `document-core` | Resultado estruturado persistido |
| `JobQuery` e `JobPage` | `document-core` | Consulta e paginacao de jobs |
| `JobStore` | `document-application` | Porta usada pela aplicacao |
| `JobTransitionPolicy` | `document-application` | Transicoes validas de estado |
| `SQLiteJobStore` | `document-application` | Adapter local em SQLite |
| `LocalJobRecoveryService` | `document-application` | Recuperacao apos restart |
| `PersistentJobService` | `document-application` | Orquestracao entre runtime e store |

`DocumentEngine.local()` compoe `PersistentJobService` com `SQLiteJobStore`.
Por padrao, o banco fica em:

```text
<data_directory>/jobs/jobs.sqlite3
```

Tambem e possivel informar `job_database_path` em `DocumentEngine.local()` ou
`LocalEngineConfig`.

## Fronteira

O kernel depende da porta `JobStore`, nao de SQLite diretamente. O SQLite e um
adapter local do modo `DocumentEngine.local()`.

O `LocalRuntime` continua responsavel por executar tarefas e expor handles de
execucao. Ele nao persiste jobs. O `PersistentJobService` observa o runtime,
aplica transicoes e grava estado/resultados pelo `JobStore`.

## Estados

Estados persistidos:

- `created`;
- `queued`;
- `running`;
- `completed`;
- `review_required`;
- `failed`;
- `cancel_requested`;
- `cancelled`.

Estados terminais:

- `completed`;
- `review_required`;
- `failed`;
- `cancelled`.

## Transicoes

Transicoes validas:

| Origem | Destinos |
|---|---|
| `created` | `queued`, `cancelled` |
| `queued` | `running`, `cancel_requested`, `failed` |
| `running` | `completed`, `review_required`, `failed`, `cancel_requested`, `cancelled` |
| `cancel_requested` | `cancelled`, `completed`, `failed` |

Jobs terminais nao sao reiniciados arbitrariamente.

## Recuperacao

Na abertura do engine local, `LocalJobRecoveryService` varre jobs nao terminais.

Politica atual:

- `created`, `queued` e `running` viram `failed`;
- o erro usa codigo `job.interrupted` e `retryable=True`;
- `cancel_requested` vira `cancelled`;
- resultados ja persistidos continuam disponiveis apos nova instancia.

Essa politica evita que jobs antigos fiquem presos em estados intermediarios
apos encerramento do processo.

## Persistencia Do Resultado

Resultados pequenos e estruturados sao persistidos como JSON em SQLite. Dados
binarios grandes devem continuar fora do banco, via artefatos.

`JobStoredResult` armazena `ProcessingResult`; referencias de artefato permanecem
como `ArtifactReference`, sem expor caminhos absolutos.

## Canais Publicos

Os fluxos publicos permanecem os mesmos:

- `DocumentEngine.submit()`;
- `DocumentEngine.get_job_status()`;
- `DocumentEngine.get_job_result()`;
- `DocumentEngine.cancel_job()`;
- `POST /v1/extractions`;
- `GET /v1/extractions/{job_id}`;
- `GET /v1/extractions/{job_id}/result`;
- `POST /v1/extractions/{job_id}/cancel`;
- `eixo jobs status`;
- `eixo jobs result`;
- `eixo jobs cancel`.

API e CLI continuam adaptadores: elas nao acessam SQLite diretamente.

## Limites

Esta nao e a persistencia de producao do Eixo. Ainda ficam fora:

- filas distribuidas;
- reexecucao automatica de jobs interrompidos;
- streaming de eventos;
- locks multi-host;
- storage de resultados binarios grandes dentro do banco.
