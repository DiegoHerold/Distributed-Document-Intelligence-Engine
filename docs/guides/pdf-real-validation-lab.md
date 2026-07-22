# Laboratorio de Validacao PDF

O laboratorio da Fase 3.14 e uma ferramenta tecnica para validar PDFs reais em
ambiente local controlado.

Ele nao e viewer de producao, editor ou sistema de renderizacao definitivo.

## CLI

Validar uma pasta:

```bash
eixo pdf validate ./pdfs-reais --profile full-fidelity --diagnostic-preview --output ./diagnostics
```

Validar um arquivo:

```bash
eixo pdf validate documento.pdf --profile visual --output ./diagnostics
```

Paginas especificas:

```bash
eixo pdf validate documento.pdf --pages 1-3 --profile visual
```

Senha temporaria:

```bash
eixo pdf validate protegido.pdf --password "senha-local"
```

A senha e encaminhada para `ParseRequest.options` e nao e gravada nos relatorios.

## Pacote de Diagnostico

Cada documento recebe uma pasta propria:

```text
diagnostics/
|-- index.html
|-- summary.json
|-- history.json
|-- batch-report.json
|-- batch-report.html
`-- documents/
    `-- document-slug/
        |-- document.json
        `-- runs/
            `-- diagnostic-run-id/
                |-- inspection.json
                |-- artifact-summary.json
                |-- native-scene-summary.json
                |-- report.json
                |-- report.html
                |-- findings.json
                |-- warnings.json
                |-- limitations.json
                |-- assessment.json
                |-- comparison.json
                |-- manual-evaluation.json
                `-- pages/
                    |-- page-001-original.png
                    |-- page-001-overlay.png
                    |-- page-001-elements.json
                    `-- page-001-scene.json
```

`page-*-original.png` e uma renderizacao independente da pagina original quando
o adapter PyMuPDF estiver disponivel. Se o renderer opcional nao estiver
instalado, o validador gera uma pagina-base diagnostica e registra a limitacao.
`page-*-overlay.png` desenha elementos extraidos a partir da cena.

`page-*-elements.json` contem somente dados necessarios ao diagnostico local:
geometria, elementos, relacoes, estatisticas, warnings e limitacoes. Ele nao
incorpora bytes de imagens, fontes binarias ou objetos internos do provider.

## Laboratorio Interativo

`report.html` tambem e o laboratorio interativo autocontido da Fase 3.14.2. Ele
consome os artefatos da Fase 3.14.1 e nao chama novamente o parser.

Funcionalidades disponiveis:

- selecao de elementos clicando sobre a pagina;
- visualizacao somente original, somente overlay, lado a lado ou sobreposicao;
- zoom e opacidade compartilhados;
- filtros por texto, imagem, vetor, clipping, interativos, ID e recurso;
- paineis de texto, imagens, vetores, recursos, warnings e achados;
- navegacao de recurso para elementos relacionados;
- avaliacao manual salva separadamente no `localStorage` do navegador;
- consulta de historico por `history.json`;
- `comparison.json` com diferencas de contagem em relacao a execucao anterior.

O laboratorio e uma ferramenta tecnica local. Ele nao depende de internet, CDN,
API publica, Blocos 6, 7 ou 8, e nao modifica `NativePDFSceneArtifact` nem
`PDFPageScene`.

## Estados

Cada PDF e processado independentemente:

- `pending`
- `processing`
- `completed`
- `completed_with_warnings`
- `failed`
- `cancelled`

Uma falha em um documento nao interrompe os demais.

## Avaliacao Manual

`assessment.json` e `manual-evaluation.json` registram o template de revisao:

- status geral: `approved`, `approved_with_limitations`, `failed`,
  `needs_investigation`;
- dimensoes: `text`, `geometry`, `fonts`, `images`, `vectors`, `clipping`,
  `visual_order`, `resources`, `provenance`, `overall_fidelity`;
- valores: `pass`, `partial`, `fail`, `not_applicable`;
- observacoes tecnicas.

## Seguranca

- PDFs reais nao devem ser adicionados automaticamente ao repositorio.
- O processamento e local.
- Conteudo completo nao deve ser copiado para logs.
- Valores de formularios e senhas nao devem ser registrados.
- Promova para corpus permanente apenas PDFs autorizados e anonimizados.

## Relacao com Goldens

Quando um PDF real revelar falha:

1. investigar a causa;
2. criar PDF sintetico minimo que reproduza o problema;
3. corrigir o parser;
4. adicionar o sintetico ao corpus da Fase 3.13;
5. criar ou atualizar golden test explicitamente;
6. reprocessar o PDF real no laboratorio.
