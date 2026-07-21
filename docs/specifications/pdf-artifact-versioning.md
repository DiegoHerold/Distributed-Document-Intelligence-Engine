# PDF Artifact Versioning

Status: inicial, Fase 3.11.

O Bloco 3 usa versionamento explicito para diferenciar instancia, schema,
producer e provider.

## Campos

- `artifact_version`: versao da instancia/contrato do artefato produzido.
- `schema_version`: versao da forma serializada.
- `provider_version`: versao do provider que originou artefatos de entrada.
- `artifact_versions`: mapa de versoes dos artefatos consolidados.

## Compatibilidade

O builder registra warnings quando encontra:

- `native_scene_source_missing`;
- `native_scene_document_mismatch`;
- `native_scene_source_hash_mismatch`;
- referencias ou paginas ausentes.

Artefatos opcionais podem estar ausentes, mas isso reduz fidelidade e fica
rastreavel por warnings, limitacoes ou dimensoes `unknown`.

## Persistencia

`NativePDFSceneArtifact` e serializavel e compativel com `ArtifactStore` por meio
de `ArtifactReference`. A escrita automatica no store, endpoints, CLI e fluxo
publico completo pertencem a Fase 3.12.
