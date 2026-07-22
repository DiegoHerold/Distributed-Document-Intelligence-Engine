from __future__ import annotations

import pytest

from eixo import PDFParseOptions, PDFParseProfile, ValidationError


def test_pdf_parse_profile_accepts_public_names() -> None:
    assert PDFParseProfile.parse("basic") is PDFParseProfile.BASIC
    assert PDFParseProfile.parse("full-fidelity") is PDFParseProfile.FULL_FIDELITY
    assert PDFParseProfile.parse(None) is PDFParseProfile.VISUAL


def test_pdf_parse_options_redacts_password_and_uses_public_pages() -> None:
    options = PDFParseOptions.from_public_options(
        profile="textual",
        options={
            "page_selection": {"pages": [1, 3]},
            "password": "secret",
            "timeout": 2,
        },
    )

    assert options.profile is PDFParseProfile.TEXTUAL
    assert options.page_selection == (1, 3)
    assert options.page_indexes == (0, 2)
    assert options.safe_options()["password_provided"] is True
    assert "secret" not in str(options.to_dict())


def test_pdf_parse_profile_rejects_unknown_profile() -> None:
    with pytest.raises(ValidationError):
        PDFParseProfile.parse("everything")
