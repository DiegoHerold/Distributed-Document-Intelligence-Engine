# Ingestao e Identidade de Conteudo

Este documento descreve a base implementada nas fases 2.1 a 2.4 do Bloco 2.

## Objetivo

O fluxo inicial de ingestao transforma uma origem externa em conteudo resolvido,
detecta o formato real, calcula hash SHA-256 e produz uma identidade tecnica do
conteudo. Ele nao armazena o documento, nao faz parsing e nao cria ciclo de vida
persistente.

```text
entrada publica
  -> DocumentSource
  -> SourceResolver
  -> DocumentFormatDetector
  -> ContentHasher
  -> DocumentIdentity
  -> capability ou erro controlado
```

## Contratos

`DocumentSource` descreve a origem logica sem abrir arquivos.

Tipos iniciais:

- `LocalPathSource`;
- `BytesSource`;
- `StreamSource`;
- `ArtifactReferenceSource`, preservado para integracao futura com artefatos.

Factories publicas:

```python
DocumentSource.from_path("documento.pdf")
DocumentSource.from_bytes(b"...", filename="documento.pdf")
DocumentSource.from_stream(stream, filename="documento.pdf")
```

Metadados preservados quando disponiveis:

- `filename`;
- `declared_media_type`;
- `declared_extension`;
- `size` declarada ou resolvida;
- `origin_reference`;
- `metadata`.

## Ownership

| Source | Abre | Fecha | Observacao |
|---|---|---|---|
| `LocalPathSource` | resolver | resolver | arquivo aberto em binario e fechado no cleanup |
| `BytesSource` | resolver | resolver | cria `BytesIO` seekable |
| `StreamSource` seekable | consumidor | consumidor, salvo `close_on_cleanup=True` | posicao original e restaurada quando possivel |
| `StreamSource` nao seekable | consumidor/resolver | resolver fecha copia temporaria | conteudo e copiado em chunks para arquivo temporario |

O uso recomendado e:

```python
async with resolver.resolve(source) as resolved:
    identified = await identifier.identify(resolved)
```

## Deteccao

O detector inicial combina sinais reais e declarados:

- PDF, PNG, JPEG e TIFF por assinatura;
- XLSX por ZIP com estruturas OOXML minimas;
- CSV por heuristica textual conservadora;
- desconhecido quando nao ha evidencia suficiente.

Extensao e MIME declarados sao sinais auxiliares. Divergencias geram warnings,
mas nao bloqueiam o fluxo por padrao.

## Hash e identidade

`ContentHash` usa SHA-256 sobre os bytes reais completos, em chunks, sem incluir
nome, MIME ou extensao.

`DocumentIdentity` diferencia:

- `ContentHash`: identidade matematica dos bytes;
- `DocumentId`: identificador de entidade documental futura;
- `DocumentIdentity`: hash, tamanho, formato detectado e versao da identidade.

O formato canonico do hash e:

```text
sha256:<digest-hexadecimal>
```

## Integracao

`DocumentEngine` aceita entradas convenientes e as converte internamente:

- `str` e `Path` viram `DocumentSource.from_path`;
- `bytes`, `bytearray` e `memoryview` viram `DocumentSource.from_bytes`;
- streams com `read()` viram `DocumentSource.from_stream`;
- `DocumentSource` continua aceito diretamente.

API e CLI nao resolvem arquivos nem detectam formato. Elas adaptam a entrada para
contratos do Eixo e entregam ao engine.

## Fora do escopo

As fases 2.1 a 2.4 nao implementam:

- `LocalArtifactStore`;
- persistencia do original;
- ciclo de vida documental;
- jobs persistentes;
- PDF Inspector ou Excel Inspector completos;
- parsing, OCR, templates, schemas ou modelo canonico.

## Contradicoes e duvidas

- O indice de fases ainda lista algumas fases do Bloco 1 como planejadas, apesar
  de componentes do Bloco 1 ja existirem no workspace. A implementacao do Bloco 2
  foi feita sobre o estado real do codigo.
- A API HTTP ainda materializa uploads multipart em memoria na borda porque o
  parser multipart atual e minimalista. A fronteira arquitetural esta preservada:
  o kernel recebe `BytesSource`, nao tipos HTTP.
