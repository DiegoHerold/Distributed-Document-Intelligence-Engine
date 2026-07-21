# PDF Editability Hints

Status: inicial, Fase 3.11.

Editabilidade e um indicio tecnico, nao uma promessa de editor. O Eixo registra
se os dados necessarios parecem existir, mas nao executa edicao nesta fase.

## Estados

- `native_editable`;
- `partially_editable`;
- `reconstruction_required`;
- `raster_only`;
- `not_editable`;
- `unknown`.

## Resumo

`PDFEditabilitySummary` consolida:

- status geral;
- status de texto;
- status de imagem;
- status de vetor;
- status de formulario;
- contagens por estado;
- motivos seguros.

## Politica

Texto pode ser parcialmente editavel quando possui Unicode e geometria, mas
fontes ou metricas ainda nao garantem reconstrucao perfeita. Imagens podem ser
`raster_only` quando a substituicao nativa exigiria tratamento de bytes,
mascaras ou clipping fora desta fase. Vetores podem exigir reconstrucao quando
dependem de patterns, shadings ou estados graficos incompletos.
