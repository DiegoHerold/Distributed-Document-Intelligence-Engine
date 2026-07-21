# PDF Image Resources

Status: Fase 3.7 implementada parcialmente.

## Contratos

`PDFImageResource` e o contrato publico para imagens nativas reutilizaveis em
PDF.

Campos centrais:

- `image_resource_id`;
- `resource_reference`;
- `object_reference`;
- `image_kind`;
- `width`;
- `height`;
- `bits_per_component`;
- `color_space`;
- `filter_chain`;
- `encoded_hash`;
- `decoded_hash`;
- `encoded_artifact_reference`;
- `decoded_artifact_reference`;
- `normalized_artifact_reference`;
- `mask_reference`;
- `soft_mask_reference`;
- `transparency`;
- `pages_using_resource`;
- `provider_metadata`;
- `fidelity`.

## Bytes

Bytes de imagem nao sao embutidos em `PDFImageResource`. Quando o provider
extrai uma representacao binaria, o contrato usa `PDFImageBinaryReference`:

- `binary_id`;
- `artifact_reference`, quando houver `ArtifactStore` integrado;
- `content_hash`;
- `size_bytes`;
- `representation`;
- `media_type`;
- `detected_format`;
- `extraction_method`;
- `fidelity`.

Na Fase 3.7, o PyMuPDF produz referencias com hash, tamanho e formato por
`document.extract_image(xref)`. O armazenamento fisico em `ArtifactStore` fica
para a integracao posterior do parser completo.

## Identidade

IDs devem ser deterministicos quando o PDF fornece xref ou identificador
equivalente. Hashes usam SHA-256 sobre bytes extraidos pelo provider e nao sobre
serializacoes de objetos Python.

## Limites

`PDFImageExtractionOptions` controla selecao de paginas, inclusao de bytes,
tamanho maximo por imagem, quantidade maxima de recursos, ocorrencias por
pagina e exportacoes normalizadas.
