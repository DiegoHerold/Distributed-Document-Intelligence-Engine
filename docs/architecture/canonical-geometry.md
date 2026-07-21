# Geometria Canonica

Status: Fase 3.3 implementada.

## Convencao Oficial

A geometria visual canonica do Eixo usa:

- origem no canto superior esquerdo da area visual oficial;
- eixo X crescendo da esquerda para a direita;
- eixo Y crescendo de cima para baixo;
- unidade absoluta `point`;
- `1 point = 1/72 inch`;
- rotacao positiva no sentido horario;
- valores `float` de precisao dupla;
- valores finitos obrigatorios;
- tolerancias centralizadas.

Pixels nunca sao unidade canonica. Conversoes para pixels exigem DPI explicito.

## Espacos

`CoordinateSpace` define `native`, `canonical`, `normalized`, `pixel` e
`object_local`.

## Modelos

O modulo publico e `eixo.geometry`.

Modelos principais:

- `Point`;
- `Vector`;
- `Size`;
- `BoundingBox`;
- `Polygon`;
- `Quad`;
- `Rotation`;
- `AffineMatrix`;
- `NormalizedPoint`;
- `NormalizedBoundingBox`;
- `PageGeometry`.

Unidades e politica:

- `CoordinateUnit`;
- `CoordinateSpace`;
- `PageBoxPolicy`;
- `GeometryTolerance`.

Erros:

- `GeometryValidationError`;
- `NonInvertibleTransformError`.

## Matriz Afim

A matriz canonica usa seis parametros:

```text
| a c e |
| b d f |
| 0 0 1 |
```

Aplicacao a ponto coluna:

```text
x' = a*x + c*y + e
y' = b*x + d*y + f
```

Composicao:

```text
A @ B
```

significa que `B` e aplicada primeiro e `A` depois.

## Normalizacao

`NormalizedPoint` e `NormalizedBoundingBox` sao estritos:

```text
0.0 <= x <= 1.0
0.0 <= y <= 1.0
```

Geometria fora da pagina nao sofre clamp silencioso. Use `clamp=True` apenas
quando o recorte proporcional for uma escolha explicita.

## Pagina PDF

O adapter `canonical_pdf_page_geometry()` fica em `eixo.pdf` e produz
`PageGeometry`.

Politica de area visual:

- `CropBox` quando disponivel;
- fallback para `MediaBox`;
- `PageBoxPolicy` permite selecionar explicitamente `MediaBox` ou `CropBox`.

A transformacao PDF nativo -> canonico considera origem inferior esquerda do
PDF, eixo Y nativo crescente para cima, origem canonica superior esquerda, eixo
Y canonico crescente para baixo, deslocamento de caixas, coordenadas negativas,
`UserUnit` e rotacoes de pagina 0, 90, 180 e 270 graus.

## Precisao

O Eixo usa `float` de precisao dupla. `NaN` e infinitos sao rejeitados,
igualdade geometrica deve usar `almost_equals()`, serializacao preserva valores
sem arredondamento destrutivo, e matrizes singulares nao podem ser invertidas.

Caixas degeneradas sao permitidas quando representam linhas, pontos ou ancoras.

## Exemplo

```python
from eixo.geometry import AffineMatrix, BoundingBox, Point, Size

page_size = Size(width=595.0, height=842.0)
box = BoundingBox(72.0, 100.0, 300.0, 150.0)

normalized = box.normalize(page_size)
restored = normalized.denormalize(page_size)
transformed = box.transform(AffineMatrix.rotation(90.0))

assert restored.almost_equals(box)
assert transformed.width > 0
assert AffineMatrix.rotation(90.0).apply_to_point(Point(1.0, 0.0)).almost_equals(
    Point(0.0, 1.0)
)
```

## Limites Atuais

- Clipping completo de poligonos complexos fica para fases futuras.
- O adapter PDF inicial cobre rotacoes de pagina ortogonais.
- Conversao para pixels exige DPI unico por chamada.
- A fase nao implementa decomposicao visual, texto granular, imagens, vetores
  ou cena visual.
