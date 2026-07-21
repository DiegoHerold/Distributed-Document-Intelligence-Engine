# eixo-api

Aplicacao HTTP oficial inicial do Eixo.

A API e um adaptador REST sobre `DocumentEngine`. Ela nao implementa parsing,
processamento documental, capabilities concretas ou acesso direto a stores.

## Execucao local

Com `uv` instalado:

```bash
uv run uvicorn eixo_api.main:app --reload
```

Com o Python do ambiente:

```bash
python -m uvicorn eixo_api.main:app --reload
```

OpenAPI:

```text
http://localhost:8000/openapi.json
http://localhost:8000/docs
```

## Configuracao

`ApiConfig` define:

- titulo, descricao e versao;
- ambiente, host e porta;
- modo debug;
- OpenAPI habilitado ou nao;
- CORS restritivo e desabilitado por padrao;
- `max_upload_size`;
- `request_timeout`;
- `local_data_dir`, usado pelo storage local de artefatos, documentos e jobs.

PostgreSQL, Redis, MinIO, Temporal, API keys, tenants obrigatorios e rate
limiting distribuido nao fazem parte desta fase.

## Lifecycle

`create_app()` cria somente a aplicacao FastAPI.

No startup, o lifespan cria ou reaproveita uma unica instancia de
`DocumentEngine`, inicia o engine e marca a API como pronta.

No shutdown, a API marca o estado como encerrando, chama `engine.shutdown()` e
encerra o `LocalRuntime` por meio do proprio engine.

## Endpoints

- `GET /health`: processo HTTP vivo.
- `GET /ready`: engine, runtime, registry e job store prontos.
- `POST /v1/documents:inspect`: upload multipart para `InspectionRequest`.
- `POST /v1/documents:parse`: upload multipart para `ParseRequest`.
- `POST /v1/extractions`: cria job assincrono local com `ProcessingRequest`.
- `GET /v1/extractions/{job_id}`: consulta `JobResult`.
- `GET /v1/extractions/{job_id}/result`: consulta `ProcessingResult`.
- `POST /v1/extractions/{job_id}/cancel`: solicita cancelamento.

## Uploads

A borda HTTP le `multipart/form-data`, valida tamanho, nome e MIME declarado, e
converte o arquivo para `BytesSource`. Objetos do framework nao vazam para o
nucleo.

A validacao documental de seguranca e executada pelo `DocumentEngine`: tamanho
real, arquivo vazio, formato detectado, divergencias de MIME/extensao,
corrupcao basica, XLSX/ZIP e nomes perigosos usam a mesma politica da
biblioteca Python e da CLI. A API faz apenas validacoes de transporte.

Limitacao atual: o adapter multipart inicial materializa o arquivo em memoria
depois de respeitar o limite configurado. O nucleo recebe somente `BytesSource`,
nao tipos HTTP.

## Jobs

Jobs e resultados estruturados pequenos ficam em SQLite dentro do engine local.
Eles sobrevivem a uma nova instancia simples usando o mesmo `local_data_dir`.
Documentos e artefatos originais tambem ficam no `local_data_dir` configurado.

Esta persistencia e local. PostgreSQL, filas distribuidas e workers remotos
continuam fora desta fase.

## Erros

Erros de dominio sao convertidos para `ErrorResult`, com correlation ID e sem
stack trace no corpo da resposta.

Mapeamentos principais:

- `CapabilityNotFoundError`: 422
- `UnsupportedFormatError`: 415
- `InvalidMimeError`: 415
- `FileTooLargeError`: 413
- `ReadTimeoutError`: 408
- `UnsafeFilenameError`: 400
- `PathTraversalError`: 400
- `EmptyFileError`: 422
- `CorruptedFileError`: 422
- `ArchiveSecurityError`: 422
- `PageLimitExceededError`: 422
- `UploadTooLargeError`: 413
- `ArtifactNotFoundError`: 404
- `DocumentVersionConflictError`: 409
- `JobNotFoundError`: 404
- `JobResultUnavailableError`: 409
- `JobConcurrencyError`: 409
- `InvalidJobTransitionError`: 409
- `JobPersistenceError`: 503
- `JobRecoveryError`: 503
- `InvalidStateTransitionError`: 409
- `ExecutionTimeoutError`: 504
- `ExecutionRejectedError`: 503
- `ConfigurationError`: 503

## Exemplos

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready

curl -X POST -F "file=@documento.pdf" \
  http://localhost:8000/v1/documents:inspect

curl -X POST -F "file=@documento.pdf" \
  http://localhost:8000/v1/documents:parse

curl -X POST -F "file=@documento.pdf" \
  http://localhost:8000/v1/extractions

curl http://localhost:8000/v1/extractions/job_123
curl http://localhost:8000/v1/extractions/job_123/result
curl -X POST http://localhost:8000/v1/extractions/job_123/cancel
```

Sem capabilities reais registradas, endpoints documentais retornam erro
estruturado de capability ausente.
