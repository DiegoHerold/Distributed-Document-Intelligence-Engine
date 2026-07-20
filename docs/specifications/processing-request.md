# ProcessingRequest

`ProcessingRequest` e o contrato publico inicial para solicitar processamento documental.

## Campos

- `source`: origem do documento, usando `DocumentSource`.
- `profile`: perfil de processamento, inicialmente `balanced`.
- `policies`: politicas extensivas por chave estruturada.
- `schema_reference`: referencia opcional para schema futuro.
- `template_reference`: referencia opcional para template futuro.
- `options`: opcoes adicionais versionaveis.
- `correlation_id`: identificador para rastreamento.
- `tenant_id`: identificador opcional de tenant.
- `contract_version`: versao do contrato.

## Fontes

Fontes iniciais:

- `LocalPathSource`;
- `BytesSource`;
- `ArtifactReferenceSource`.

Objetos de transporte, como `UploadFile` do FastAPI, nao fazem parte deste contrato.

## Limitacoes atuais

O contrato existe, mas ainda nao ha parser real de PDF, Excel, OCR ou processamento semantico.

