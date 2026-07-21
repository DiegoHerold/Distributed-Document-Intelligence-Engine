# PDF Image Transforms

Status: Fase 3.7 implementada parcialmente.

## Objetivo

Transformacoes de imagem preservam como um recurso foi pintado na pagina sem
alterar a definicao do recurso.

Cada `PDFImageOccurrence` pode carregar:

- bounding box canonica;
- bounding box normalizada;
- quad;
- matriz afim;
- ordem de pintura;
- DPI efetivo;
- status de clipping;
- visibilidade;
- confianca geometrica.

## Coordenadas

As coordenadas publicas seguem [canonical-geometry.md](../architecture/canonical-geometry.md):
origem no canto superior esquerdo, X para a direita, Y para baixo e unidade em
points.

Quando o provider entrega bbox fora da pagina, o Eixo nao normaliza
silenciosamente. A ocorrencia permanece com bbox absoluto e visibilidade como
`partially_clipped` ou `outside_page`.

## DPI Efetivo

O DPI efetivo e calculado por:

```text
dpi = pixels / (points / 72)
```

O valor e diagnostico. Ele nao prova a resolucao original nem implica qualidade
visual, pois a imagem pode ter sido recomprimida, mascarada ou transformada.
