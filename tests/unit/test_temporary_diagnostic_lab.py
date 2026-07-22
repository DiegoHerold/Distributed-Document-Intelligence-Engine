from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from eixo.core import ValidationError
from eixo.diagnostics import (
    TemporaryDiagnosticConfig,
    TemporaryDiagnosticSessionCleaner,
    TemporaryDiagnosticStore,
)
from eixo.diagnostics.temporary_lab import (
    sanitize_temporary_filename,
    validate_pdf_upload,
)


def test_temporary_store_creates_isolated_session_and_cleans_by_inactivity(
    tmp_path,
) -> None:
    store = TemporaryDiagnosticStore(
        TemporaryDiagnosticConfig(
            root_directory=tmp_path / "temporary-diagnostics",
            heartbeat_interval=1,
            inactive_session_grace_period=1,
            maximum_session_lifetime=60,
            cleanup_interval=1,
        )
    )
    session = store.create_session()
    store.save_upload(
        session.session_id,
        filename="../unsafe.pdf",
        content=b"%PDF-1.7\n",
    )

    assert session.uploads_directory.exists()
    assert session.artifacts_directory.exists()
    assert session.previews_directory.exists()
    assert session.reports_directory.exists()
    assert session.runtime_directory.exists()
    assert session.documents
    assert all(".." not in document.filename for document in session.documents.values())

    session.last_activity_at = datetime.now(UTC) - timedelta(seconds=2)
    removed = TemporaryDiagnosticSessionCleaner(store).cleanup()

    assert removed == [session.session_id]
    assert not session.root_directory.exists()
    assert session.session_id not in store.sessions


def test_temporary_pdf_validation_rejects_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        validate_pdf_upload(b"not a pdf", max_size=100)
    with pytest.raises(ValidationError):
        sanitize_temporary_filename("../")


def test_temporary_store_blocks_report_path_traversal(tmp_path) -> None:
    store = TemporaryDiagnosticStore(
        TemporaryDiagnosticConfig(root_directory=tmp_path / "temporary-diagnostics")
    )
    session = store.create_session()
    document = store.save_upload(
        session.session_id,
        filename="ok.pdf",
        content=b"%PDF-1.7\n",
    )
    run = session.reports_directory / "documents" / "ok" / "runs" / "run_fake"
    run.mkdir(parents=True)
    (run / "report.html").write_text("ok", encoding="utf-8")
    document.report_directory = run
    document.html_report_path = run / "report.html"

    assert store.resolve_report_file(
        session.session_id,
        document.document_id,
        "report.html",
    ).name == "report.html"
    with pytest.raises(ValidationError):
        store.resolve_report_file(session.session_id, document.document_id, "../x")
