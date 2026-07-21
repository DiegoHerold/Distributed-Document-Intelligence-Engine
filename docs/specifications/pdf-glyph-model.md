# PDF Glyph Model

Status: Fases 3.5 e 3.6 implementadas parcialmente.

`NativeGlyph` representa o desenho tipografico individual. Ele nao e igual a um
caractere Unicode.

Um glifo pode mapear para:

- nenhum Unicode;
- um caractere;
- varios caracteres;
- uma ligatura;
- caractere privado ou invalido.

`NativeCharacter` representa a unidade Unicode quando disponivel. O modelo
preserva `unicode_text` e `normalized_unicode_text` separadamente.

## Geometria

Glifos usam geometria canonica:

- `origin`;
- `bounding_box`;
- `quad`;
- `baseline_reference`;
- `text_matrix`;
- `effective_transform`.

Quando a geometria vem do provider, a confianca fica parcial ou aproximada.
