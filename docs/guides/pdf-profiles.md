# Perfis publicos de PDF

Fase: 3.12.

Os perfis publicos sao representados por `PDFParseProfile`:

- `basic`;
- `textual`;
- `visual`;
- `full_fidelity`.

`full-fidelity` e aceito na CLI e normalizado para `full_fidelity`.

## basic

Produz inspecao tecnica e resumo publico:

- validade e versao;
- numero de paginas;
- metadados seguros;
- criptografia;
- geometria de paginas;
- presenca de texto, imagens, vetores e formularios;
- warnings, limitacoes e proveniencia basica.

Persistencia: inspecao e resultado publico.

## textual

Inclui tudo de `basic` e executa:

- estrutura interna minima necessaria;
- catalogo de fontes;
- tipografia;
- texto nativo granular.

Persistencia: inspecao, tipografia, texto nativo e resultado publico.

## visual

Perfil recomendado para preview, selecao visual e analise de layout.

Inclui tudo de `textual` e executa:

- imagens;
- vetores;
- clipping;
- links, anotacoes, widgets e camadas best effort;
- `PDFPageScenesArtifact`;
- `NativePDFSceneArtifact`.

Persistencia: artefatos intermediarios visuais, cenas e artefato nativo final.

## full_fidelity

Perfil mais completo suportado atualmente.

Inclui o pipeline visual e habilita opcoes mais completas quando os contratos ja
suportam isso, como content streams, sumarios crus, bytes codificados de imagem,
representacoes normalizadas e programas de fonte permitidos.

Persistencia: todos os artefatos produzidos pelo perfil e resultado publico.

## Opcoes publicas

`PDFParseOptions` aceita:

- `profile`;
- `page_selection`, usando paginas publicas 1-based;
- `include_hidden_elements`;
- `password`;
- `timeout`;
- `persist_artifacts`.

`password` nao aparece em `to_dict()`, `safe_options()` ou logs estruturados; a
serializacao indica apenas `password_provided`.
