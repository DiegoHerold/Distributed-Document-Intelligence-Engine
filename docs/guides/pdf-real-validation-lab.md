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

## Upload Temporario

Quando a API local estiver em execucao, a pagina `/lab` abre uma entrada simples
para uso exploratorio:

```text
abrir /lab -> arrastar PDFs -> processar -> abrir validacao -> limpar sessao
```

Esse modo cria uma `DiagnosticTemporarySession` e grava todos os dados sob um
`TemporaryDiagnosticStore` isolado:

```text
temporary-diagnostics/
`-- session-id/
    |-- uploads/
    |-- artifacts/
    |-- previews/
    |-- reports/
    `-- runtime/
```

O upload aceita um ou varios PDFs, valida assinatura real `%PDF-`, tamanho e
limites configurados antes de processar, e nao confia apenas em extensao, nome
ou `Content-Type`. Cada documento fica independente, com estado, etapa,
warnings, limitacoes, acao para abrir, remocao individual e exportacao manual.

O processamento temporario usa o mesmo parser oficial por meio de
`DocumentEngine.local(data_directory=session/runtime)`. Assim, os artefatos do
parser ficam no runtime temporario da sessao e nao entram no `ArtifactStore`
oficial da aplicacao, no `PersistentJobStore`, no corpus ou no historico
permanente.

A pagina envia heartbeat periodico e tenta fechar a sessao por `sendBeacon` em
`pagehide`/`beforeunload`. Como eventos de fechamento do navegador sao
best effort, `TemporaryDiagnosticSessionCleaner` tambem remove sessoes sem
heartbeat depois do periodo de seguranca e apaga sessoes que ultrapassarem o
tempo maximo de retencao.

No modo temporario, o laboratorio mostra:

```text
Historico desativado no modo temporario
```

As avaliacoes manuais ficam somente em memoria enquanto a pagina esta aberta,
exceto se o usuario exportar explicitamente o pacote de diagnostico. A
exportacao nao inclui o PDF original por padrao; ele so entra no pacote se a
opcao explicita `include_original=true` for usada.

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
                    |-- page-001-original-standard.png
                    |-- page-001-original-high.png
                    |-- page-001-original-ultra.png
                    |-- page-001-overlay.png
                    |-- page-001-elements.json
                    `-- page-001-scene.json
```

`page-*-original-standard.png`, `page-*-original-high.png` e
`page-*-original-ultra.png` sao renderizacoes independentes da pagina original em
qualidades progressivas. O laboratorio inicia em `high` e promove para `ultra`
em zoom alto sem mudar a origem ou a escala canonica das camadas. O arquivo
`page-*-original.png` permanece como alias de compatibilidade da renderizacao
`high`. Se o renderer opcional nao estiver instalado, o validador gera uma
pagina-base diagnostica e registra a limitacao. `page-*-overlay.png` desenha
elementos extraidos a partir da cena para diagnostico estatico.

`page-*-elements.json` contem somente dados necessarios ao diagnostico local:
geometria, elementos, relacoes, estatisticas, warnings e limitacoes. Ele nao
incorpora bytes de imagens, fontes binarias ou objetos internos do provider.

## Laboratorio Interativo

`report.html` tambem e o laboratorio interativo autocontido da Fase 3.14.2. Ele
consome os artefatos da Fase 3.14.1 e nao chama novamente o parser.

Funcionalidades disponiveis:

- selecao de elementos clicando sobre a pagina por hit testing geometrico;
- preview unico com pagina original como bitmap base e camadas vetoriais
  interativas sobrepostas;
- renderizacao progressiva em qualidade `standard`, `high` e `ultra`;
- modos da camada: limpo, somente selecao, diagnostico leve e diagnostico
  completo;
- labels configuraveis: nunca, hover, selecao ou sempre;
- zoom, pan, ajuste a largura/pagina e intensidade da camada sobreposta;
- filtros por texto, imagem, vetor, clipping, interativos, ID, recurso,
  visibilidade e granularidade textual;
- busca por texto extraido, ID, tipo, fonte e recurso;
- listas virtualizadas para documentos com milhares de elementos;
- painel destacado de valor extraido e abas de propriedades;
- paineis de texto, imagens, vetores, recursos, warnings e achados;
- navegacao de recurso para elementos relacionados;
- multisselecao temporaria com Ctrl+clique e `DiagnosticCompositeSelection`
  diagnostica no painel JSON;
- acao de expandir selecao para a linha textual quando as relacoes nativas
  permitem;
- avaliacao manual salva separadamente no `localStorage` do navegador;
- consulta de historico por `history.json`;
- `comparison.json` com diferencas de contagem em relacao a execucao anterior.

No fluxo temporario da API, o relatorio injeta uma barra de sessao com retorno
para os uploads da propria sessao, remocao/limpeza e exportacao manual. Esse
estado e efemero: nao deve ser usado como relatorio pronto ou corpus permanente.

A camada interativa nao usa `page-*-overlay.png` como superficie de clique nem
cria uma segunda representacao da mesma pagina. O HTML monta um unico
`InteractivePDFPageViewport`: imagem original em alta resolucao, camada
vetorial de elementos, hover, selecao, labels temporarios e hit testing. Todas
as camadas usam a mesma origem, tamanho, zoom, scroll e `PageViewportTransform`.
O hit testing converte coordenadas da viewport para coordenadas canonicas da
pagina, aplica area minima de clique e ordena candidatos sobrepostos por
prioridade, granularidade, area e ordem visual.

Valores textuais exibidos no laboratorio sao enriquecidos a partir dos
artefatos persistidos, como `PDFNativeTextArtifact`, sem alterar a cena oficial.
IDs completos continuam disponiveis no painel JSON, mas as listas mostram
rotulos legiveis como valor, tipo e pagina.

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
