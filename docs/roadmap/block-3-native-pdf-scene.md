# Bloco 3 - Decomposicao nativa e cena visual de PDF

Status: em andamento.

Dependencias: Blocos 1 e 2 concluidos.

## Objetivo

Construir uma capability de PDF capaz de decompor documentos digitais em uma
cena visual nativa, preservando conteudo, geometria, tipografia, imagens,
vetores, transformacoes, transparencia, mascaras, clipping, ordem de desenho,
recursos internos, relacoes entre objetos e proveniencia.

O resultado nao deve ser apenas texto extraido. O PDF deve ser tratado como uma
cena grafica reconstruivel e versionada.

Fluxo conceitual:

```text
PDF original
  -> objetos e recursos nativos
  -> elementos graficos ordenados
  -> cena visual canonica da pagina
  -> artefato reconstruivel e versionado
```

O bloco nao implementa editor visual, alteracao de PDF, exportacao de PDF
alterado, OCR, reconstrucao semantica, tabelas reconstruidas, templates ou IA
semantica.

## Representacoes Produzidas

### NativePDFParseArtifact

Representacao nativa que preserva o que foi encontrado no PDF com o minimo
possivel de interpretacao:

- objetos;
- referencias;
- content streams;
- recursos;
- instrucoes graficas;
- agrupamentos fornecidos pelo provider;
- coordenadas originais;
- informacoes especificas do PDF.

### PDFPageScene

Cena visual normalizada independente do provider:

- elementos ordenados;
- texto;
- imagens;
- vetores;
- links;
- anotacoes;
- clipping;
- camadas;
- geometria canonica;
- relacoes entre recursos e ocorrencias.

A representacao nativa preserva fidelidade e evidencia. A cena visual
normalizada facilita preview, selecao, diagnostico e edicao futura.

## Fases

### 3.1 - Contratos e providers nativos de PDF

Status: concluida.

Criar a fronteira entre o nucleo do Eixo e bibliotecas concretas de PDF.

Contratos conceituais:

- `PDFNativeProvider`;
- `PDFInspectionProvider`;
- `PDFContentProvider`;
- `PDFResourceProvider`;
- `PDFRenderingProvider`, apenas como contrato futuro.

O primeiro provider real pode usar PyMuPDF, PDFium ou equivalente, mas objetos
da biblioteca concreta nao podem aparecer nos contratos publicos.

O provider deve declarar suporte a capacidades como caracteres, glifos,
palavras, blocos nativos, imagens, ocorrencias de imagem, vetores, clipping,
anotacoes, camadas, ordem de content stream e fontes incorporadas.

### 3.2 - PDF Inspector tecnico

Criar a inspecao autoritativa especifica de PDF.

Deve identificar validade estrutural, versao, quantidade de paginas, metadados,
caixas, rotacoes, dimensoes, criptografia, exigencia de senha, permissoes,
presenca de texto, imagens, vetores, anotacoes, formularios, camadas opcionais
e sinais basicos de PDF escaneado ou hibrido.

Estados de criptografia:

- `not_encrypted`;
- `encrypted_unlocked`;
- `password_required`;
- `invalid_password`;
- `unsupported_encryption`.

Senhas nao podem ser persistidas, registradas em logs, retornadas pela API,
incluidas em jobs ou adicionadas a proveniencia.

Separacao de responsabilidade:

- Fase 2.8 responde se e seguro tentar abrir o conteudo como PDF.
- Fase 3.2 responde se o provider consegue abrir e descrever tecnicamente o PDF.

### 3.3 - Geometria e coordenadas canonicas

Definir o sistema geometrico oficial do Eixo:

- origem no canto superior esquerdo;
- eixo X cresce para a direita;
- eixo Y cresce para baixo;
- unidade principal em ponto PDF;
- bounding box como `x`, `y`, `width`, `height`;
- coordenadas normalizadas entre 0 e 1;
- referencia na pagina visivel apos crop e rotacao.

Modelos necessarios:

- `Point`;
- `Size`;
- `BoundingBox`;
- `NormalizedBoundingBox`;
- `Quad`;
- `Polygon`;
- `AffineTransform`;
- `PageGeometry`;
- `CoordinateSystem`.

A geometria deve preservar MediaBox, CropBox, BleedBox, TrimBox, ArtBox,
rotacao, transformacoes entre sistemas, coordenadas originais, coordenadas
canonicas, transformacao inversa, escala, inclinacao, espelhamento e translacao.

### 3.4 - Recursos, objetos e content streams

Construir inventario tecnico de objetos indiretos, referencias internas,
paginas, content streams, XObjects, Form XObjects, fontes, imagens, mascaras,
ExtGState, color spaces, patterns, shadings, clipping paths, recursos herdados,
Optional Content Groups, anotacoes, links e formularios.

Referencias proprias do Eixo:

- `PDFObjectReference`;
- `PDFContentStreamReference`;
- `PDFResourceReference`;
- `PDFFontReference`;
- `PDFImageReference`;
- `PDFFormReference`.

Quando possivel, preservar `content_stream_index`, `operation_index`,
`paint_order` e `z_order`. Ordem logica de leitura, ordem nativa do provider,
ordem grafica de desenho e ordem normalizada posterior nao sao equivalentes.

### 3.5 - Fontes e tipografia

Criar `PDFFontResource`, `PDFFontCatalog`, `PDFTextStyle` e
`PDFGlyphMetrics`.

Preservar, quando disponivel: nome interno, familia normalizada, PostScript
name, subset, fonte incorporada, fonte parcialmente incorporada, encoding, mapa
Unicode, metricas, ascender, descender, peso, italico, monoespacada, serifada,
direcao, escrita vertical, tamanho, cor, opacidade, render mode, espacamento e
transformacao textual.

Fontes incorporadas podem ser preservadas como artefatos internos quando legal e
tecnicamente permitido, mas nao devem ser expostas indiscriminadamente como
arquivos publicos.

### 3.6 - Texto granular e hierarquia textual nativa

Extrair texto no maior nivel de detalhe viavel:

```text
NativeTextBlock
  -> NativeTextLine
  -> NativeTextSpan
  -> NativeGlyph ou NativeCharacter
```

Produzir `NativeWord` quando palavras puderem ser determinadas com seguranca.

Cada glifo ou caractere deve preservar Unicode, glyph id, posicao, bounding box,
quad, avanco, baseline, origem, fonte, estilo, content stream, ordem de pintura,
confianca da decodificacao e metodo de extracao.

Regra fundamental: bloco nativo nao e paragrafo; linha nativa nao e linha
semantica. Paragrafos, titulos e secoes pertencem ao Bloco 6.

Texto convertido em curvas deve permanecer como vetor, sem afirmar existencia de
texto nativo.

### 3.7 - Imagens, mascaras e ocorrencias

Separar recurso de imagem e ocorrencia visual.

`PDFImageResource` preserva identificador, hash, bytes originais quando
disponiveis, formato, dimensoes, bits por componente, color space, compressao,
mascara, soft mask, transparencia, artefato e objeto PDF de origem.

`PDFImageOccurrence` preserva pagina, recurso utilizado, bounding box, quad,
matriz de transformacao, recorte, clipping, opacidade, blend mode, ordem de
desenho, Form XObject pai e visibilidade.

A mesma imagem pode possuir varias ocorrencias.

### 3.8 - Vetores e estado grafico

Extrair elementos graficos nativos como `VectorPath`, `LineSegment`,
`Rectangle`, `BezierCurve`, `Polygon`, `FilledRegion`, `Stroke`,
`ShadingReference` e `PatternReference`.

Preservar comandos de caminho, linhas, curvas, fechamento, fill, stroke, largura
do traco, line cap, line join, dash pattern, cor, color space, opacidade, blend
mode, transformacao, clipping, winding rule, ordem de pintura e referencia ao
content stream.

Criar `PDFClippingPath` e permitir referencias a `clip_path_reference`,
`mask_reference` e `soft_mask_reference`.

Sinais como `possible_separator` ou `possible_table_border` sao permitidos, mas
reconstrucao de tabelas nao pertence a este bloco.

### 3.9 - Links, anotacoes, formularios e camadas

Preservar componentes interativos e opcionais:

- links com area clicavel, URI, destino interno, pagina de destino, acao e bbox;
- anotacoes com tipo, posicao, conteudo, autor, data, aparencia, cor, flags e
  relacao com a pagina;
- campos AcroForm basicos com tipo, nome, valor, opcoes, posicao, aparencia,
  estado, flags, somente leitura e obrigatoriedade;
- Optional Content Groups por `PDFLayer` e `PDFLayerMembership`.

Nao implementar edicao ou assinatura de formularios.

### 3.10 - PDFPageScene

Montar a cena visual de cada pagina.

Estrutura sugerida:

```text
PDFPageScene
  -> page_id
  -> geometry
  -> ordered_elements
  -> text_elements
  -> image_occurrences
  -> vector_elements
  -> clipping_paths
  -> links
  -> annotations
  -> form_fields
  -> layers
  -> resource_references
  -> warnings
  -> limitations
```

Contrato base: `PDFVisualElement` com `element_id`, `element_type`, `page_id`,
`bbox`, `normalized_bbox`, `quad` ou `path`, `transform`, `paint_order`,
`z_order`, `opacity`, `blend_mode`, `clip_reference`, `layer_reference`,
`parent_reference`, `source_reference`, `extraction_method`, `fidelity` e
`provenance`.

Identificadores devem ser deterministicos quando possivel, estaveis entre
execucoes equivalentes e independentes de enderecos de memoria.

### 3.11 - NativePDFSceneArtifact

Consolidar a extracao em um artefato proprio do Eixo:

```text
NativePDFSceneArtifact
  -> artifact_version
  -> document_id
  -> source_artifact
  -> inspection
  -> document_resources
  -> pages
  -> warnings
  -> limitations
  -> fidelity_summary
  -> editability_hints
  -> provenance
```

Classificacao de fidelidade:

- `native_exact`;
- `native_normalized`;
- `provider_reconstructed`;
- `heuristic`;
- `raster_only`;
- `unsupported`.

Indicios de editabilidade:

- `native_editable`;
- `partially_editable`;
- `reconstruction_required`;
- `raster_only`;
- `unknown`.

O artefato nao pode ser apenas a serializacao bruta do provider.

### 3.12 - Integracao publica, armazenamento e jobs

Integrar a capability nativa de PDF ao Eixo preservando as interfaces genericas:

- `engine.inspect("documento.pdf")`;
- `engine.parse("documento.pdf")`;
- `POST /v1/documents:inspect`;
- `POST /v1/documents:parse`;
- `eixo inspect documento.pdf`;
- `eixo parse documento.pdf`.

Wrappers especializados como `inspect_pdf` ou `parse_pdf` podem existir, mas nao
podem conter logica propria.

Processamento seletivo deve permitir paginas, extracao textual, visual ou full
fidelity por perfis coerentes como `basic`, `textual`, `visual` e
`full_fidelity`.

`NativePDFSceneArtifact` deve ser armazenado pelo `ArtifactStore`. Imagens e
recursos grandes devem ser armazenados separadamente e referenciados. Parsing
completo deve funcionar por jobs locais persistentes.

### 3.13 - Corpus, golden tests e regressao visual

Criar corpus minimo com PDFs de texto digital simples, multiplas fontes, fonte
subset, texto caractere por caractere, texto rotacionado, pagina rotacionada,
crop box, imagens repetidas, mascaras, pagina inteira como imagem, vetores,
bordas de tabela, transparencia, clipping, links, anotacoes, formularios,
camadas, PDF protegido, PDF hibrido, texto convertido em curvas, estrutura
malformada aceitavel e multiplas paginas.

Golden tests devem validar paginas, geometria, texto, caracteres, fontes,
imagens, recursos, posicoes, transformacoes, vetores, ordem de pintura,
relacoes, warnings, proveniencia e fidelidade.

Coordenadas de ponto flutuante devem usar tolerancias documentadas, sem esconder
erros geometricos por normalizacao excessiva.

Criar infraestrutura para futura comparacao visual entre renderizacao original e
renderizacao reconstruida da cena. Nesta fase, um renderer diagnostico simples
ou exportacao de overlay e suficiente.

Metricas por documento:

- `text_elements`;
- `image_resources`;
- `image_occurrences`;
- `vector_paths`;
- `unresolved_fonts`;
- `unsupported_operations`;
- `elements_without_geometry`;
- `elements_without_source_reference`.

## Fora Do Escopo

- OCR;
- reconstrucao semantica;
- titulos, paragrafos semanticos, listas e secoes;
- tabelas reconstruidas;
- rotulos e valores;
- classificacao documental;
- templates;
- schemas de extracao;
- edicao visual;
- movimentacao de elementos;
- substituicao de texto;
- exportacao de PDF alterado;
- colaboracao;
- frontend estilo Canva;
- renderizacao definitiva;
- conversao completa para HTML ou SVG;
- interpretacao propria de toda a especificacao PDF.

## Marco De Conclusao

O Bloco 3 estara concluido quando o Eixo conseguir transformar um PDF digital em
`NativePDFSceneArtifact` com paginas, geometria canonica, texto granular, fontes,
imagens, vetores, transformacoes, clipping, transparencia, ordem visual,
recursos, links, anotacoes, relacoes, proveniencia e avaliacao de fidelidade.

Ao final, deve ser possivel construir um preview de diagnostico que desenhe os
elementos extraidos sobre a pagina e permita selecionar cada elemento pelo seu
`element_id`.

Isso nao significa que todos os PDFs serao totalmente editaveis. Significa que o
Eixo tera preservado a estrutura necessaria para visualizar, selecionar,
compreender, reconstruir e futuramente editar.

## Divisao Recomendada Em Prompts

| Prompt | Escopo |
|---|---|
| 3.A | Fases 3.1 a 3.3: contratos, provider, PDF Inspector, geometria |
| 3.B | Fases 3.4 a 3.6: objetos, content streams, fontes, texto granular |
| 3.C | Fases 3.7 a 3.9: imagens, mascaras, vetores, clipping, links, anotacoes, formularios e camadas |
| 3.D | Fases 3.10 a 3.12: `PDFPageScene`, `NativePDFSceneArtifact`, integracao publica e armazenamento |
| 3.E | Fase 3.13: corpus, golden tests, regressao geometrica e visual |
