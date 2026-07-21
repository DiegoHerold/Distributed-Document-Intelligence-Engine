# ADR-0008 - Geometria canonica

## Status

Aceita.

## Contexto

O Bloco 3 precisa transformar PDFs em cenas visuais reconstruiveis e
comparaveis. Antes desta decisao, a geometria existente estava limitada a
`PDFPageGeometry`, com `width`, `height`, `rotation`, `media_box` e `crop_box`
representados por valores simples ou tuplas. Nao havia um modulo geometrico
central para pontos, caixas, quads, poligonos, matrizes, unidades, tolerancias
ou coordenadas normalizadas.

Diagnostico real da Fase 3.3:

- nao existem tipos publicos `Point`, `Size`, `BoundingBox`, `Polygon`, `Quad`,
  `Rotation` ou `AffineMatrix`;
- nao existem modelos normalizados;
- `PDFPageGeometry` e o unico contrato visual atual;
- o provider PyMuPDF converte retangulos nativos para tuplas e calcula largura e
  altura diretamente;
- nao ha vazamento de tipos `fitz` nos contratos publicos;
- nao ha dependencia geometrica externa, como NumPy ou Shapely;
- nao ha testes de propriedade existentes;
- a suite baseline executada antes da fase teve 146 testes passando e uma falha
  temporal em job persistente ao buscar resultado antes da persistencia.

## Decisao

Adotar um sistema geometrico canonico em `eixo.geometry`, independente de PDF,
OCR, API, UI, provider ou biblioteca matematica externa.

Convencao oficial:

- origem no canto superior esquerdo da area visual oficial;
- eixo X cresce da esquerda para a direita;
- eixo Y cresce de cima para baixo;
- unidade absoluta canonica: `point`;
- `1 point = 1/72 inch`;
- rotacao positiva em graus no sentido horario;
- valores de rotacao normalizados para `0 <= degrees < 360`;
- numero interno: `float` de precisao dupla;
- valores `NaN` e infinitos sao rejeitados;
- tolerancias sao centralizadas;
- modelos sao imutaveis e serializaveis.

Matriz afim canonica:

```text
| a c e |
| b d f |
| 0 0 1 |
```

Aplicada a ponto coluna:

```text
x' = a*x + c*y + e
y' = b*x + d*y + f
```

Composicao:

```text
A @ B
```

significa que `B` e aplicada primeiro e `A` depois.

## Paginas PDF

Para PDF, a area visual oficial usa `CropBox` quando disponivel e `MediaBox`
como fallback. A transformacao PDF nativo -> canonico considera:

- deslocamento da caixa escolhida;
- eixo Y nativo crescente para cima;
- eixo Y canonico crescente para baixo;
- `UserUnit`;
- rotacoes de pagina 0, 90, 180 e 270 graus.

Rotacoes arbitrarias continuam suportadas no modelo geral, mas a transformacao
oficial de pagina PDF trata inicialmente rotacoes ortogonais, que sao as
rotacoes de pagina padronizadas pelo PDF.

## Coordenadas Normalizadas

Modelos `Normalized*` sao estritos e aceitam apenas valores em `[0, 1]`.
Geometria fora da pagina nao sofre clamp silencioso. Operacoes que precisam
recortar devem chamar explicitamente `clip_to_page()` ou normalizar com
`clamp=True`.

## Consequencias

- Todos os formatos futuros podem reutilizar a mesma geometria.
- Providers convertem para contratos publicos sem expor tipos externos.
- O inspector passa a carregar geometria canonica de pagina.
- Operacoes de pagina, preview, OCR e cena visual compartilham a mesma base.
- Operacoes complexas de clipping de poligonos ficam fora do escopo inicial e
  devem ser adicionadas com testes proprios.
