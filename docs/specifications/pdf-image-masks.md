# PDF Image Masks

Status: Fase 3.7 implementada parcialmente.

## Objetivo

Mascaras de imagem descrevem transparencia ou recorte visual associado a uma
imagem. Elas nao devem ser confundidas com ocorrencias visuais independentes.

Contratos:

- `PDFImageMaskReference`;
- `PDFSoftMaskResource`;
- `PDFColorKeyMask`;
- `PDFImageTransparency`;
- `PDFImageMaskType`.

## Tipos

Tipos iniciais:

- `image_mask`;
- `soft_mask`;
- `stencil_mask`;
- `color_key_mask`;
- `alpha_channel`;
- `unknown`.

`PDFImageTransparency` consolida opacidade, blend mode, referencia de mascara,
soft mask, color key e indicador de canal alpha quando conhecido.

## PyMuPDF

O adapter PyMuPDF resolve soft masks a partir do campo `smask` retornado por
`page.get_images(full=True)`. Quando a mascara tambem pode ser extraida por
xref, ela entra no catalogo como recurso tecnico com bytes referenciados por
hash e tamanho.

## Lacunas

- color key masks ainda dependem de exposicao mais rica do provider;
- alpha premultiplicado e composicao exata nao sao calculados;
- clipping path e estado grafico serao aprofundados na Fase 3.8.
