from __future__ import annotations

from eixo_api.application import create_app

app = create_app()

__all__ = ["app", "create_app"]
