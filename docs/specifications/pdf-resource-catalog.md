# PDF Resource Catalog

Status: Fase 3.4 implementada.

## Objetivo

`PDFResourceCatalog` consolida recursos tecnicos do PDF sem confundir recurso e
ocorrencia visual.

Categorias:

- `PDFFontResourceDescriptor`;
- `PDFImageResourceDescriptor`;
- `PDFXObjectResource`;
- `PDFGraphicsStateResource`;
- `PDFColorSpaceResource`;
- `PDFPatternResource`;
- `PDFShadingResource`;
- `PDFLayerResource`;
- `PDFUnknownResource`.

## Escopos

`PDFResourceScope` diferencia:

- `document`;
- `page`;
- `inherited`;
- `form_xobject`;
- `content_stream`;
- `inline`.

O mesmo nome, como `/F1` ou `/Im0`, pode aparecer em escopos diferentes sem
colidir.

## Recursos desconhecidos

Recursos nao reconhecidos sao preservados como `PDFUnknownResource`, com tipo
declarado, resumo seguro, escopo e proveniencia. Eles nao sao descartados.

## Dados brutos

O catalogo nao embute bytes grandes. Resumos de dicionario sao limitados e
seguros. Conteudo grande devera usar `ArtifactStore` em fases futuras.
