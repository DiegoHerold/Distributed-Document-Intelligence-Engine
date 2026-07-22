from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core import ValidationError
from eixo.core.serialization import Serializable


class PDFParseProfile(StrEnum):
    BASIC = "basic"
    TEXTUAL = "textual"
    VISUAL = "visual"
    FULL_FIDELITY = "full_fidelity"

    @classmethod
    def parse(cls, value: str | "PDFParseProfile" | None) -> "PDFParseProfile":
        if value is None:
            return cls.VISUAL
        if isinstance(value, cls):
            return value
        normalized = value.strip().lower().replace("-", "_")
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValidationError(
                "Unsupported PDF parse profile",
                details={
                    "profile": value,
                    "supported_profiles": [item.value for item in cls],
                },
            ) from exc


@dataclass(frozen=True, slots=True)
class PDFParseOptions(Serializable):
    profile: PDFParseProfile = PDFParseProfile.VISUAL
    page_selection: tuple[int, ...] | None = None
    include_hidden_elements: bool = True
    password: str | None = field(default=None, repr=False)
    timeout: float | None = None
    persist_artifacts: bool = True

    def __post_init__(self) -> None:
        profile = PDFParseProfile.parse(self.profile)
        object.__setattr__(self, "profile", profile)
        if self.page_selection is not None:
            if not self.page_selection:
                raise ValueError("page_selection cannot be empty")
            if any(page <= 0 for page in self.page_selection):
                raise ValueError("page_selection uses 1-based positive page numbers")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be positive")

    @classmethod
    def from_public_options(
        cls,
        *,
        profile: str | PDFParseProfile | None = None,
        page_selection: tuple[int, ...] | None = None,
        options: dict[str, Any] | None = None,
    ) -> "PDFParseOptions":
        raw = dict(options or {})
        raw_profile = profile or raw.pop("profile", None)
        raw_pages = page_selection or _page_selection_from(raw.pop("page_selection", None))
        if raw_pages is None:
            raw_pages = _page_selection_from(raw.pop("pages", None))
        include_hidden = raw.pop("include_hidden_elements", True)
        password = raw.pop("password", None)
        timeout = raw.pop("timeout", raw.pop("timeout_seconds", None))
        persist = raw.pop("persist_artifacts", True)
        return cls(
            profile=PDFParseProfile.parse(raw_profile),
            page_selection=raw_pages,
            include_hidden_elements=bool(include_hidden),
            password=str(password) if password is not None else None,
            timeout=float(timeout) if timeout is not None else None,
            persist_artifacts=bool(persist),
        )

    @property
    def page_indexes(self) -> tuple[int, ...] | None:
        if self.page_selection is None:
            return None
        return tuple(page - 1 for page in self.page_selection)

    def safe_options(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "page_selection": list(self.page_selection) if self.page_selection else None,
            "include_hidden_elements": self.include_hidden_elements,
            "timeout": self.timeout,
            "persist_artifacts": self.persist_artifacts,
            "password_provided": self.password is not None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


def _page_selection_from(value: object) -> tuple[int, ...] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return _page_selection_from(value.get("pages"))
    if isinstance(value, int):
        return (value,)
    if isinstance(value, str):
        return _parse_page_ranges(value)
    if isinstance(value, (list, tuple, set)):
        pages = tuple(int(item) for item in value)
        return pages or None
    raise ValidationError("page_selection must be a page number, list, range or object")


def _parse_page_ranges(value: str) -> tuple[int, ...] | None:
    pages: list[int] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValidationError("page range end must be greater than or equal to start")
            pages.extend(range(start, end + 1))
            continue
        pages.append(int(token))
    return tuple(dict.fromkeys(pages)) or None


__all__ = ["PDFParseOptions", "PDFParseProfile"]
