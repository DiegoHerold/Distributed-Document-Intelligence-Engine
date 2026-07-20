# ProcessingResult

`ProcessingResult` representa o resultado publico inicial do processamento.

## Campos

- `job_id`;
- `document_id`;
- `status`;
- `data`;
- `artifacts`;
- `warnings`;
- `errors`;
- `execution_metadata`;
- `contract_version`.

## Erros publicos

Erros sao expostos por `ErrorResult`, com:

- codigo estavel;
- mensagem segura;
- categoria;
- flag `retryable`;
- detalhes estruturados;
- `correlation_id` quando aplicavel.

Stack traces nao fazem parte do contrato publico.

## Evolucao

`data` permanece generico nesta fase para permitir evolucao futura de schemas, templates e resultados estruturados.

