from __future__ import annotations

import json
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse

from eixo import DocumentEngine
from eixo.core import ValidationError
from eixo.diagnostics import TemporaryDiagnosticStore
from eixo_api.responses import json_response
from eixo_api.upload import HttpUploadedFile, UploadTooLargeError, read_limited_body

MULTIPART_OVERHEAD_LIMIT = 1024 * 1024

router = APIRouter(prefix="/lab", tags=["PDF Validation Lab"])


@dataclass(frozen=True, slots=True)
class LabUpload:
    files: tuple[HttpUploadedFile, ...]
    fields: dict[str, str]


@router.get("", summary="Open the temporary PDF validation lab")
async def open_lab() -> HTMLResponse:
    return HTMLResponse(_upload_page_html())


@router.get("/sessions/{session_id}", summary="Open an existing lab session")
async def open_existing_session(session_id: str, request: Request) -> HTMLResponse:
    store = _store(request)
    session = store.get_session(session_id)
    payload = session.to_public_dict()
    payload["heartbeat_interval"] = store.config.heartbeat_interval
    payload["privacy"] = _privacy_message()
    return HTMLResponse(_upload_page_html(session_payload=payload))


@router.post("/sessions", summary="Create a temporary diagnostic session")
async def create_session(request: Request):
    store = _store(request)
    session = store.create_session()
    payload = session.to_public_dict()
    payload["heartbeat_interval"] = store.config.heartbeat_interval
    payload["privacy"] = _privacy_message()
    return json_response(payload, status_code=201)


@router.post("/sessions/{session_id}/heartbeat", summary="Heartbeat a lab session")
async def heartbeat_session(session_id: str, request: Request):
    store = _store(request)
    session = store.heartbeat(session_id)
    payload = session.to_public_dict()
    payload["heartbeat_interval"] = store.config.heartbeat_interval
    return json_response(payload)


@router.post("/sessions/{session_id}/close", summary="Close a lab session")
async def close_session_beacon(session_id: str, request: Request):
    return json_response(_store(request).close_session(session_id))


@router.delete("/sessions/{session_id}", summary="Clear a lab session")
async def clear_session(session_id: str, request: Request):
    return json_response(_store(request).close_session(session_id))


@router.post(
    "/sessions/{session_id}/documents",
    summary="Upload and process PDFs in a temporary diagnostic session",
)
async def upload_documents(session_id: str, request: Request):
    store = _store(request)
    upload = await _read_lab_upload(request)
    if not upload.files:
        raise ValidationError("At least one PDF file is required")
    profile = upload.fields.get("profile", "visual").replace("-", "_")
    if profile not in {"visual", "full_fidelity"}:
        raise ValidationError("profile must be visual or full_fidelity")
    documents = [
        store.save_upload(
            session_id,
            filename=file.filename,
            content=file.content,
        )
        for file in upload.files
    ]
    for document in documents:
        await store.process_document(
            session_id,
            document.document_id,
            profile=profile,
            engine_factory=_temporary_engine_factory(request),
        )
    session = store.get_session(session_id)
    payload = session.to_public_dict()
    payload["auto_open_document_id"] = (
        documents[0].document_id if len(documents) == 1 else None
    )
    return json_response(payload)


@router.delete(
    "/sessions/{session_id}/documents/{document_id}",
    summary="Remove one temporary diagnostic document",
)
async def remove_document(session_id: str, document_id: str, request: Request):
    return json_response(_store(request).remove_document(session_id, document_id))


@router.get(
    "/sessions/{session_id}/documents/{document_id}/files/{path:path}",
    summary="Read a generated temporary diagnostic report file",
)
async def read_report_file(
    session_id: str,
    document_id: str,
    path: str,
    request: Request,
):
    resolved = _store(request).resolve_report_file(session_id, document_id, path)
    if Path(path).name == "report.html":
        return HTMLResponse(
            _inject_temporary_report_controls(
                resolved.read_text(encoding="utf-8"),
                session_id=session_id,
            )
        )
    return FileResponse(resolved)


@router.get(
    "/sessions/{session_id}/documents/{document_id}/export",
    summary="Export a temporary diagnostic package",
)
async def export_document(
    session_id: str,
    document_id: str,
    request: Request,
    include_original: bool = False,
):
    export_path = _store(request).export_document(
        session_id,
        document_id,
        include_original=include_original,
    )
    return FileResponse(
        export_path,
        filename=export_path.name,
        media_type="application/zip",
    )


@router.post("/cleanup", summary="Run temporary diagnostic cleanup")
async def cleanup_sessions(request: Request):
    removed = _store(request).cleanup_expired()
    return json_response({"removed_session_ids": removed})


async def _read_lab_upload(request: Request) -> LabUpload:
    config = request.app.state.eixo.config
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type.lower():
        raise ValidationError("Content-Type must be multipart/form-data")
    max_size = (
        config.max_upload_size * config.max_temporary_diagnostic_files
        + MULTIPART_OVERHEAD_LIMIT
    )
    body = await read_limited_body(request, max_size=max_size)
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + body
    )
    if not message.is_multipart():
        raise ValidationError("Invalid multipart body")
    fields: dict[str, str] = {}
    files: list[HttpUploadedFile] = []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name is None:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is None:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8")
            continue
        if name not in {"file", "files"}:
            continue
        if len(files) >= config.max_temporary_diagnostic_files:
            raise UploadTooLargeError("Too many files for one diagnostic session")
        files.append(
            HttpUploadedFile(
                filename=filename,
                content_type=part.get_content_type(),
                content=payload,
            )
        )
    return LabUpload(files=tuple(files), fields=fields)


def _store(request: Request) -> TemporaryDiagnosticStore:
    return request.app.state.eixo.require_temporary_diagnostic_store()


def _temporary_engine_factory(request: Request):
    config = request.app.state.eixo.config
    injected = request.app.state.eixo.temporary_diagnostic_engine_factory
    if injected is not None:
        return injected

    def create_engine(data_directory: Path):
        return DocumentEngine.local(
            default_timeout=config.request_timeout,
            data_directory=data_directory,
        )

    return create_engine


def _privacy_message() -> str:
    return (
        "Os PDFs sao processados somente nesta sessao. Os arquivos e resultados "
        "sao excluidos ao limpar ou encerrar a sessao. Uma limpeza automatica "
        "tambem remove sessoes abandonadas."
    )


def _upload_page_html(session_payload: dict[str, Any] | None = None) -> str:
    payload = json.dumps(
        {
            "privacy": _privacy_message(),
            "session": session_payload,
        }
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Laboratorio de validacao de PDF</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --ink: #17212b;
      --muted: #617283;
      --line: #d8dee7;
      --accent: #087f8c;
      --accent-dark: #066773;
      --danger: #b42318;
      --surface: #fff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
      font-size: 14px;
      line-height: 1.5;
    }}
    header {{
      background: #101820;
      color: #fff;
      padding: 18px 24px;
    }}
    header h1 {{
      margin: 0;
      font-size: 22px;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      gap: 18px;
    }}
    .dropzone {{
      background: var(--surface);
      border: 2px dashed #91a7b5;
      border-radius: 10px;
      min-height: 260px;
      display: grid;
      place-items: center;
      text-align: center;
      padding: 28px;
      box-shadow: 0 1px 3px rgba(16, 24, 40, .08);
    }}
    .dropzone.dragging {{
      border-color: var(--accent);
      background: #eefaf9;
    }}
    .dropzone h2 {{
      font-size: 24px;
      margin: 0 0 10px;
    }}
    .dropzone p {{
      margin: 6px 0;
      color: var(--muted);
    }}
    button, select, input {{
      font: inherit;
    }}
    button {{
      border: 1px solid #b8c4d0;
      background: linear-gradient(#fff, #f5f7fa);
      padding: 9px 12px;
      border-radius: 7px;
      cursor: pointer;
    }}
    button.primary {{
      background: var(--accent);
      border-color: var(--accent-dark);
      color: #fff;
    }}
    button.danger {{
      color: var(--danger);
    }}
    select {{
      border: 1px solid #b8c4d0;
      border-radius: 7px;
      padding: 8px 10px;
      background: #fff;
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 16px;
      box-shadow: 0 1px 3px rgba(16, 24, 40, .06);
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }}
    .privacy {{
      border-left: 4px solid var(--accent);
      background: #eefaf9;
    }}
    .documents {{
      display: grid;
      gap: 10px;
    }}
    .document {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      display: grid;
      gap: 8px;
      background: #fff;
    }}
    .document strong {{
      word-break: break-word;
    }}
    .meta {{
      color: var(--muted);
      font-size: 12px;
    }}
    progress {{
      width: 100%;
      height: 12px;
    }}
    .hidden {{
      display: none;
    }}
    @media (max-width: 720px) {{
      main {{ padding: 16px; }}
      .toolbar {{ align-items: stretch; flex-direction: column; }}
      button, select {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header><h1>Laboratorio de validacao de PDF</h1></header>
  <main>
    <section class="dropzone" id="dropzone">
      <div>
        <h2>Arraste um ou mais PDFs para esta area</h2>
        <p>Ou selecione arquivos do computador para processar temporariamente.</p>
        <p><button class="primary" id="select-files">Selecionar PDFs</button></p>
        <p class="meta">
          Os arquivos sao temporarios e serao excluidos ao limpar ou encerrar
          a sessao.
        </p>
      </div>
    </section>
    <section class="panel toolbar">
      <label>Perfil
        <select id="profile">
          <option value="visual" selected>Visual</option>
          <option value="full_fidelity">Fidelidade completa</option>
        </select>
      </label>
      <button class="primary" id="start">Iniciar validacao</button>
      <button class="danger" id="clear">Limpar sessao e excluir arquivos</button>
      <input class="hidden" id="file-input" type="file" accept="application/pdf,.pdf" multiple>
    </section>
    <section class="panel privacy">
      <strong>Processamento temporario</strong>
      <p id="privacy"></p>
      <p class="meta">Historico desativado no modo temporario.</p>
    </section>
    <section class="panel">
      <h2>Documentos da sessao</h2>
      <div id="documents" class="documents"></div>
    </section>
  </main>
  <script id="boot-data" type="application/json">{payload}</script>
  <script>
    const boot = JSON.parse(document.getElementById("boot-data").textContent);
    const state = {{ session: null, files: [], heartbeat: null, transferring: false }};
    const $ = (id) => document.getElementById(id);
    const currentSessionId = () => state.session?.session_id || null;
    $("privacy").textContent = boot.privacy;
    if (boot.session) {{
      state.session = boot.session;
      startHeartbeat();
      renderDocuments(state.session.documents || []);
    }} else {{
      renderQueued();
    }}

    async function ensureSession() {{
      if (state.session) return state.session;
      const response = await fetch("/lab/sessions", {{ method: "POST" }});
      state.session = await response.json();
      if (!currentSessionId()) throw new Error("Sessao temporaria invalida");
      startHeartbeat();
      return state.session;
    }}

    function startHeartbeat() {{
      if (state.heartbeat) clearInterval(state.heartbeat);
      const interval = Math.max(5, Number(state.session.heartbeat_interval || 25)) * 1000;
      state.heartbeat = setInterval(() => {{
        const sessionId = currentSessionId();
        if (!sessionId) return;
        fetch(`/lab/sessions/${{sessionId}}/heartbeat`, {{ method: "POST" }});
      }}, interval);
    }}

    function addFiles(fileList) {{
      const incoming = Array.from(fileList || []);
      state.files.push(...incoming);
      renderQueued();
    }}

    function renderQueued() {{
      const list = $("documents");
      list.innerHTML = "";
      state.files.forEach((file, index) => {{
        const row = document.createElement("div");
        row.className = "document";
        row.innerHTML = `
          <strong>${{escapeHtml(file.name)}}</strong>
          <span class="meta">${{formatBytes(file.size)}} | aguardando</span>
          <button data-remove="${{index}}">Remover antes do processamento</button>
        `;
        list.appendChild(row);
      }});
      list.querySelectorAll("[data-remove]").forEach(button => {{
        button.addEventListener("click", () => {{
          state.files.splice(Number(button.dataset.remove), 1);
          renderQueued();
        }});
      }});
    }}

    async function startProcessing() {{
      if (!state.files.length) return;
      const session = await ensureSession();
      const sessionId = currentSessionId();
      if (!sessionId) throw new Error("Sessao temporaria invalida");
      renderProcessing();
      const form = new FormData();
      form.append("profile", $("profile").value);
      state.files.forEach(file => form.append("files", file, file.name));
      const response = await fetch(`/lab/sessions/${{sessionId}}/documents`, {{
        method: "POST",
        body: form
      }});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || "Falha no upload");
      state.files = [];
      state.session = payload;
      renderDocuments(payload.documents || []);
      if (payload.auto_open_document_id) {{
        const doc = (payload.documents || []).find(item =>
          item.document_id === payload.auto_open_document_id);
        if (doc?.report_url) {{
          state.transferring = true;
          location.href = doc.report_url;
        }}
      }}
    }}

    function renderProcessing() {{
      $("documents").innerHTML = state.files.map(file => `
        <div class="document">
          <strong>${{escapeHtml(file.name)}}</strong>
          <span class="meta">processando temporariamente</span>
          <progress max="1"></progress>
        </div>
      `).join("");
    }}

    function renderDocuments(documents) {{
      $("documents").innerHTML = documents.map(document => `
        <div class="document">
          <strong>${{escapeHtml(document.filename)}}</strong>
          <span class="meta">
            ${{formatBytes(document.size)}} |
            ${{escapeHtml(document.stage)}} |
            paginas: ${{document.page_count || 0}} |
            warnings: ${{document.warning_count || 0}} |
            limitacoes: ${{document.limitation_count || 0}}
          </span>
          <progress value="${{document.progress || 0}}" max="1"></progress>
          ${{document.error ? `<span class="meta">${{escapeHtml(document.error)}}</span>` : ""}}
          <div class="toolbar">
            ${{document.report_url ? `<a href="${{document.report_url}}">Abrir validacao</a>` : ""}}
            ${{exportLink(document)}}
            <button data-delete="${{document.document_id}}">Remover documento</button>
          </div>
        </div>
      `).join("");
      $("documents").querySelectorAll("[data-delete]").forEach(button => {{
        button.addEventListener("click", () => removeDocument(button.dataset.delete));
      }});
      $("documents").querySelectorAll("a").forEach(link => {{
        link.addEventListener("click", () => {{ state.transferring = true; }});
      }});
    }}

    function exportLink(document) {{
      if (!document.report_url) return "";
      const sessionId = currentSessionId();
      if (!sessionId) return "";
      const href = `/lab/sessions/${{sessionId}}/documents/${{document.document_id}}/export`;
      return `<a href="${{href}}">Exportar relatorio</a>`;
    }}

    async function removeDocument(documentId) {{
      const sessionId = currentSessionId();
      if (!sessionId) return;
      const response = await fetch(`/lab/sessions/${{sessionId}}/documents/${{documentId}}`, {{
        method: "DELETE"
      }});
      state.session = await response.json();
      renderDocuments(state.session.documents || []);
    }}

    async function clearSession() {{
      const sessionId = currentSessionId();
      if (!sessionId) {{
        state.files = [];
        state.session = null;
        renderQueued();
        return;
      }}
      const ok = confirm(
        "Os arquivos e resultados desta sessao serao excluidos. " +
        "Esta acao nao pode ser desfeita."
      );
      if (!ok) return;
      await fetch(`/lab/sessions/${{sessionId}}`, {{ method: "DELETE" }});
      if (state.heartbeat) clearInterval(state.heartbeat);
      state.session = null;
      state.files = [];
      renderQueued();
    }}

    function closeWithBeacon() {{
      if (!state.session || state.transferring) return;
      const sessionId = currentSessionId();
      if (!sessionId) return;
      const url = `/lab/sessions/${{sessionId}}/close`;
      navigator.sendBeacon?.(url);
      fetch(url, {{ method: "POST", keepalive: true }}).catch(() => undefined);
    }}

    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, char => ({{
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\\"": "&quot;", "'": "&#039;"
      }}[char]));
    }}

    function formatBytes(value) {{
      if (value < 1024) return `${{value}} B`;
      if (value < 1024 * 1024) return `${{(value / 1024).toFixed(1)}} KB`;
      return `${{(value / 1024 / 1024).toFixed(1)}} MB`;
    }}

    $("select-files").addEventListener("click", () => $("file-input").click());
    $("file-input").addEventListener("change", event => addFiles(event.target.files));
    $("start").addEventListener("click", () => startProcessing().catch(error => {{
      $("documents").innerHTML = `<div class="document"><strong>Falha</strong>
        <span class="meta">${{escapeHtml(error.message)}}</span></div>`;
    }}));
    $("clear").addEventListener("click", clearSession);
    ["dragenter", "dragover"].forEach(name => $("dropzone").addEventListener(name, event => {{
      event.preventDefault();
      $("dropzone").classList.add("dragging");
    }}));
    ["dragleave", "drop"].forEach(name => $("dropzone").addEventListener(name, event => {{
      event.preventDefault();
      $("dropzone").classList.remove("dragging");
    }}));
    $("dropzone").addEventListener("drop", event => addFiles(event.dataTransfer.files));
    window.addEventListener("pagehide", closeWithBeacon);
    window.addEventListener("beforeunload", closeWithBeacon);
  </script>
</body>
</html>"""


def _inject_temporary_report_controls(html: str, *, session_id: str) -> str:
    snippet = f"""
<script>
(function() {{
  const sessionId = {json.dumps(session_id)};
  const interval = 25000;
  let transferring = false;
  const bar = document.createElement("div");
  bar.style.cssText = [
    "position:fixed",
    "right:18px",
    "top:18px",
    "z-index:9999",
    "background:#101820",
    "color:#fff",
    "border-radius:8px",
    "padding:10px",
    "box-shadow:0 2px 8px rgba(16,24,40,.22)",
    "font:13px Segoe UI, Arial, sans-serif"
  ].join(";");
  bar.innerHTML = [
    "<strong>Sessao temporaria</strong>",
    "<a id='eixo-temp-uploads' "
      + "href='/lab/sessions/{session_id}' "
      + "style='color:#fff;margin-left:10px'>Voltar uploads</a>",
    "<button id='eixo-temp-clear' style='margin-left:10px'>Limpar sessao</button>"
  ].join("");
  document.body.appendChild(bar);
  document.getElementById("eixo-temp-uploads").addEventListener("click", () => {{
    transferring = true;
  }});
  const heartbeat = () => fetch(`/lab/sessions/${{sessionId}}/heartbeat`, {{
    method: "POST"
  }}).catch(() => undefined);
  const timer = setInterval(heartbeat, interval);
  heartbeat();
  document.getElementById("eixo-temp-clear").addEventListener("click", async () => {{
    const ok = confirm(
      "Os arquivos e resultados desta sessao serao excluidos. " +
      "Esta acao nao pode ser desfeita."
    );
    if (!ok) return;
    clearInterval(timer);
    await fetch(`/lab/sessions/${{sessionId}}`, {{ method: "DELETE" }});
    location.href = "/lab";
  }});
  const close = () => {{
    if (transferring) return;
    clearInterval(timer);
    const url = `/lab/sessions/${{sessionId}}/close`;
    navigator.sendBeacon?.(url);
    fetch(url, {{ method: "POST", keepalive: true }}).catch(() => undefined);
  }};
  window.addEventListener("pagehide", close);
  window.addEventListener("beforeunload", close);
}})();
</script>
"""
    if "</body>" in html:
        return html.replace("</body>", f"{snippet}</body>")
    return html + snippet


__all__ = ["router"]
