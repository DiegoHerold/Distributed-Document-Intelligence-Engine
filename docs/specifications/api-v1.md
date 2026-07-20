# API REST v1

Especificacao inicial da API REST do Eixo.

## Principio

```text
HTTP
  -> API adapter
  -> DocumentEngine
  -> Application
  -> Capability Registry
  -> LocalRuntime
```

A API nao implementa regras documentais. Endpoints convertem transporte HTTP
para contratos publicos e delegam ao `DocumentEngine`.

## Endpoints operacionais

### GET /health

Sempre responde 200 quando o processo HTTP esta vivo.

```json
{
  "status": "ok",
  "service": "eixo-api",
  "version": "0.1.0"
}
```

### GET /ready

Retorna 200 quando engine, runtime, registry e job store estao prontos.

Retorna 503 quando a aplicacao nao aceita operacoes documentais.

## Endpoints documentais

### POST /v1/documents:inspect

Entrada: `multipart/form-data`.

Campos:

- `file`: obrigatorio;
- `options`: JSON object opcional;
- `correlation_id`: opcional.

Converte para `InspectionRequest` e chama `DocumentEngine.inspect()`.

### POST /v1/documents:parse

Entrada: `multipart/form-data`.

Campos:

- `file`: obrigatorio;
- `options`: JSON object opcional;
- `requested_capability`: opcional;
- `correlation_id`: opcional.

Converte para `ParseRequest` e chama `DocumentEngine.parse()`.

### POST /v1/extractions

Entrada: `multipart/form-data`.

Campos:

- `file`: obrigatorio;
- `profile`: opcional, default `balanced`;
- `options`: JSON object opcional;
- `schema_id`: opcional;
- `template_id`: opcional;
- `correlation_id`: opcional.

Converte para `ProcessingRequest` e chama `DocumentEngine.submit()`.

Resposta: `202 Accepted`, `JobResult` e header `Location`.

### GET /v1/extractions/{job_id}

Chama `DocumentEngine.get_job_status()` e retorna `JobResult`.

### GET /v1/extractions/{job_id}/result

Chama `DocumentEngine.get_job_result()` e retorna `ProcessingResult` quando
disponivel.

Resultado ainda indisponivel retorna 409 com `ErrorResult`.

### POST /v1/extractions/{job_id}/cancel

Chama `DocumentEngine.cancel_job()`.

Cancelamento aceito retorna 202. Job inexistente retorna 404. Transicao
invalida retorna 409.

## Upload

O adapter HTTP valida:

- `Content-Type: multipart/form-data`;
- campo `file`;
- nome de arquivo sanitizado;
- MIME declarado com formato `tipo/subtipo`;
- limite real de leitura;
- arquivo nao vazio.

O contrato atual usa `BytesSource`. Stream documental real fica para fase
posterior.

## Erros

Respostas de erro usam `ErrorResult`.

| Erro | HTTP |
| --- | ---: |
| `ValidationError` | 422 |
| `UploadTooLargeError` | 413 |
| `CapabilityNotFoundError` | 422 |
| `UnsupportedFormatError` | 415 |
| `JobNotFoundError` | 404 |
| `InvalidStateTransitionError` | 409 |
| `ExecutionTimeoutError` | 504 |
| `ExecutionCancelledError` | 409 |
| `ExecutionRejectedError` | 503 |
| `ConfigurationError` | 503 |
| erro inesperado | 500 |

## Correlation ID

A API aceita `X-Correlation-ID`. Quando ausente ou invalido, gera um novo ID.
Toda resposta inclui `X-Correlation-ID`.

## OpenAPI

Quando `docs_enabled=True`, a especificacao fica em:

```text
/openapi.json
```

A interface interativa fica em:

```text
/docs
```

## Limites

A v1 inicial nao inclui autenticacao, tenants obrigatorios, persistencia
duravel, object storage, workers remotos, webhooks, streaming ou providers
documentais reais.
