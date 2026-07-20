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
- `StreamSource`;
- `ArtifactReferenceSource`.

Objetos de transporte, como `UploadFile` do FastAPI, nao fazem parte deste contrato.
Sources descrevem a origem e nao abrem arquivos durante a construcao.

O fluxo compartilhado resolve a origem, detecta formato real e calcula
identidade de conteudo antes de executar a capability compativel.
Depois das fases 2.5 e 2.6, o mesmo fluxo armazena o original como
`ArtifactReference` e registra um `DocumentRecord` local com status `stored`.
Contratos publicos nao expõem caminhos absolutos do storage local.

## Limitacoes atuais

O contrato existe, mas ainda nao ha parser real de PDF, Excel, OCR ou processamento semantico.
