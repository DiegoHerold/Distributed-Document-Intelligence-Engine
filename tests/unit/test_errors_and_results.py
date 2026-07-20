from __future__ import annotations

from eixo.core import (
    CapabilityNotFoundError,
    ErrorCategory,
    EixoWarning,
    OperationResult,
    Severity,
)


def test_domain_error_payload_is_safe() -> None:
    error = CapabilityNotFoundError(
        "missing capability",
        details={"internal": "kept structured"},
        public_context={"capability": "document.inspect"},
    )
    payload = error.to_payload()

    assert payload.code == "capability.not_found"
    assert payload.category is ErrorCategory.CAPABILITY
    assert payload.public_context["capability"] == "document.inspect"


def test_operation_result_carries_warnings_and_errors() -> None:
    warning = EixoWarning(code="sample.warning", message="careful", severity=Severity.WARNING)
    result = OperationResult(value={"ok": True}, warnings=(warning,))

    assert result.ok
    assert result.to_dict()["warnings"][0]["code"] == "sample.warning"

